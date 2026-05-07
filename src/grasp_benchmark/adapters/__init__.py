from __future__ import annotations

from grasp_benchmark.adapters.base import AgentAdapter
from grasp_benchmark.adapters.graspvla import GraspVLAAdapter
from grasp_benchmark.adapters.modular_adapters import AnyGraspAdapter, ContactGraspNetAdapter


ADAPTERS: dict[str, type[AgentAdapter]] = {
    "graspvla": GraspVLAAdapter,
    "anygrasp": AnyGraspAdapter,
    "cgn": ContactGraspNetAdapter,
}


def build_adapter(method_name: str, method_config: dict, sensor_config: dict) -> AgentAdapter:
    try:
        adapter_cls = ADAPTERS[method_name]
    except KeyError as exc:
        raise KeyError(f"Unknown method adapter: {method_name}") from exc
    return adapter_cls(method_config=method_config, sensor_config=sensor_config)
