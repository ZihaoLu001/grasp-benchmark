from __future__ import annotations

import argparse
import faulthandler
import json
import os
import traceback
import signal
import socket
from dataclasses import replace
from pathlib import Path

from grasp_benchmark.adapters import build_adapter
from grasp_benchmark.adapters.base import AdapterExecutionError
from grasp_benchmark.adapters.modular_components import method_tier as resolve_method_tier
from grasp_benchmark.config import load_cluster_config, load_named_config
from grasp_benchmark.execution import run_integration_suite
from grasp_benchmark.paths import PROJECT_ROOT, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.runners.graspvla_official_aligned import (
    OfficialAlignmentVariant,
    parse_seed_csv,
    run_official_aligned_suite,
)
from grasp_benchmark.runners.graspvla_track_a_sim import run_shared_track_a_suite
from grasp_benchmark.task_specs import expand_task_set
from grasp_benchmark.types import EpisodeResult, append_episode_results_csv


_FAULT_HANDLER_STREAM = None


def _maybe_enable_faulthandler() -> None:
    global _FAULT_HANDLER_STREAM
    target = os.environ.get("GB_FAULTHANDLER_PATH", "").strip()
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    _FAULT_HANDLER_STREAM = path.open("a", encoding="utf-8")
    faulthandler.enable(file=_FAULT_HANDLER_STREAM, all_threads=True)
    try:
        faulthandler.register(signal.SIGUSR1, file=_FAULT_HANDLER_STREAM, all_threads=True, chain=False)
    except Exception:
        pass


def _maybe_enable_numpy_compat() -> None:
    try:
        import numpy as np
    except Exception:
        return
    for alias, target in (("float", float), ("int", int), ("bool", bool)):
        if not hasattr(np, alias):
            setattr(np, alias, target)


def _runtime_config(method_config: dict, cluster_config: dict) -> dict:
    runtime = {
        "timeout_ms": 10000,
        "project_root": str(PROJECT_ROOT),
        "miniforge_root": cluster_config["miniforge_root"],
        "conda_envs_dir": cluster_config["conda_envs_dir"],
        "remote_root": cluster_config["remote_root"],
        "cuda_home": cluster_config.get("cuda_home", ""),
    }
    server = method_config.get("server")
    if isinstance(server, dict):
        runtime.update(server)
    return runtime


def _task_runtime_overrides(method_config: dict, task_set: str) -> dict:
    overrides = method_config.get("task_runtime_overrides", {})
    if not isinstance(overrides, dict):
        return {}
    selected = overrides.get(task_set, {})
    return dict(selected) if isinstance(selected, dict) else {}


def _shard_task_specs(task_specs: list, shard_index: int, shard_count: int) -> list:
    if shard_count <= 1:
        return list(task_specs)
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError(f"Invalid shard index {shard_index} for shard count {shard_count}.")
    return [task_spec for index, task_spec in enumerate(task_specs) if index % shard_count == shard_index]


def _filter_scene_ids(task_specs: list, scene_ids: str) -> list:
    if not scene_ids.strip():
        return list(task_specs)
    allowed = {item.strip() for item in scene_ids.split(",") if item.strip()}
    return [task_spec for task_spec in task_specs if task_spec.scene_id in allowed]


def _is_shared_track_a_execution_mode(execution_mode: str) -> bool:
    return execution_mode == "shared_track_a_sim" or execution_mode.startswith("track_a_diag_")


def _is_official_aligned_execution_mode(execution_mode: str) -> bool:
    return execution_mode == "official_aligned_sim"


def _shared_protocol(sensor_config: dict) -> dict:
    return {
        "track": sensor_config.get("track", ""),
        "sensor_stack": sensor_config.get("sensor_stack", ""),
        "control_mode": sensor_config.get("control_mode", ""),
        "workspace_cm": dict(sensor_config.get("workspace_cm", {})),
        "success_definition": dict(sensor_config.get("success_definition", {})),
        "attempts_per_trial": int(sensor_config.get("attempts_per_trial", 0)),
        "embodiment": dict(sensor_config.get("embodiment", {})),
        "scene_edit_policy": str(sensor_config.get("scene_edit_policy", "")),
        "logging_contract": str(sensor_config.get("logging_contract", "")),
    }


