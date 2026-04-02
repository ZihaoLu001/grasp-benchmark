from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import UPSTREAMS_DIR


@dataclass(frozen=True, slots=True)
class UpstreamSpec:
    name: str
    url: str
    description: str

    @property
    def local_dir(self) -> Path:
        return UPSTREAMS_DIR / self.name


UPSTREAMS: tuple[UpstreamSpec, ...] = (
    UpstreamSpec(
        name="GraspVLA",
        url="https://github.com/PKU-EPIC/GraspVLA.git",
        description="Official GraspVLA model server and code.",
    ),
    UpstreamSpec(
        name="GraspVLA-playground",
        url="https://github.com/MiYanDoris/GraspVLA-playground.git",
        description="Official simulation playground and LIBERO evaluation wrapper.",
    ),
    UpstreamSpec(
        name="GraspVLA-real-world-controller",
        url="https://github.com/MiYanDoris/GraspVLA-real-world-controller.git",
        description="Official Franka real-world controller.",
    ),
    UpstreamSpec(
        name="anygrasp_sdk",
        url="https://github.com/graspnet/anygrasp_sdk.git",
        description="Official AnyGrasp SDK.",
    ),
    UpstreamSpec(
        name="contact_graspnet",
        url="https://github.com/NVlabs/contact_graspnet.git",
        description="Official Contact-GraspNet repository.",
    ),
    UpstreamSpec(
        name="GroundingDINO",
        url="https://github.com/IDEA-Research/GroundingDINO.git",
        description="Official Grounding DINO repository.",
    ),
    UpstreamSpec(
        name="curobo",
        url="https://github.com/NVlabs/curobo.git",
        description="Motion planner dependency used by the GraspVLA playground stack.",
    ),
)

UPSTREAMS_BY_NAME = {spec.name: spec for spec in UPSTREAMS}


def load_method_config(method_name: str) -> dict:
    return load_named_config("methods", method_name)

