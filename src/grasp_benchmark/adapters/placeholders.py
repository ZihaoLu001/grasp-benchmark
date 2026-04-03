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
from grasp_benchmark.paths import PROJECT_ROOT
from grasp_benchmark.types import Action, Observation


def _project_root(runtime_config: dict[str, Any]) -> Path:
    return Path(str(runtime_config.get("project_root", PROJECT_ROOT)))


def _require_path(path: Path, *, failure_stage: str, description: str) -> Path:
    if not path.exists():
        raise AdapterExecutionError(f"Missing {description}: {path}", failure_stage=failure_stage)
    return path


def _point_cloud_from_depth(obs: Observation, np_module: Any) -> tuple[Any, Any]:
    depth = np_module.asarray(obs.depth_front, dtype=np_module.float32)
    colors = np_module.asarray(obs.rgb_front, dtype=np_module.float32)
    if depth.ndim != 2:
        raise AdapterExecutionError("Front depth frame must be a 2D array.", failure_stage="observation")
    if colors.ndim != 3 or colors.shape[:2] != depth.shape:
        raise AdapterExecutionError(
            "Front RGB frame must match the front depth resolution.",
            failure_stage="observation",
        )

    fx = float(obs.intrinsics_front.get("fx", 0.0))
    fy = float(obs.intrinsics_front.get("fy", 0.0))
    cx = float(obs.intrinsics_front.get("cx", depth.shape[1] / 2))
    cy = float(obs.intrinsics_front.get("cy", depth.shape[0] / 2))
    if fx <= 0 or fy <= 0:
        raise AdapterExecutionError(
            "Camera intrinsics must include positive fx/fy values.",
            failure_stage="observation",
        )

    ymap, xmap = np_module.indices(depth.shape)
    z = depth
    mask = np_module.isfinite(z) & (z > 1e-6)
    if not np_module.any(mask):
        raise AdapterExecutionError("No valid depth pixels were available.", failure_stage="observation")

    x = (xmap - cx) / fx * z
    y = (ymap - cy) / fy * z
    points = np_module.stack([x, y, z], axis=-1)[mask].astype(np_module.float32)
    rgb = colors[mask]
    if rgb.max(initial=0.0) > 1.0:
        rgb = rgb / 255.0
    return points, rgb.astype(np_module.float32)


def _workspace_limits(sensor_config: dict[str, Any]) -> list[float]:
    workspace_cm = sensor_config.get("workspace_cm", {})
    half_x = float(workspace_cm.get("x", 40.0)) / 200.0
    half_y = float(workspace_cm.get("y", 50.0)) / 200.0
    max_z = max(float(workspace_cm.get("z", 20.0)) / 100.0, 0.2)
    return [-half_x, half_x, -half_y, half_y, 0.0, max_z]


def _conservative_delta_from_points(points: Any, np_module: Any) -> tuple[float, float, float, float, float, float]:
    center = np_module.mean(points, axis=0)
    dx = float(np_module.clip(center[0], -0.05, 0.05))
    dy = float(np_module.clip(center[1], -0.05, 0.05))
    dz = float(np_module.clip(center[2] - 0.2, -0.05, 0.05))
    return (dx, dy, dz, 0.0, 0.0, 0.0)


class GraspVLAAdapter(AgentAdapter):
    adapter_kind = "graspvla"

    def setup(self, config: dict[str, Any]) -> None:
        try:
            import numpy as np
            import zmq
        except ImportError as exc:
            raise RuntimeError(
                "GraspVLAAdapter requires numpy and pyzmq in the active environment."
            ) from exc

        self.runtime_config = config
        self._np = np
        self._zmq = zmq
        self._instruction = ""
        self._last_gripper = 1
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REQ)
        timeout_ms = int(config.get("timeout_ms", 10000))
        self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        self._socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
        host = str(config.get("host", self.method_config["server"]["host"]))
        port = int(config.get("port", self.method_config["server"]["port"]))
        self._socket.connect(f"tcp://{host}:{port}")

    def reset(self, task_spec: dict[str, Any]) -> None:
        self.task_spec = task_spec
        self._instruction = str(task_spec.get("instruction", "")).strip()

    def _proprio_history(self, obs: Observation) -> list[Any]:
        history = obs.proprio.get("history")
        if isinstance(history, list) and history:
            return history[-4:]

        state = obs.proprio.get("state")
        if state is None:
            pose = obs.proprio.get("ee_pose", [0.0] * 6)
            gripper = obs.proprio.get("gripper", self._last_gripper)
            state = [*pose[:6], gripper]

        state_list = list(state)
        if len(state_list) != 7:
            raise ValueError("GraspVLA proprio state must contain 7 values.")
        return [state_list[:] for _ in range(4)]

    def step(self, obs: Observation) -> Action:
        request = {
            "front_view_image": [obs.rgb_front],
            "side_view_image": [obs.rgb_side],
            "proprio_array": self._proprio_history(obs),
            "text": self._instruction or obs.instruction,
        }
        self._socket.send_pyobj(request)
        response = self._socket.recv_pyobj()
        if not isinstance(response, dict) or not response.get("result"):
            raise RuntimeError(f"Unexpected GraspVLA response: {response!r}")

        first_action = response["result"][0]
        delta = tuple(float(value) for value in first_action[:6])
        raw_gripper = float(first_action[6])
        if raw_gripper < 0:
            self._last_gripper = -1
        elif raw_gripper > 0:
            self._last_gripper = 1
        return Action(ee_delta=delta, gripper=self._last_gripper)

    def close(self) -> None:
        if getattr(self, "_socket", None) is not None:
            self._socket.close(linger=0)
        if getattr(self, "_context", None) is not None:
            self._context.term()