def _sanitize_reason(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}"
    return " ".join(message.split())[:4000]


def _setup_failure_results(
    *,
    adapter_name: str,
    method_tier: str = "unknown_method_tier",
    sensor_stack: str,
    task_specs: list,
    node: str,
    commit: str,
    execution_mode: str,
    exc: BaseException,
    parent_run_id: str = "",
    shard_id: str = "",
    gpu_id: str = "",
) -> list[EpisodeResult]:
    failure_stage = exc.failure_stage if isinstance(exc, AdapterExecutionError) else "adapter_setup"
    failure_reason = _sanitize_reason(exc)
    results: list[EpisodeResult] = []
    for trial in task_specs:
        results.append(
            EpisodeResult(
                method=adapter_name,
                method_tier=method_tier,
                track=trial.track,
                execution_mode=execution_mode,
                task=trial.task,
                scene_id=trial.scene_id,
                scene_recipe_id=trial.scene_recipe_id,
                object_id=trial.object_id,
                object_group=trial.object_group,
                condition=trial.condition,
                instruction=trial.instruction,
                instruction_variant_id=trial.instruction_variant_id,
                instruction_variant_family=trial.instruction_variant_family,
                shift_family=trial.shift_family,
                shift_severity=trial.shift_severity,
                sensor_stack=sensor_stack,
                attempts=0,
                success=False,
                lift_cm=0.0,
                hold_s=0.0,
                spl=0.0,
                inference_ms=0.0,
                cycle_time_s=0.0,
                failure_stage=failure_stage,
                failure_reason=failure_reason,
                collision=False,
                video_path="",
                node=node,
                commit=commit,
                replicate_index=trial.replicate_index,
                seed=trial.seed,
                parent_run_id=parent_run_id,
                shard_id=shard_id,
                gpu_id=gpu_id,
            )
        )
    return results


def _official_setup_failure_results(
    *,
    adapter_name: str,
    method_tier: str,
    sensor_stack: str,
    benchmarks: list[str],
    tasks_per_benchmark: int,
    seeds: list[int],
    playground_seed_list: list[int],
    run_playground_sanity: bool,
    node: str,
    commit: str,
    execution_mode: str,
    exc: BaseException,
    parent_run_id: str = "",
    shard_id: str = "",
    gpu_id: str = "",
) -> list[EpisodeResult]:
    failure_stage = exc.failure_stage if isinstance(exc, AdapterExecutionError) else "adapter_setup"
    failure_reason = _sanitize_reason(exc)
    results: list[EpisodeResult] = []
    for benchmark in benchmarks:
        for task_index in range(max(int(tasks_per_benchmark), 0)):
            for seed in seeds:
                results.append(
                    EpisodeResult(
                        method=adapter_name,
                        method_tier=method_tier,
                        track="official_alignment",
                        execution_mode=execution_mode,
                        task=benchmark,
                        scene_id=f"{benchmark}__setup_failure_task{task_index:03d}__seed{int(seed)}",
                        scene_recipe_id=f"{benchmark}__setup_failure_task{task_index:03d}",
                        object_id="official_alignment_setup",
                        object_group="official_alignment_setup",
                        condition="setup_failure",
                        instruction="",
                        sensor_stack=sensor_stack,
                        attempts=0,
                        success=False,
                        lift_cm=0.0,
                        hold_s=0.0,
                        spl=0.0,
                        inference_ms=0.0,
                        cycle_time_s=0.0,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                        collision=False,
                        video_path="",
                        node=node,
                        commit=commit,
                        replicate_index=task_index + 1,
                        seed=int(seed),
                        parent_run_id=parent_run_id,
                        shard_id=shard_id,
                        gpu_id=gpu_id,
                    )
                )
    if run_playground_sanity:
        for seed in playground_seed_list:
            results.append(
                EpisodeResult(
                    method=adapter_name,
                    method_tier=method_tier,
                    track="official_alignment",
                    execution_mode=execution_mode,
                    task="playground_sanity",
                    scene_id=f"playground_sanity__setup_failure__seed{int(seed)}",
                    scene_recipe_id="playground_sanity__setup_failure",
                    object_id="official_alignment_setup",
                    object_group="official_alignment_setup",
                    condition="setup_failure",
                    instruction="",
                    sensor_stack=sensor_stack,
                    attempts=0,
                    success=False,
                    lift_cm=0.0,
                    hold_s=0.0,
                    spl=0.0,
                    inference_ms=0.0,
                    cycle_time_s=0.0,
                    failure_stage=failure_stage,
                    failure_reason=failure_reason,
                    collision=False,
                    video_path="",
                    node=node,
                    commit=commit,
                    replicate_index=1,
                    seed=int(seed),
                    parent_run_id=parent_run_id,
                    shard_id=shard_id,
                    gpu_id=gpu_id,
                )
            )
    return results


def main() -> None:
    _maybe_enable_faulthandler()
    _maybe_enable_numpy_compat()
    parser = argparse.ArgumentParser(description="Remote benchmark worker scaffold.")
    parser.add_argument(
        "--cluster-config",
        default="",
        help="Cluster config name under configs/cluster. Defaults to GRASP_BENCHMARK_CLUSTER_CONFIG or default.",
    )
    parser.add_argument("--method", required=True)
    parser.add_argument("--task-set", required=True)
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--max-trials", type=int, default=0, help="Optional cap on expanded trial count.")
    parser.add_argument("--execution-mode", default="integration_fixture")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--gpu-id", default="")
    parser.add_argument("--parent-run-id", default="")
    parser.add_argument("--scene-ids", default="")
    parser.add_argument("--robot-config-override", default="")
    parser.add_argument("--lift-threshold-cm", type=float, default=-1.0)
    parser.add_argument("--hold-steps", type=int, default=-1)
    parser.add_argument("--attempt-budget-override", type=int, default=-1)
    parser.add_argument("--trace-steps", action="store_true")
    parser.add_argument("--graspvla-view-mode", default="", help="Optional GraspVLA camera-ablation mode.")
    parser.add_argument("--camera-jitter-mode", default="", help="Optional observation-space camera jitter mode.")
    parser.add_argument("--segmentation-mode", default="", help="Optional modular perception mode, e.g. oracle_gt.")
    parser.add_argument("--oracle-grasp-mode", default="", help="Optional proposal override mode, e.g. topdown_centroid.")
    parser.add_argument(
        "--native-multiview-fusion",
        action="store_true",
        default=None,
        help="Enable CGN native multi-view fused-depth mode.",
    )
    parser.add_argument("--official-benchmarks", default="libero_object,libero_10,libero_goal")
    parser.add_argument("--official-task-count", type=int, default=2)
    parser.add_argument("--official-seeds", default="0,1,2,3,4,5,6,7,8,9")
    parser.add_argument("--official-playground-seeds", default="0,1,2,3,4")
    parser.add_argument("--official-variant-name", default="")
    parser.add_argument("--official-agent-mode", default="wrapper")
    parser.add_argument("--official-robot-profile", default="extended_finger")
    parser.add_argument("--official-success-mode", default="env_done")
    parser.add_argument("--official-scene-edit-policy", default="official")
    parser.add_argument("--official-run-playground-sanity", action="store_true")
    args = parser.parse_args()

    cluster_config = load_cluster_config(args.cluster_config)
    method_config = load_named_config("methods", args.method)
    sensor_config = load_named_config("sensors", args.sensor_config)
    task_config = load_named_config("tasks", args.task_set)
    adapter = build_adapter(args.method, method_config, sensor_config)

    output_dir = Path(args.output_dir)
    ensure_dir(output_dir)
    payload = {
        "method": args.method,
        "benchmark_method_tier": resolve_method_tier(method_config),
        "task_set": args.task_set,
        "sensor_config": args.sensor_config,
        "execution_mode": args.execution_mode,
        "node": socket.gethostname(),
        "project_root": str(PROJECT_ROOT),
        "commit": resolve_commit(PROJECT_ROOT),
        "required_upstreams": adapter.required_upstreams(),
        "missing_upstreams": adapter.validate_project_root(PROJECT_ROOT),
        "task_groups": task_config.get("task_groups", []),
        "adapter_input_policy": adapter.input_policy(),
        "shared_protocol": _shared_protocol(sensor_config),
        "parent_run_id": args.parent_run_id,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "shard_id": f"shard_{args.shard_index:03d}",
        "gpu_id": args.gpu_id,
        "scene_ids_filter": args.scene_ids,
        "robot_config_override": args.robot_config_override,
        "lift_threshold_cm_override": args.lift_threshold_cm,
        "hold_steps_override": args.hold_steps,
        "attempt_budget_override": args.attempt_budget_override,
        "trace_steps": args.trace_steps,
        "graspvla_view_mode": args.graspvla_view_mode,
        "camera_jitter_mode": args.camera_jitter_mode,
        "segmentation_mode": args.segmentation_mode,
        "oracle_grasp_mode": args.oracle_grasp_mode,
        "native_multiview_fusion": args.native_multiview_fusion,
    }

    if args.smoke_only:
        (output_dir / "smoke.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return

    if _is_official_aligned_execution_mode(args.execution_mode):
        all_task_specs = []
        task_specs = []
        payload["expanded_trial_count"] = 0
        payload["trial_count"] = 0
        payload["task_specs"] = []
        payload["official_alignment"] = {
            "benchmarks": [item.strip() for item in args.official_benchmarks.split(",") if item.strip()],
            "tasks_per_benchmark": args.official_task_count,
            "seed_list": parse_seed_csv(args.official_seeds),
            "playground_seed_list": parse_seed_csv(args.official_playground_seeds),
            "variant": {
                "name": args.official_variant_name or "official_alignment_variant",
                "agent_mode": args.official_agent_mode,
                "robot_profile": args.official_robot_profile,
                "success_mode": args.official_success_mode,
                "scene_edit_policy": args.official_scene_edit_policy,
                "run_playground_sanity": args.official_run_playground_sanity,
                "lift_threshold_cm_override": args.lift_threshold_cm if args.lift_threshold_cm > 0 else None,
                "hold_steps_override": args.hold_steps if args.hold_steps > 0 else None,
            },
        }
    else:
        max_trials = args.max_trials or None
        all_task_specs = expand_task_set(task_config, max_trials=max_trials)
        if args.attempt_budget_override > 0:
            all_task_specs = [
                replace(task_spec, attempts_per_trial=int(args.attempt_budget_override)) for task_spec in all_task_specs
            ]
        task_specs = _shard_task_specs(all_task_specs, args.shard_index, args.shard_count)
        task_specs = _filter_scene_ids(task_specs, args.scene_ids)
        payload["expanded_trial_count"] = len(all_task_specs)
        payload["trial_count"] = len(task_specs)
        payload["task_specs"] = [task_spec.to_task_spec() for task_spec in task_specs]
    (output_dir / "run_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    benchmark_method_tier = resolve_method_tier(method_config)
    try:
        runtime_config = _runtime_config(method_config, cluster_config)
        runtime_config.update(_task_runtime_overrides(method_config, args.task_set))
        runtime_config["gpu_id"] = args.gpu_id
        runtime_config["execution_mode"] = args.execution_mode
        runtime_config["smoke_only"] = args.smoke_only
        runtime_config["debug_dump_dir"] = str(output_dir / "debug")
        runtime_config["task_set"] = args.task_set
        if args.graspvla_view_mode:
            runtime_config["graspvla_view_mode"] = args.graspvla_view_mode
        if args.camera_jitter_mode:
            runtime_config["camera_jitter_mode"] = args.camera_jitter_mode
        if args.segmentation_mode:
            runtime_config["segmentation_mode"] = args.segmentation_mode
        if args.oracle_grasp_mode:
            runtime_config["oracle_grasp_mode"] = args.oracle_grasp_mode
        if args.native_multiview_fusion is not None:
            runtime_config["native_multiview_fusion"] = args.native_multiview_fusion
        if _is_official_aligned_execution_mode(args.execution_mode):
            variant = OfficialAlignmentVariant(
                name=args.official_variant_name or "official_alignment_variant",
                execution_mode=args.execution_mode,
                agent_mode=args.official_agent_mode,
                robot_profile=args.official_robot_profile,
                success_mode=args.official_success_mode,
                scene_edit_policy=args.official_scene_edit_policy,
                run_playground_sanity=args.official_run_playground_sanity,
                lift_threshold_cm_override=args.lift_threshold_cm if args.lift_threshold_cm > 0 else None,
                hold_steps_override=args.hold_steps if args.hold_steps > 0 else None,
            )
            results, official_metadata = run_official_aligned_suite(
                variant=variant,
                artifact_dir=output_dir,
                runtime_config=runtime_config,
                node=payload["node"],
                commit=payload["commit"],
                parent_run_id=args.parent_run_id,
                benchmarks=[item.strip() for item in args.official_benchmarks.split(",") if item.strip()],
                tasks_per_benchmark=args.official_task_count,
                seeds=parse_seed_csv(args.official_seeds),
                playground_seeds=parse_seed_csv(args.official_playground_seeds),
                trace_steps=args.trace_steps,
            )
            payload["official_alignment"] = official_metadata
            payload["trial_count"] = len(results)
            (output_dir / "run_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        elif _is_shared_track_a_execution_mode(args.execution_mode):
            results, scene_metadata = run_shared_track_a_suite(
                method_name=args.method,
                method_config=method_config,
                task_config=task_config,
                sensor_config=sensor_config,
                task_specs=task_specs,
                artifact_dir=output_dir,
                node=payload["node"],
                commit=payload["commit"],
                runtime_config=runtime_config,
                execution_mode=args.execution_mode,
                parent_run_id=args.parent_run_id,
                shard_id=payload["shard_id"],
                gpu_id=args.gpu_id,
                robot_config_override=args.robot_config_override,
                lift_threshold_cm_override=args.lift_threshold_cm if args.lift_threshold_cm > 0 else None,
                hold_steps_override=args.hold_steps if args.hold_steps > 0 else None,
                trace_steps=args.trace_steps,
            )
            payload.update(scene_metadata)
            (output_dir / "run_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        else:
            adapter.setup(runtime_config)
            results = run_integration_suite(
                adapter=adapter,
                method_tier=benchmark_method_tier,
                sensor_config=sensor_config,
                task_specs=task_specs,
                artifact_dir=output_dir / "episodes",
                node=payload["node"],
                commit=payload["commit"],
                execution_mode=args.execution_mode,
            )
    except Exception as exc:
        payload["setup_error"] = _sanitize_reason(exc)
        payload["setup_traceback"] = traceback.format_exc(limit=50)
        (output_dir / "run_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if _is_official_aligned_execution_mode(args.execution_mode) and not task_specs:
            results = _official_setup_failure_results(
                adapter_name=adapter.name,
                method_tier=benchmark_method_tier,
                sensor_stack=str(sensor_config["sensor_stack"]),
                benchmarks=[item.strip() for item in args.official_benchmarks.split(",") if item.strip()],
                tasks_per_benchmark=args.official_task_count,
                seeds=parse_seed_csv(args.official_seeds),
                playground_seed_list=parse_seed_csv(args.official_playground_seeds),
                run_playground_sanity=args.official_run_playground_sanity,
                node=payload["node"],
                commit=payload["commit"],
                execution_mode=args.execution_mode,
                exc=exc,
                parent_run_id=args.parent_run_id,
                shard_id=payload["shard_id"],
                gpu_id=args.gpu_id,
            )
        else:
            results = _setup_failure_results(
                adapter_name=adapter.name,
                method_tier=benchmark_method_tier,
                sensor_stack=str(sensor_config["sensor_stack"]),
                task_specs=task_specs,
                node=payload["node"],
                commit=payload["commit"],
                execution_mode=args.execution_mode,
                exc=exc,
                parent_run_id=args.parent_run_id,
                shard_id=payload["shard_id"],
                gpu_id=args.gpu_id,
            )
    finally:
        adapter.close()

    append_episode_results_csv(output_dir / "results.csv", results)
    summary = {
        "method": args.method,
        "task_set": args.task_set,
        "execution_mode": args.execution_mode,
        "trial_count": len(results),
        "successes": sum(1 for result in results if result.success),
        "failures": sum(1 for result in results if not result.success),
        "results_path": str(output_dir / "results.csv"),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
