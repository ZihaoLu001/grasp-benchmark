from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class Observation:
    rgb_front: Any
    rgb_side: Any
    depth_front: Any = None
    depth_side: Any = None
    intrinsics_front: Mapping[str, Any] = field(default_factory=dict)
    intrinsics_side: Mapping[str, Any] = field(default_factory=dict)
    extrinsics_front: Mapping[str, Any] = field(default_factory=dict)
    extrinsics_side: Mapping[str, Any] = field(default_factory=dict)
    proprio: Mapping[str, Any] = field(default_factory=dict)
    instruction: str = ""
    timestamp: float | None = None


@dataclass(slots=True)
class Action:
    ee_delta: tuple[float, float, float, float, float, float]
    gripper: int

    def __post_init__(self) -> None:
        if len(self.ee_delta) != 6:
            raise ValueError("ee_delta must contain exactly 6 values.")
        if self.gripper not in (-1, 1):
            raise ValueError("gripper must be either -1 or 1.")


@dataclass(slots=True)
class EpisodeResult:
    method: str
    track: str
    execution_mode: str
    task: str
    scene_id: str
    object_id: str
    object_group: str
    condition: str
    instruction: str
    sensor_stack: str
    attempts: int
    success: bool
    lift_cm: float
    hold_s: float
    spl: float
    inference_ms: float
    cycle_time_s: float
    failure_stage: str
    failure_reason: str
    collision: bool
    video_path: str
    node: str
    commit: str

    @classmethod
    def fieldnames(cls) -> list[str]:
        return [
            "method",
            "track",
            "execution_mode",
            "task",
            "scene_id",
            "object_id",
            "object_group",
            "condition",
            "instruction",
            "sensor_stack",
            "attempts",
            "success",
            "lift_cm",
            "hold_s",
            "spl",
            "inference_ms",
            "cycle_time_s",
            "failure_stage",
            "failure_reason",
            "collision",
            "video_path",
            "node",
            "commit",
        ]

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["success"] = int(self.success)
        row["collision"] = int(self.collision)
        return row


def append_episode_results_csv(path: Path, results: list[EpisodeResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EpisodeResult.fieldnames())
        if write_header:
            writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())
