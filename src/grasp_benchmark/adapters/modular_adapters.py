from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from grasp_benchmark.adapters.base import AgentAdapter, AdapterExecutionError
from grasp_benchmark.adapters.modular_components import (
    PerceptionResult,
    SharedModularPerception,
    build_shared_pick_plan,
)
from grasp_benchmark.paths import PROJECT_ROOT
from grasp_benchmark.types import Action, Observation


def _project_root(runtime_config: dict[str, Any]) -> Path:
    return Path(str(runtime_config.get("project_root", PROJECT_ROOT)))


def _require_path(path: Path, *, failure_stage: str, description: str) -> Path:
    if not path.exists():
        raise AdapterExecutionError(f"Missing {description}: {path}", failure_stage=failure_stage)
    return path


def _legacy_ld_library_path(legacy_env_prefix: Path, cuda_home: str) -> str:
    entries: list[str] = []
    normalized_cuda_home = str(cuda_home or "").rstrip("/")
    if normalized_cuda_home:
        entries.append(f"{normalized_cuda_home}/lib64")
    entries.append((legacy_env_prefix / "lib").as_posix())
    entries.append((legacy_env_prefix / "lib" / "python3.10" / "site-packages" / "nvidia" / "cudnn" / "lib").as_posix())
    entries.extend(["/usr/lib64", "/usr/lib/x86_64-linux-gnu"])
    return ":".join(entries) + "${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"