class AnyGraspAdapter(AgentAdapter):
    adapter_kind = "anygrasp"

    def setup(self, config: dict[str, Any]) -> None:
        try:
            import numpy as np
        except ImportError as exc:
            raise AdapterExecutionError(
                "AnyGrasp requires numpy in the active environment.",
                failure_stage="dependency_setup",
            ) from exc

        self.runtime_config = config
        self._np = np
        self._instruction = ""
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

    def reset(self, task_spec: dict[str, Any]) -> None:
        self.task_spec = task_spec
        self._instruction = str(task_spec.get("instruction", "")).strip()

    def step(self, obs: Observation) -> Action:
        points, colors = _point_cloud_from_depth(obs, self._np)
        try:
            grasp_group, _ = self._model.get_grasp(
                points,
                colors,
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
                "AnyGrasp returned zero grasp proposals for the current observation.",
                failure_stage="grasp_proposal",
            )
        return Action(ee_delta=_conservative_delta_from_points(points, self._np), gripper=1)

    def close(self) -> None:
        self._model = None


class ContactGraspNetAdapter(AgentAdapter):
    adapter_kind = "cgn"

    def setup(self, config: dict[str, Any]) -> None:
        try:
            import numpy as np
        except ImportError as exc:
            raise AdapterExecutionError(
                "Contact-GraspNet requires numpy in the active environment.",
                failure_stage="dependency_setup",
            ) from exc

        self.runtime_config = config
        self._np = np
        self._instruction = ""
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
        self._downsample_stride = max(int(self.method_config.get("smoke_downsample_stride", 1)), 1)
        self._gpu_id = str(config.get("gpu_id", "0") or "0")
        self._pending_actions: list[Action] = []

    def reset(self, task_spec: dict[str, Any]) -> None:
        self.task_spec = task_spec
        self._instruction = str(task_spec.get("instruction", "")).strip()
        self._pending_actions = []

    def _current_pose(self, obs: Observation) -> Any:
        state = obs.proprio.get("state")
        if state is None:
            history = obs.proprio.get("history")
            if isinstance(history, list) and history:
                state = history[-1]
        if state is None:
            raise AdapterExecutionError(
                "Contact-GraspNet requires proprio state for shared Track A execution.",
                failure_stage="observation",
            )
        state_array = self._np.asarray(state, dtype=self._np.float32)
        if state_array.shape[0] < 6:
            raise AdapterExecutionError(
                "Contact-GraspNet proprio state must include at least 6 end-effector values.",
                failure_stage="observation",
            )
        return state_array[:6]

    def _camera_target_in_world(self, obs: Observation, translation: Any) -> Any | None:
        matrix = obs.extrinsics_front.get("matrix")
        if matrix is None:
            return None
        extrinsic = self._np.asarray(matrix, dtype=self._np.float32)
        if extrinsic.shape != (4, 4):
            return None
        point = self._np.asarray([translation[0], translation[1], translation[2], 1.0], dtype=self._np.float32)
        return (extrinsic @ point)[:3]

    def _chunk_delta_actions(self, start_xyz: Any, goal_xyz: Any, *, gripper: int) -> list[Action]:
        delta = self._np.asarray(goal_xyz, dtype=self._np.float32) - self._np.asarray(start_xyz, dtype=self._np.float32)
        max_component = float(self._np.max(self._np.abs(delta)))
        chunk_size = 0.04
        chunks = max(1, int(self._np.ceil(max_component / chunk_size)))
        if chunks == 0:
            chunks = 1
        step_delta = delta / float(chunks)
        return [
            Action(
                ee_delta=(
                    float(step_delta[0]),
                    float(step_delta[1]),
                    float(step_delta[2]),
                    0.0,
                    0.0,
                    0.0,
                ),
                gripper=gripper,
            )
            for _ in range(chunks)
        ]

    def _build_plan(self, obs: Observation, payload: dict[str, Any]) -> list[Action]:
        current_pose = self._current_pose(obs)
        translation = self._np.asarray(payload.get("best_translation", [0.0, 0.0, 0.2]), dtype=self._np.float32)
        target_world = self._camera_target_in_world(obs, translation)
        if target_world is None:
            return [Action(ee_delta=_conservative_delta_from_points(translation.reshape(1, 3), self._np), gripper=1)]

        current_xyz = current_pose[:3]
        approach_xyz = target_world.copy()
        approach_xyz[2] = max(float(current_xyz[2]), float(target_world[2]) + 0.08)
        grasp_xyz = target_world.copy()
        grasp_xyz[2] = max(0.02, float(target_world[2]) + 0.015)
        lift_xyz = grasp_xyz.copy()
        lift_xyz[2] = grasp_xyz[2] + 0.18

        plan: list[Action] = []
        plan.extend(self._chunk_delta_actions(current_xyz, approach_xyz, gripper=1))
        plan.extend(self._chunk_delta_actions(approach_xyz, grasp_xyz, gripper=1))
        plan.append(Action(ee_delta=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), gripper=-1))
        plan.append(Action(ee_delta=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), gripper=-1))
        plan.extend(self._chunk_delta_actions(grasp_xyz, lift_xyz, gripper=-1))
        return plan

    def step(self, obs: Observation) -> Action:
        if os.name == "nt":
            raise AdapterExecutionError(
                "Contact-GraspNet legacy-env execution is only supported on the Linux cluster nodes.",
                failure_stage="legacy_runtime",
            )
        if self._pending_actions:
            return self._pending_actions.pop(0)

        depth = self._np.asarray(obs.depth_front, dtype=self._np.float32)
        rgb = self._np.asarray(obs.rgb_front, dtype=self._np.uint8)
        if self._downsample_stride > 1:
            depth = depth[:: self._downsample_stride, :: self._downsample_stride]
            rgb = rgb[:: self._downsample_stride, :: self._downsample_stride, :]
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
            self._np.savez(input_path, depth=depth, K=K, rgb=rgb)
            runner_cmd = [
                "bash",
                "-lc",
                (
                    f'source "{self._miniforge_root}/etc/profile.d/conda.sh" && '
                    f'PYTHONPATH="{_project_root(self.runtime_config) / "src"}" '
                    'LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libstdc++.so.6" '
                    f'LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu${{LD_LIBRARY_PATH:+:${{LD_LIBRARY_PATH}}}}" '
                    f'CUDA_VISIBLE_DEVICES={self._gpu_id} conda run -p "{self._legacy_env_prefix}" python -m grasp_benchmark.runners.contact_graspnet '
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
            completed = subprocess.run(
                runner_cmd,
                capture_output=True,
                text=True,
                timeout=max(int(self.runtime_config.get("timeout_ms", 10000)), 300000),
                check=False,
            )
            if completed.returncode != 0:
                stderr = (completed.stderr or completed.stdout).strip()
                raise AdapterExecutionError(
                    f"Contact-GraspNet runner failed: {stderr[:200]}",
                    failure_stage="legacy_runtime",
                )
            if not output_path.exists():
                raise AdapterExecutionError(
                    "Contact-GraspNet runner did not produce an output payload.",
                    failure_stage="adapter_bridge",
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            if not payload.get("ok"):
                raise AdapterExecutionError(
                    str(payload.get("failure_reason", "Contact-GraspNet produced no valid grasp.")),
                    failure_stage=str(payload.get("failure_stage", "grasp_proposal")),
                )
            self._pending_actions = self._build_plan(obs, payload)
            if not self._pending_actions:
                raise AdapterExecutionError(
                    "Contact-GraspNet planner failed to produce any executable actions.",
                    failure_stage="planner_failure",
                )
            return self._pending_actions.pop(0)

    def close(self) -> None:
        return None
