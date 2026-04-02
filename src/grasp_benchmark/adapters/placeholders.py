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


class GraspVLAAdapter(_PlaceholderAdapter):
    adapter_kind = "graspvla"


class AnyGraspAdapter(_PlaceholderAdapter):
    adapter_kind = "anygrasp"


class ContactGraspNetAdapter(_PlaceholderAdapter):
    adapter_kind = "cgn"

