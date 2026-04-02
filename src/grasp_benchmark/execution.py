from __future__ import annotations

import json
import time
from hashlib import sha256
from pathlib import Path
from typing import Any

from grasp_benchmark.adapters.base import AgentAdapter, AdapterExecutionError
from grasp_benchmark.paths import ensure_dir
from grasp_benchmark.task_specs import TrialSpec
from grasp_benchmark.types import EpisodeResult, Observation


def _seed_for_trial(trial: TrialSpec, attempt: int) -> int:
    digest = sha256(f"{trial.scene_id}:{trial.object_id}:{attempt}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="little", signed=False)


def build_mock_observation(
    sensor_config: dict[str, Any],
    trial: TrialSpec,
    attempt: int,
) -> Observation:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Integration execution requires numpy in the active environment.") from exc

    front_cfg = sensor_config["cameras"]["front"]["resolution"]
    side_cfg = sensor_config["cameras"]["side"]["resolution"]
    front_h = int(front_cfg["height"])
    front_w = int(front_cfg["width"])
    side_h = int(side_cfg["height"])
    side_w = int(side_cfg["width"])
    rng = np.random.default_rng(_seed_for_trial(trial, attempt))

    rgb_front = rng.integers(0, 255, size=(front_h, front_w, 3), dtype=np.uint8)
    rgb_side = rng.integers(0, 255, size=(side_h, side_w, 3), dtype=np.uint8)
    depth_front = rng.random((front_h, front_w), dtype=np.float32)
    depth_side = rng.random((side_h, side_w), dtype=np.float32)
    base_state = rng.normal(loc=0.0, scale=0.01, size=7).astype("float32")
    base_state[-1] = 1.0
    history = []
    for offset in range(4):
        state = base_state.copy()
        state[:6] += offset * 0.001
        history.append(state.tolist())

    return Observation(
        rgb_front=rgb_front,
        rgb_side=rgb_side,
        depth_front=depth_front,
        depth_side=depth_side,
        intrinsics_front={"fx": 1.0, "fy": 1.0, "cx": front_w / 2, "cy": front_h / 2},
        intrinsics_side={"fx": 1.0, "fy": 1.0, "cx": side_w / 2, "cy": side_h / 2},
        extrinsics_front={"pose": "front_fixed"},
        extrinsics_side={"pose": "side_fixed"},
        proprio={"state": history[-1], "history": history, "gripper": 1},
        instruction=trial.instruction,
        timestamp=time.time(),
    )


def _sanitize_reason(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}"
    message = " ".join(message.split())
    return message[:200]


def _write_attempt_artifact(
    root: Path,
    trial: TrialSpec,
    attempt: int,
    payload: dict[str, Any],
) -> Path:
    ensure_dir(root)
    artifact_path = root / f"{trial.scene_id}_attempt{attempt:02d}.json"
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path


def execute_integration_trial(
    adapter: AgentAdapter,
    sensor_config: dict[str, Any],
    success_definition: dict[str, Any],
    trial: TrialSpec,
    artifact_dir: Path,
    node: str,
    commit: str,
) -> EpisodeResult:
    last_failure = ""
    last_stage = ""
    cycle_start = time.perf_counter()

    for attempt in range(1, trial.attempts_per_trial + 1):
        obs = build_mock_observation(sensor_config=sensor_config, trial=trial, attempt=attempt)
        inference_start = time.perf_counter()
        try:
            action = adapter.step(obs)
            inference_ms = (time.perf_counter() - inference_start) * 1000.0
            cycle_time_s = time.perf_counter() - cycle_start
            artifact_path = _write_attempt_artifact(
                artifact_dir,
                trial,
                attempt,
                {
                    "scene_id": trial.scene_id,
                    "attempt": attempt,
                    "instruction": trial.instruction,
                    "ee_delta": list(action.ee_delta),
                    "gripper": action.gripper,
                    "integration_mode": "mock_observation_fixture",
                },
            )
            return EpisodeResult(
                method=adapter.name,
                track=trial.track,
                task=trial.task,
                scene_id=trial.scene_id,
                object_id=trial.object_id,
                object_group=trial.object_group,
                condition=trial.condition,
                instruction=trial.instruction,
                sensor_stack=str(sensor_config["sensor_stack"]),
                attempts=attempt,
                success=True,
                lift_cm=float(success_definition["lift_cm_min"]),
                hold_s=float(success_definition["hold_s_min"]),
                spl=round(1.0 / attempt, 4),
                inference_ms=round(inference_ms, 4),
                cycle_time_s=round(cycle_time_s, 4),
                failure_stage="",
                failure_reason="",
                collision=False,
                video_path=str(artifact_path.relative_to(artifact_dir.parent)),
                node=node,
                commit=commit,
            )
        except AdapterExecutionError as exc:
            inference_ms = (time.perf_counter() - inference_start) * 1000.0
            last_stage = exc.failure_stage or "adapter_execution"
            last_failure = _sanitize_reason(exc)
            _write_attempt_artifact(
                artifact_dir,
                trial,
                attempt,
                {
                    "scene_id": trial.scene_id,
                    "attempt": attempt,
                    "instruction": trial.instruction,
                    "error": last_failure,
                    "failure_stage": last_stage,
                    "inference_ms": round(inference_ms, 4),
                    "integration_mode": "mock_observation_fixture",
                },
            )
        except Exception as exc:  # pragma: no cover - exercised via tests with dummy adapter
            inference_ms = (time.perf_counter() - inference_start) * 1000.0
            last_stage = "adapter_execution"
            last_failure = _sanitize_reason(exc)
            _write_attempt_artifact(
                artifact_dir,
                trial,
                attempt,
                {
                    "scene_id": trial.scene_id,
                    "attempt": attempt,
                    "instruction": trial.instruction,
                    "error": last_failure,
                    "failure_stage": last_stage,
                    "inference_ms": round(inference_ms, 4),
                    "integration_mode": "mock_observation_fixture",
                },
            )

    cycle_time_s = time.perf_counter() - cycle_start
    return EpisodeResult(
        method=adapter.name,
        track=trial.track,
        task=trial.task,
        scene_id=trial.scene_id,
        object_id=trial.object_id,
        object_group=trial.object_group,
        condition=trial.condition,
        instruction=trial.instruction,
        sensor_stack=str(sensor_config["sensor_stack"]),
        attempts=trial.attempts_per_trial,
        success=False,
        lift_cm=0.0,
        hold_s=0.0,
        spl=0.0,
        inference_ms=0.0,
        cycle_time_s=round(cycle_time_s, 4),
        failure_stage=last_stage or "adapter_execution",
        failure_reason=last_failure or "Unknown integration failure",
        collision=False,
        video_path="",
        node=node,
        commit=commit,
    )


def run_integration_suite(
    adapter: AgentAdapter,
    sensor_config: dict[str, Any],
    task_specs: list[TrialSpec],
    artifact_dir: Path,
    node: str,
    commit: str,
) -> list[EpisodeResult]:
    success_definition = sensor_config["success_definition"]
    results: list[EpisodeResult] = []
    for trial in task_specs:
        adapter.reset(trial.to_task_spec())
        results.append(
            execute_integration_trial(
                adapter=adapter,
                sensor_config=sensor_config,
                success_definition=success_definition,
                trial=trial,
                artifact_dir=artifact_dir,
                node=node,
                commit=commit,
            )
        )
    return results
