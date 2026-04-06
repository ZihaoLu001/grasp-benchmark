from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from grasp_benchmark.types import Action, Observation


class AdapterExecutionError(RuntimeError):
    def __init__(self, message: str, *, failure_stage: str = "adapter_execution") -> None:
        super().__init__(message)
        self.failure_stage = failure_stage


class AgentAdapter(ABC):
    def __init__(self, method_config: dict[str, Any], sensor_config: dict[str, Any]) -> None:
        self.method_config = method_config
        self.sensor_config = sensor_config

    @property
    def name(self) -> str:
        return str(self.method_config["name"])

    def required_upstreams(self) -> list[str]:
        return list(self.method_config.get("upstreams", []))

    def validate_project_root(self, project_root: Path) -> list[str]:
        missing = []
        for upstream in self.required_upstreams():
            path = project_root / "third_party" / "upstreams" / upstream
            if not path.exists():
                missing.append(str(path))
        return missing

    def input_policy(self) -> dict[str, Any]:
        policy = self.method_config.get("track_a_input_policy", {})
        return dict(policy) if isinstance(policy, dict) else {}

    def attempt_complete(self) -> bool:
        return False

    @abstractmethod
    def setup(self, config: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def reset(self, task_spec: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def step(self, obs: Observation) -> Action:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError
