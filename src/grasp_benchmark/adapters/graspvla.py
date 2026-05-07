from __future__ import annotations

from typing import Any

from grasp_benchmark.adapters.base import AgentAdapter
from grasp_benchmark.types import Action, Observation


class GraspVLAAdapter(AgentAdapter):
    adapter_kind = "graspvla"

    def setup(self, config: dict[str, Any]) -> None:
        try:
            import numpy as np
            import zmq
        except ImportError as exc:
            raise RuntimeError("GraspVLAAdapter requires numpy and pyzmq in the active environment.") from exc

        self.runtime_config = config
        self._np = np
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
        self._view_mode = str(config.get("graspvla_view_mode", "dual")).strip().lower()

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
        front_rgb = obs.rgb_front
        side_rgb = obs.rgb_side
        if self._view_mode == "front_only_duplicate":
            side_rgb = obs.rgb_front
        elif self._view_mode == "front_only_blank":
            side_rgb = self._np.zeros_like(obs.rgb_front)
        elif self._view_mode == "side_only_duplicate":
            front_rgb = obs.rgb_side
        elif self._view_mode == "side_only_blank":
            front_rgb = self._np.zeros_like(obs.rgb_side)
        request = {
            "front_view_image": [front_rgb],
            "side_view_image": [side_rgb],
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
