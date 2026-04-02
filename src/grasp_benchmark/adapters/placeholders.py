from __future__ import annotations

from typing import Any

from grasp_benchmark.adapters.base import AgentAdapter
from grasp_benchmark.types import Action, Observation


class _PlaceholderAdapter(AgentAdapter):
    adapter_kind = "placeholder"

    def setup(self, config: dict[str, Any]) -> None:
        self.runtime_config = config

    def reset(self, task_spec: dict[str, Any]) -> None:
        self.task_spec = task_spec

    def step(self, obs: Observation) -> Action:
        raise NotImplementedError(
            f"{self.name} adapter execution is not implemented yet. "
            "Use this scaffold to validate installs, dispatch jobs, and aggregate results."
        )

    def close(self) -> None:
        return None


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


class AnyGraspAdapter(_PlaceholderAdapter):
    adapter_kind = "anygrasp"


class ContactGraspNetAdapter(_PlaceholderAdapter):
    adapter_kind = "cgn"