def _legacy_cuda_visible_devices(runtime_gpu_id: str, environ: dict[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    inherited = str(env.get("CUDA_VISIBLE_DEVICES", "")).strip()
    if inherited:
        return inherited
    return str(runtime_gpu_id or "0").strip() or "0"


def _legacy_runner_timeout_s(runtime_config: dict[str, Any]) -> float:
    timeout_ms = max(int(runtime_config.get("timeout_ms", 10000)), 0)
    return max(timeout_ms / 1000.0, 300.0)


def _cgn_runner_trace_summary(trace_events: list[Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for event in trace_events:
        if not isinstance(event, dict):
            continue
        stage = str(event.get("stage", ""))
        if stage == "tensorflow_imported":
            summary["tensorflow_gpu_count"] = int(event.get("gpu_count", 0) or 0)
        elif stage == "input_loaded":
            summary["input_contract"] = event.get("input_contract")
            summary["use_raw_points"] = bool(event.get("use_raw_points", False))
            summary["points_shape"] = event.get("points_shape")
            summary["segment_ids_shape"] = event.get("segment_ids_shape")
            summary["depth_shape"] = event.get("depth_shape")
            summary["K_shape"] = event.get("K_shape")
            summary["segmap_shape"] = event.get("segmap_shape")
            summary["has_rgb"] = bool(event.get("has_rgb", False))
        elif stage == "point_cloud_ready":
            summary["pc_full_shape"] = event.get("pc_full_shape")
            summary["segment_shapes"] = event.get("segment_shapes")
        elif stage == "predict_scene_grasps_start":
            summary["local_regions"] = bool(event.get("local_regions", False))
            summary["filter_grasps"] = bool(event.get("filter_grasps", False))
            summary["forward_passes"] = int(event.get("forward_passes", 0) or 0)
        elif stage == "predict_scene_grasps_done":
            summary["grasp_counts"] = event.get("grasp_counts")
            summary["score_counts"] = event.get("score_counts")
    return summary


def _workspace_limits(sensor_config: dict[str, Any]) -> list[float]:
    workspace_cm = sensor_config.get("workspace_cm", {})
    half_x = float(workspace_cm.get("x", 40.0)) / 200.0
    half_y = float(workspace_cm.get("y", 50.0)) / 200.0
    max_z = max(float(workspace_cm.get("z", 20.0)) / 100.0, 0.2)
    return [-half_x, half_x, -half_y, half_y, 0.0, max_z]


class _SharedModularAdapterBase(AgentAdapter):
    def _reset_latest_payloads(self) -> None:
        self._latest_debug_payload: dict[str, Any] = {}
        self._latest_stage_metrics = {
            "grounding_success": -1,
            "mask_nonempty": 0,
            "proposal_nonempty": 0,
            "plan_success": 0,
        }

    def _setup_shared_modular(self, config: dict[str, Any]) -> None:
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise AdapterExecutionError(
                f"Shared modular execution requires numpy and opencv in the active environment: {exc}",
                failure_stage="dependency_setup",
            ) from exc

        self.runtime_config = config
        self._np = np
        for alias, target in (("float", float), ("int", int), ("bool", bool)):
            if not hasattr(self._np, alias):
                setattr(self._np, alias, target)
        self._instruction = ""
        self._pending_actions: list[Action] = []
        self._candidate_payloads: list[dict[str, Any]] = []
        debug_dump_dir = str(config.get("debug_dump_dir", "")).strip()
        self._debug_dump_dir = Path(debug_dump_dir) if debug_dump_dir else None
        self._planner_config = dict(self.method_config.get("planner", {}))
        planner_overrides = config.get("planner_overrides", {})
        if isinstance(planner_overrides, dict):
            self._planner_config.update(planner_overrides)
        self._single_plan_per_attempt = bool(self._planner_config.get("single_plan_per_attempt", False))
        self._attempt_complete = False
        self._perception = SharedModularPerception(
            method_config=self.method_config,
            runtime_config=config,
            np_module=np,
            cv2_module=cv2,
        )
        self._reset_latest_payloads()

    def reset(self, task_spec: dict[str, Any]) -> None:
        self.task_spec = task_spec
        self._instruction = str(task_spec.get("instruction", "")).strip()
        self._pending_actions = []
        self._candidate_payloads = []
        self._attempt_complete = False
        self._reset_latest_payloads()

    def attempt_complete(self) -> bool:
        return bool(self._attempt_complete)

    def latest_debug_payload(self) -> dict[str, Any]:
        return dict(self._latest_debug_payload)

    def latest_stage_metrics(self) -> dict[str, int]:
        return dict(self._latest_stage_metrics)

    def _write_debug_payload(self, prefix: str, payload: dict[str, Any]) -> None:
        if self._debug_dump_dir is None:
            return
        self._debug_dump_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            encoding="utf-8",
            dir=self._debug_dump_dir,
            prefix=prefix,
            suffix=".json",
        ) as handle:
            json.dump(payload, handle, indent=2)

    def _proposal_payload(self, obs: Observation, perception: PerceptionResult) -> dict[str, Any]:
        raise NotImplementedError

    def _candidate_sequence(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = payload.get("candidate_grasps")
        if isinstance(candidates, list) and candidates:
            normalized: list[dict[str, Any]] = []
            inherited_debug = {
                key: payload[key]
                for key in ("segment_key", "grasp_count", "runner_trace_summary")
                if key in payload
            }
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                candidate_payload = dict(candidate)
                for key, value in inherited_debug.items():
                    candidate_payload.setdefault(key, value)
                normalized.append(candidate_payload)
            if normalized:
                return normalized
        return [dict(payload)]

    def _candidate_validation_failure(self, candidate: dict[str, Any]) -> str:
        if not bool(self._planner_config.get("validate_gripper_opening", False)):
            return ""
        if "gripper_opening_m" not in candidate:
            return ""
        try:
            opening_m = float(candidate.get("gripper_opening_m"))
        except (TypeError, ValueError):
            return "candidate rejected: gripper_opening_m is not numeric"
        if not bool(self._np.isfinite(opening_m)):
            return "candidate rejected: gripper_opening_m is not finite"
        min_opening_m = float(self._planner_config.get("min_gripper_opening_m", 0.0))
        max_opening_m = float(self._planner_config.get("max_gripper_opening_m", 0.085))
        if opening_m < min_opening_m:
            return (
                "candidate rejected: gripper_opening_m "
                f"{opening_m:.4f} below min_gripper_opening_m {min_opening_m:.4f}"
            )
        if opening_m > max_opening_m:
            return (
                "candidate rejected: gripper_opening_m "
                f"{opening_m:.4f} above max_gripper_opening_m {max_opening_m:.4f}"
            )
        return ""

    def _plan_candidate(self, obs: Observation, candidate: dict[str, Any]) -> tuple[list[Action], dict[str, Any]]:
        translation = candidate.get("best_translation")
        if translation is None:
            raise AdapterExecutionError(
                "The modular grasp pipeline did not produce a target translation for the shared planner.",
                failure_stage="planner_failure",
            )
        planned_actions, planner_debug = build_shared_pick_plan(
            obs,
            self._np,
            translation_cam=self._np.asarray(translation, dtype=self._np.float32),
            planner_config=self._planner_config,
            grasp_matrix_cam=(
                self._np.asarray(candidate["best_grasp"], dtype=self._np.float32)
                if self._planner_config.get("use_grasp_pose", True) and candidate.get("best_grasp") is not None
                else None
            ),
            return_debug=True,
        )
        planner_debug["proposal_source"] = str(candidate.get("proposal_source", "model"))
        planner_debug["proposal_score"] = float(candidate.get("best_score", 0.0))
        return planned_actions, planner_debug

    def _plan_next_viable_candidate(
        self,
        obs: Observation,
        first_candidate: dict[str, Any],
    ) -> tuple[dict[str, Any], list[Action], dict[str, Any], list[str]]:
        candidate = first_candidate
        skipped: list[str] = []
        while True:
            validation_failure = self._candidate_validation_failure(candidate)
            if validation_failure:
                skipped.append(validation_failure)
                if not self._candidate_payloads:
                    raise AdapterExecutionError(
                        "All modular grasp candidates were rejected before planning: " + "; ".join(skipped),
                        failure_stage="grasp_proposal",
                    )
                candidate = self._candidate_payloads.pop(0)
                continue
            try:
                planned_actions, planner_debug = self._plan_candidate(obs, candidate)
                if skipped:
                    planner_debug["skipped_planner_candidates"] = list(skipped)
                return candidate, planned_actions, planner_debug, skipped
            except AdapterExecutionError as exc:
                if exc.failure_stage != "planner_failure" or not self._candidate_payloads:
                    raise
                skipped.append(str(exc))
                candidate = self._candidate_payloads.pop(0)

    def step(self, obs: Observation) -> Action:
        if self._pending_actions:
            action = self._pending_actions.pop(0)
            if self._single_plan_per_attempt and not self._pending_actions and not self._candidate_payloads:
                self._attempt_complete = True
            return action

        self._attempt_complete = False
        self._reset_latest_payloads()
        perception = None
        payload = None
        try:
            if self._candidate_payloads:
                candidate = self._candidate_payloads.pop(0)
                self._latest_stage_metrics["proposal_nonempty"] = 1
                candidate, planned_actions, planner_debug, _skipped = self._plan_next_viable_candidate(obs, candidate)
            else:
                perception = self._perception.observe(
                    task_spec=self.task_spec,
                    instruction=self._instruction or obs.instruction,
                    obs=obs,
                )
                if str(self.task_spec.get("task", "")).strip() == "language_conditioned_single_target_pick":
                    self._latest_stage_metrics["grounding_success"] = 1 if perception.detection is not None else 0
                self._latest_stage_metrics["mask_nonempty"] = int(bool(perception.debug.get("mask_pixels", 0)))
                payload = self._proposal_payload(obs, perception)
                self._latest_stage_metrics["proposal_nonempty"] = 1
                candidates = self._candidate_sequence(payload)
                candidate = candidates[0]
                self._candidate_payloads = candidates[1:]
                candidate, planned_actions, planner_debug, _skipped = self._plan_next_viable_candidate(obs, candidate)
        except AdapterExecutionError as exc:
            if exc.failure_stage == "grounding_error":
                self._latest_stage_metrics["grounding_success"] = 0
            elif exc.failure_stage == "segmentation_error":
                if self._latest_stage_metrics["grounding_success"] < 0 and str(self.task_spec.get("task", "")).strip() == "language_conditioned_single_target_pick":
                    self._latest_stage_metrics["grounding_success"] = 0
                self._latest_stage_metrics["mask_nonempty"] = 0
            elif exc.failure_stage == "grasp_proposal":
                self._latest_stage_metrics["proposal_nonempty"] = 0
            elif exc.failure_stage == "planner_failure":
                self._latest_stage_metrics["plan_success"] = 0
            raise
        replan_action_horizon = max(int(self._planner_config.get("replan_action_horizon", 0)), 0)
        if replan_action_horizon > 0:
            self._pending_actions = planned_actions[:replan_action_horizon]
            planner_debug["planned_plan_length"] = int(len(planned_actions))
            planner_debug["executed_plan_length"] = int(len(self._pending_actions))
            planner_debug["replan_action_horizon"] = int(replan_action_horizon)
        else:
            self._pending_actions = planned_actions
            planner_debug["planned_plan_length"] = int(len(planned_actions))
            planner_debug["executed_plan_length"] = int(len(self._pending_actions))
        self._latest_stage_metrics["plan_success"] = 1 if self._pending_actions else 0
        if self._debug_dump_dir is not None:
            latest_payload = {
                "instruction": self._instruction or obs.instruction,
                "task_spec": self.task_spec,
                "perception": {} if perception is None else perception.debug,
                "proposal": candidate,
                "remaining_candidate_count": len(self._candidate_payloads),
                "planner": planner_debug,
                "stage_metrics": self._latest_stage_metrics,
            }
            self._latest_debug_payload = dict(latest_payload)
            self._write_debug_payload(f"{self.name}_perception_", latest_payload)
        else:
            self._latest_debug_payload = {
                "instruction": self._instruction or obs.instruction,
                "task_spec": self.task_spec,
                "perception": {} if perception is None else perception.debug,
                "proposal": candidate,
                "remaining_candidate_count": len(self._candidate_payloads),
                "planner": planner_debug,
                "stage_metrics": dict(self._latest_stage_metrics),
            }
        if not self._pending_actions:
            raise AdapterExecutionError(
                "Shared modular planner failed to produce any executable actions.",
                failure_stage="planner_failure",
            )
        action = self._pending_actions.pop(0)
        if self._single_plan_per_attempt and not self._pending_actions and not self._candidate_payloads:
            self._attempt_complete = True
        return action


class AnyGraspAdapter(_SharedModularAdapterBase):
    adapter_kind = "anygrasp"

    def setup(self, config: dict[str, Any]) -> None:
        self._setup_shared_modular(config)
        project_root = _project_root(config)
        self._sdk_root = _require_path(
            project_root / "third_party" / "upstreams" / "anygrasp_sdk",
            failure_stage="dependency_setup",
            description="AnyGrasp upstream checkout",
        )
        self._detection_root = _require_path(
            self._sdk_root / "grasp_detection",
            failure_stage="dependency_setup",
            description="AnyGrasp grasp_detection package",
        )
        license_cfg = self._detection_root / str(self.method_config.get("license_cfg_relpath", "license/licenseCfg.json"))
        _require_path(license_cfg, failure_stage="license", description="AnyGrasp license configuration")
        checkpoint_path = self._detection_root / str(
            self.method_config.get("checkpoint_relpath", "log/checkpoint_detection.tar")
        )
        _require_path(checkpoint_path, failure_stage="model_assets", description="AnyGrasp checkpoint")

        try:
            import MinkowskiEngine  # noqa: F401
        except ImportError as exc:
            raise AdapterExecutionError(
                "AnyGrasp requires MinkowskiEngine in the active environment.",
                failure_stage="dependency_setup",
            ) from exc

        if str(self._detection_root) not in sys.path:
            sys.path.insert(0, str(self._detection_root))

        try:
            from gsnet import AnyGrasp  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on native SDK binary
            raise AdapterExecutionError(
                f"Failed to import AnyGrasp SDK from {self._detection_root}.",
                failure_stage="dependency_setup",
            ) from exc

        cfg = SimpleNamespace(
            checkpoint_path=str(checkpoint_path),
            max_gripper_width=float(config.get("max_gripper_width", 0.1)),
            gripper_height=float(config.get("gripper_height", 0.03)),
            top_down_grasp=bool(config.get("top_down_grasp", False)),
            debug=bool(config.get("debug", False)),
        )
        try:
            self._model = AnyGrasp(cfg)
            self._model.load_net()
        except Exception as exc:  # pragma: no cover - depends on external model assets
            lower = str(exc).lower()
            failure_stage = "license" if "license" in lower else "model_assets"
            raise AdapterExecutionError(
                f"AnyGrasp model bootstrap failed: {exc}",
                failure_stage=failure_stage,
            ) from exc

    def _proposal_payload(self, obs: Observation, perception: PerceptionResult) -> dict[str, Any]:
        try:
            grasp_group, _ = self._model.get_grasp(
                perception.points,
                perception.colors,
                lims=_workspace_limits(self.sensor_config),
                apply_object_mask=True,
                dense_grasp=False,
                collision_detection=True,
            )
        except Exception as exc:  # pragma: no cover - depends on external model assets
            lower = str(exc).lower()
            failure_stage = "license" if "license" in lower else "grasp_proposal"
            raise AdapterExecutionError(
                f"AnyGrasp inference failed: {exc}",
                failure_stage=failure_stage,
            ) from exc

        if grasp_group is None:
            raise AdapterExecutionError(
                "AnyGrasp returned no grasp group for the current masked observation.",
                failure_stage="grasp_proposal",
            )

        if hasattr(grasp_group, "nms"):
            grasp_group = grasp_group.nms().sort_by_score()
        if grasp_group is None:
            raise AdapterExecutionError(
                "AnyGrasp post-processing removed every grasp candidate for the current masked observation.",
                failure_stage="grasp_proposal",
            )

        if len(grasp_group) == 0:
            raise AdapterExecutionError(
                "AnyGrasp returned zero grasp proposals for the current masked observation.",
                failure_stage="grasp_proposal",
            )
        best_translation = None
        best_score = 0.0
        if hasattr(grasp_group, "translations"):
            best_translation = self._np.asarray(grasp_group.translations[0], dtype=self._np.float32)
            if hasattr(grasp_group, "scores"):
                best_score = float(grasp_group.scores[0])
        elif len(grasp_group) > 0 and hasattr(grasp_group[0], "translation"):
            best_translation = self._np.asarray(grasp_group[0].translation, dtype=self._np.float32)
            best_score = float(getattr(grasp_group[0], "score", 0.0))
        if best_translation is None:
            raise AdapterExecutionError(
                "AnyGrasp produced grasp proposals but no translation could be extracted.",
                failure_stage="grasp_proposal",
            )
        return {
            "best_translation": best_translation.tolist(),
            "best_score": round(best_score, 4),
        }

    def close(self) -> None:
        self._model = None


class ContactGraspNetAdapter(_SharedModularAdapterBase):
    adapter_kind = "cgn"

    def setup(self, config: dict[str, Any]) -> None:
        self._setup_shared_modular(config)
        project_root = _project_root(config)
        self._upstream_root = _require_path(
            project_root / "third_party" / "upstreams" / "contact_graspnet",
            failure_stage="dependency_setup",
            description="Contact-GraspNet upstream checkout",
        )
        self._checkpoint_dir = self._upstream_root / str(
            self.method_config.get("checkpoint_relpath", "checkpoints/scene_test_2048_bs3_hor_sigma_001")
        )
        if not self._checkpoint_dir.exists() or not any(self._checkpoint_dir.iterdir()):
            raise AdapterExecutionError(
                f"Contact-GraspNet checkpoint directory is missing or empty: {self._checkpoint_dir}",
                failure_stage="model_assets",
            )

        miniforge_root = str(config.get("miniforge_root", ""))
        conda_envs_dir = str(config.get("conda_envs_dir", ""))
        legacy_env_name = str(self.method_config.get("legacy_env_name", ""))
        self._legacy_env_prefix = Path(conda_envs_dir) / legacy_env_name if conda_envs_dir and legacy_env_name else None
        if self._legacy_env_prefix is None or not self._legacy_env_prefix.exists():
            raise AdapterExecutionError(
                "Contact-GraspNet requires a prepared TensorFlow runtime. "
                "Run python -m grasp_benchmark.prepare_cgn --node <host> --bootstrap-legacy-env first.",
                failure_stage="legacy_runtime",
            )
        self._miniforge_root = Path(miniforge_root)
        if not self._miniforge_root.exists():
            raise AdapterExecutionError(
                f"Missing Miniforge root required for conda-run bridge: {self._miniforge_root}",
                failure_stage="legacy_runtime",
            )
        self._cuda_home = str(config.get("cuda_home", "") or "").rstrip("/")
        self._forward_passes = int(config.get("forward_passes", 1))
        self._z_min = float(config.get("z_min", 0.2))
        self._z_max = float(config.get("z_max", 1.1))
        execution_mode = str(config.get("execution_mode", ""))
        is_formal_track_a = execution_mode == "shared_track_a_sim" or execution_mode.startswith("track_a_diag_")
        stride_key = "formal_downsample_stride" if is_formal_track_a else "smoke_downsample_stride"
        self._downsample_stride = max(int(self.method_config.get(stride_key, 1)), 1)
        self._gpu_id = str(config.get("gpu_id", "0") or "0")
        self._cuda_visible_devices = _legacy_cuda_visible_devices(self._gpu_id)
        candidate_top_k = self._planner_config.get("candidate_top_k", 1)
        self._native_top_k = max(int(config.get("native_top_k", candidate_top_k)), 1)

    def _oracle_topdown_payload(self, obs: Observation, perception: PerceptionResult) -> dict[str, Any]:
        points = self._np.asarray(perception.points, dtype=self._np.float32)
        if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 3:
            raise AdapterExecutionError(
                "Oracle grasp mode requires a non-empty masked point cloud.",
                failure_stage="grasp_proposal",
            )
        extrinsic = self._np.asarray(obs.extrinsics_front.get("matrix"), dtype=self._np.float32)
        if extrinsic.shape != (4, 4):
            raise AdapterExecutionError(
                "Oracle grasp mode requires a 4x4 front-camera extrinsic matrix.",
                failure_stage="planner_failure",
            )
        centroid_cam = self._np.mean(points[:, :3], axis=0).astype(self._np.float32)
        point_cam = self._np.asarray([centroid_cam[0], centroid_cam[1], centroid_cam[2], 1.0], dtype=self._np.float32)
        centroid_world = (extrinsic @ point_cam)[:3]
        grasp_world = self._np.eye(4, dtype=self._np.float32)
        grasp_world[:3, :3] = self._np.asarray(
            [
                [1.0, 0.0, 0.0],
                [0.0, -1.0, 0.0],
                [0.0, 0.0, -1.0],
            ],
            dtype=self._np.float32,
        )
        grasp_world[:3, 3] = centroid_world
        camera_from_world = self._np.linalg.inv(extrinsic)
        grasp_cam = camera_from_world @ grasp_world
        return {
            "best_translation": centroid_cam.tolist(),
            "best_grasp": grasp_cam.tolist(),
            "best_score": 1.0,
            "proposal_source": "oracle_topdown_centroid",
            "masked_point_count": int(points.shape[0]),
        }

    def _proposal_payload(self, obs: Observation, perception: PerceptionResult) -> dict[str, Any]:
        oracle_grasp_mode = str(self.runtime_config.get("oracle_grasp_mode", "")).strip().lower()
        if oracle_grasp_mode == "topdown_centroid":
            return self._oracle_topdown_payload(obs, perception)
        if os.name == "nt":
            raise AdapterExecutionError(
                "Contact-GraspNet legacy-env execution is only supported on the Linux cluster nodes.",
                failure_stage="legacy_runtime",
            )

        with tempfile.TemporaryDirectory(prefix="gb-cgn-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.npz"
            output_path = tmp_path / "output.json"
            trace_path = tmp_path / "trace.json"
            if bool(self.runtime_config.get("native_multiview_fusion", False)):
                self._np.savez(
                    input_path,
                    points=self._np.asarray(perception.points, dtype=self._np.float32),
                    colors=self._np.asarray(perception.colors, dtype=self._np.float32),
                    segment_ids=(
                        self._np.asarray(perception.segment_ids, dtype=self._np.int32)
                        if perception.segment_ids is not None
                        else self._np.ones((int(len(perception.points)),), dtype=self._np.int32)
                    ),
                )
            else:
                depth = self._np.asarray(obs.depth_front, dtype=self._np.float32)
                rgb = self._np.asarray(obs.rgb_front, dtype=self._np.uint8)
                segmap = self._np.asarray(perception.segmap, dtype=self._np.uint8)
                if self._downsample_stride > 1:
                    depth = depth[:: self._downsample_stride, :: self._downsample_stride]
                    rgb = rgb[:: self._downsample_stride, :: self._downsample_stride, :]
                    segmap = segmap[:: self._downsample_stride, :: self._downsample_stride]

                K = self._np.array(
                    [
                        [float(obs.intrinsics_front.get("fx", 0.0)), 0.0, float(obs.intrinsics_front.get("cx", 0.0))],
                        [0.0, float(obs.intrinsics_front.get("fy", 0.0)), float(obs.intrinsics_front.get("cy", 0.0))],
                        [0.0, 0.0, 1.0],
                    ],
                    dtype=self._np.float32,
                )
                if self._downsample_stride > 1:
                    K[0, 0] /= self._downsample_stride
                    K[1, 1] /= self._downsample_stride
                    K[0, 2] /= self._downsample_stride
                    K[1, 2] /= self._downsample_stride
                if K[0, 0] <= 0 or K[1, 1] <= 0:
                    raise AdapterExecutionError(
                        "Contact-GraspNet requires positive camera intrinsics.",
                        failure_stage="observation",
                    )
                self._np.savez(input_path, depth=depth, K=K, rgb=rgb, segmap=segmap)
            runner_cmd = [
                "bash",
                "-lc",
                (
                    'env -u CC -u CXX -u CUDAHOSTCXX '
                    f'PYTHONPATH="{_project_root(self.runtime_config) / "src"}" '
                    f'LD_PRELOAD="{(self._legacy_env_prefix / "lib" / "libstdc++.so.6").as_posix()}" '
                    f'LD_LIBRARY_PATH="{_legacy_ld_library_path(self._legacy_env_prefix, self._cuda_home)}" '
                    f'CUDA_HOME="{self._cuda_home}" '
                    f'CUDA_VISIBLE_DEVICES="{self._cuda_visible_devices}" "{(self._legacy_env_prefix / "bin" / "python").as_posix()}" -m grasp_benchmark.runners.contact_graspnet '
                    f'--input "{input_path}" '
                    f'--output "{output_path}" '
                    f'--upstream-root "{self._upstream_root}" '
                    f'--checkpoint-dir "{self._checkpoint_dir}" '
                    f'--forward-passes {self._forward_passes} '
                    f'--z-min {self._z_min} '
                    f'--z-max {self._z_max} '
                    f'--top-k {self._native_top_k} '
                    f'--cuda-visible-devices "{self._cuda_visible_devices}" '
                    f'--trace-json "{trace_path}"'
                ),
            ]
            child_env = {
                key: value
                for key, value in os.environ.items()
                if key
                not in {
                    "CC",
                    "CXX",
                    "CUDAHOSTCXX",
                    "CONDA_DEFAULT_ENV",
                    "CONDA_PREFIX",
                    "CONDA_PROMPT_MODIFIER",
                    "CONDA_SHLVL",
                    "CONDA_EXE",
                    "CONDA_PYTHON_EXE",
                    "PYTHONPATH",
                    "LD_LIBRARY_PATH",
                    "LD_PRELOAD",
                    "CUDA_VISIBLE_DEVICES",
                }
            }
            child_env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            timeout_s = _legacy_runner_timeout_s(self.runtime_config)
            try:
                completed = subprocess.run(
                    runner_cmd,
                    capture_output=True,
                    text=True,
                    env=child_env,
                    timeout=timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                debug_dir = _project_root(self.runtime_config) / "artifacts" / "debug" / "cgn_legacy_runtime"
                debug_dir.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    delete=False,
                    encoding="utf-8",
                    dir=debug_dir,
                    prefix="cgn_legacy_timeout_",
                    suffix=".log",
                ) as handle:
                    handle.write("COMMAND:\n")
                    handle.write(" ".join(runner_cmd))
                    handle.write("\n\nSTDOUT:\n")
                    handle.write((exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or ""))
                    handle.write("\n\nSTDERR:\n")
                    handle.write((exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or ""))
                    debug_log_path = Path(handle.name)
                raise AdapterExecutionError(
                    f"Contact-GraspNet runner timed out after {timeout_s:.1f}s; see {debug_log_path}.",
                    failure_stage="grasp_proposal",
                ) from exc
            if completed.returncode != 0:
                stdout = (completed.stdout or "").strip()
                stderr = (completed.stderr or "").strip()
                details = stderr if stderr else stdout
                if stdout and stderr:
                    details = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
                if not details:
                    details = "Runner exited non-zero without stdout/stderr output."
                debug_dir = _project_root(self.runtime_config) / "artifacts" / "debug" / "cgn_legacy_runtime"
                debug_dir.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    delete=False,
                    encoding="utf-8",
                    dir=debug_dir,
                    prefix="cgn_legacy_",
                    suffix=".log",
                ) as handle:
                    handle.write("COMMAND:\n")
                    handle.write(" ".join(runner_cmd))
                    handle.write("\n\nSTDOUT:\n")
                    handle.write(completed.stdout or "")
                    handle.write("\n\nSTDERR:\n")
                    handle.write(completed.stderr or "")
                    debug_log_path = Path(handle.name)
                raise AdapterExecutionError(
                    f"Contact-GraspNet runner failed (exit={completed.returncode}); see {debug_log_path}: {details[-4000:]}",
                    failure_stage="legacy_runtime",
                )
            if not output_path.exists():
                raise AdapterExecutionError(
                    "Contact-GraspNet runner did not produce an output payload.",
                    failure_stage="adapter_bridge",
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            if trace_path.exists():
                try:
                    trace_events = json.loads(trace_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    trace_events = []
                if isinstance(trace_events, list):
                    payload["runner_trace_summary"] = _cgn_runner_trace_summary(trace_events)
            if not payload.get("ok"):
                self._write_debug_payload("cgn_payload_", payload)
                raise AdapterExecutionError(
                    str(payload.get("failure_reason", "Contact-GraspNet produced no valid grasp.")),
                    failure_stage=str(payload.get("failure_stage", "grasp_proposal")),
                )
            candidates = payload.get("candidate_grasps")
            if isinstance(candidates, list) and candidates:
                payload["candidate_grasps"] = [dict(candidate) for candidate in candidates if isinstance(candidate, dict)]
            return payload

    def close(self) -> None:
        return None
