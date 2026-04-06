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


def _workspace_limits(sensor_config: dict[str, Any]) -> list[float]:
    workspace_cm = sensor_config.get("workspace_cm", {})
    half_x = float(workspace_cm.get("x", 40.0)) / 200.0
    half_y = float(workspace_cm.get("y", 50.0)) / 200.0
    max_z = max(float(workspace_cm.get("z", 20.0)) / 100.0, 0.2)
    return [-half_x, half_x, -half_y, half_y, 0.0, max_z]


class _SharedModularAdapterBase(AgentAdapter):
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
        self._instruction = ""
        self._pending_actions: list[Action] = []
        debug_dump_dir = str(config.get("debug_dump_dir", "")).strip()
        self._debug_dump_dir = Path(debug_dump_dir) if debug_dump_dir else None
        self._planner_config = dict(self.method_config.get("planner", {}))
        self._perception = SharedModularPerception(
            method_config=self.method_config,
            runtime_config=config,
            np_module=np,
            cv2_module=cv2,
        )

    def reset(self, task_spec: dict[str, Any]) -> None:
        self.task_spec = task_spec
        self._instruction = str(task_spec.get("instruction", "")).strip()
        self._pending_actions = []

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

    def step(self, obs: Observation) -> Action:
        if self._pending_actions:
            return self._pending_actions.pop(0)

        perception = self._perception.observe(
            task_spec=self.task_spec,
            instruction=self._instruction or obs.instruction,
            obs=obs,
        )
        payload = self._proposal_payload(obs, perception)
        translation = payload.get("best_translation")
        if translation is None:
            raise AdapterExecutionError(
                "The modular grasp pipeline did not produce a target translation for the shared planner.",
                failure_stage="planner_failure",
            )
        self._write_debug_payload(
            f"{self.name}_perception_",
            {
                "instruction": self._instruction or obs.instruction,
                "task_spec": self.task_spec,
                "perception": perception.debug,
                "proposal": payload,
            },
        )
        self._pending_actions = build_shared_pick_plan(
            obs,
            self._np,
            translation_cam=self._np.asarray(translation, dtype=self._np.float32),
            planner_config=self._planner_config,
            grasp_matrix_cam=(
                self._np.asarray(payload["best_grasp"], dtype=self._np.float32)
                if payload.get("best_grasp") is not None
                else None
            ),
        )
        if not self._pending_actions:
            raise AdapterExecutionError(
                "Shared modular planner failed to produce any executable actions.",
                failure_stage="planner_failure",
            )
        return self._pending_actions.pop(0)


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

        if len(grasp_group) == 0:
            raise AdapterExecutionError(
                "AnyGrasp returned zero grasp proposals for the current masked observation.",
                failure_stage="grasp_proposal",
            )

        if hasattr(grasp_group, "nms"):
            grasp_group = grasp_group.nms().sort_by_score()
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
                "Contact-GraspNet requires a prepared legacy TensorFlow 2.2 runtime. "
                "Run python -m grasp_benchmark.prepare_cgn --node <host> --bootstrap-legacy-env first.",
                failure_stage="legacy_runtime",
            )
        self._miniforge_root = Path(miniforge_root)
        if not self._miniforge_root.exists():
            raise AdapterExecutionError(
                f"Missing Miniforge root required for conda-run bridge: {self._miniforge_root}",
                failure_stage="legacy_runtime",
            )
        self._forward_passes = int(config.get("forward_passes", 1))
        self._z_min = float(config.get("z_min", 0.2))
        self._z_max = float(config.get("z_max", 1.1))
        execution_mode = str(config.get("execution_mode", ""))
        is_formal_track_a = execution_mode == "shared_track_a_sim" or execution_mode.startswith("track_a_diag_")
        stride_key = "formal_downsample_stride" if is_formal_track_a else "smoke_downsample_stride"
        self._downsample_stride = max(int(self.method_config.get(stride_key, 1)), 1)
        self._gpu_id = str(config.get("gpu_id", "0") or "0")

    def _proposal_payload(self, obs: Observation, perception: PerceptionResult) -> dict[str, Any]:
        if os.name == "nt":
            raise AdapterExecutionError(
                "Contact-GraspNet legacy-env execution is only supported on the Linux cluster nodes.",
                failure_stage="legacy_runtime",
            )

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

        with tempfile.TemporaryDirectory(prefix="gb-cgn-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.npz"
            output_path = tmp_path / "output.json"
            self._np.savez(input_path, depth=depth, K=K, rgb=rgb, segmap=segmap)
            runner_cmd = [
                "bash",
                "-lc",
                (
                    'env -u CC -u CXX -u CUDAHOSTCXX '
                    f'PYTHONPATH="{_project_root(self.runtime_config) / "src"}" '
                    'LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libstdc++.so.6" '
                    f'LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu${{LD_LIBRARY_PATH:+:${{LD_LIBRARY_PATH}}}}" '
                    f'CUDA_VISIBLE_DEVICES={self._gpu_id} "{self._legacy_env_prefix / "bin" / "python"}" -m grasp_benchmark.runners.contact_graspnet '
                    f'--input "{input_path}" '
                    f'--output "{output_path}" '
                    f'--upstream-root "{self._upstream_root}" '
                    f'--checkpoint-dir "{self._checkpoint_dir}" '
                    f'--forward-passes {self._forward_passes} '
                    f'--z-min {self._z_min} '
                    f'--z-max {self._z_max} '
                    f'--cuda-visible-devices {self._gpu_id}'
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
            completed = subprocess.run(
                runner_cmd,
                capture_output=True,
                text=True,
                env=child_env,
                timeout=max(int(self.runtime_config.get("timeout_ms", 10000)), 300000),
                check=False,
            )
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
            if not payload.get("ok"):
                self._write_debug_payload("cgn_payload_", payload)
                raise AdapterExecutionError(
                    str(payload.get("failure_reason", "Contact-GraspNet produced no valid grasp.")),
                    failure_stage=str(payload.get("failure_stage", "grasp_proposal")),
                )
            return payload

    def close(self) -> None:
        return None
