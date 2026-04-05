from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from grasp_benchmark.paths import PROJECT_ROOT, ensure_dir
from grasp_benchmark.types import EpisodeResult
from grasp_benchmark.runners.graspvla_track_a_sim import (
    SharedFrankaKinematics,
    SharedTrackARemoteAgent,
    _camera_metadata,
    _refresh_obs,
    _step_trace_entry,
)


@dataclass(frozen=True, slots=True)
class OfficialLiberoTaskSpec:
    benchmark: str
    task_id: int
    task_name: str
    bddl_file: str
    problem_folder: str
    instruction: str
    obj_of_interest: tuple[str, ...]

    @property
    def episode_prefix(self) -> str:
        return f"{self.benchmark}__task{self.task_id:03d}"


@dataclass(frozen=True, slots=True)
class OfficialAlignmentVariant:
    name: str
    execution_mode: str
    agent_mode: str
    robot_profile: str
    success_mode: str
    scene_edit_policy: str
    run_playground_sanity: bool = False
    lift_threshold_cm_override: float | None = None
    hold_steps_override: int | None = None


def _playground_root() -> Path:
    return PROJECT_ROOT / "third_party" / "upstreams" / "GraspVLA-playground"


def _ensure_playground_imports(playground_root: Path) -> None:
    import sys

    playground_path = str(playground_root)
    robosuite_path = str(playground_root / "third_party" / "robosuite")
    if robosuite_path not in sys.path:
        sys.path.insert(0, robosuite_path)
    if playground_path not in sys.path:
        sys.path.insert(0, playground_path)


def _with_playground_imports() -> tuple[Path, Path]:
    playground_root = _playground_root()
    _ensure_playground_imports(playground_root)
    previous_cwd = Path.cwd()
    os.chdir(playground_root)
    return playground_root, previous_cwd


def _restore_cwd(previous_cwd: Path) -> None:
    os.chdir(previous_cwd)


def _robot_config_path(robot_profile: str) -> Path:
    if robot_profile == "extended_finger":
        return PROJECT_ROOT / "third_party" / "upstreams" / "GraspVLA-playground" / "assets" / "franka_with_extended_finger" / "franka.yml"
    return PROJECT_ROOT / "third_party" / "upstreams" / "curobo" / "src" / "curobo" / "content" / "configs" / "robot" / "franka.yml"


def parse_seed_csv(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _official_task_candidates(benchmarks: list[str]) -> dict[str, list[dict[str, Any]]]:
    from benchmark_runner import get_benchmark_dict

    benchmark_dict = get_benchmark_dict()
    candidates: dict[str, list[dict[str, Any]]] = {}
    for benchmark_name in benchmarks:
        benchmark_instance = benchmark_dict[benchmark_name]()
        entries: list[dict[str, Any]] = []
        for task_id in range(len(benchmark_instance.tasks)):
            task = benchmark_instance.get_task(task_id)
            entries.append(
                {
                    "benchmark": benchmark_name,
                    "task_id": task_id,
                    "task_name": str(task.name),
                    "bddl_file": str(task.bddl_file),
                    "problem_folder": str(task.problem_folder),
                }
            )
        candidates[benchmark_name] = entries
    return candidates


def select_non_invalid_official_tasks(
    candidates: dict[str, list[dict[str, Any]]],
    tasks_per_benchmark: int,
    is_valid: Callable[[str, int], tuple[bool, str, tuple[str, ...]]],
) -> list[OfficialLiberoTaskSpec]:
    selected: list[OfficialLiberoTaskSpec] = []
    for benchmark_name, entries in candidates.items():
        chosen = 0
        for entry in entries:
            valid, instruction, obj_of_interest = is_valid(benchmark_name, int(entry["task_id"]))
            if not valid:
                continue
            selected.append(
                OfficialLiberoTaskSpec(
                    benchmark=benchmark_name,
                    task_id=int(entry["task_id"]),
                    task_name=str(entry["task_name"]),
                    bddl_file=str(entry["bddl_file"]),
                    problem_folder=str(entry["problem_folder"]),
                    instruction=instruction,
                    obj_of_interest=tuple(obj_of_interest),
                )
            )
            chosen += 1
            if chosen >= tasks_per_benchmark:
                break
        if chosen < tasks_per_benchmark:
            raise RuntimeError(
                f"Benchmark {benchmark_name} only yielded {chosen} non-invalid tasks, expected {tasks_per_benchmark}."
            )
    return selected


def select_official_libero_subset(benchmarks: list[str], tasks_per_benchmark: int) -> list[OfficialLiberoTaskSpec]:
    playground_root, previous_cwd = _with_playground_imports()
    try:
        from benchmark_runner import create_environment, get_benchmark_dict, process_initial_state, setup_benchmark_paths

        paths = setup_benchmark_paths()
        bddl_files_default_path = paths["bddl_files"]
        benchmark_candidates = _official_task_candidates(benchmarks)
        benchmark_dict = get_benchmark_dict()

        def _is_valid(benchmark_name: str, task_id: int) -> tuple[bool, str, tuple[str, ...]]:
            problem_folder = str(benchmark_candidates[benchmark_name][task_id]["problem_folder"])
            bddl_file = str(benchmark_candidates[benchmark_name][task_id]["bddl_file"])
            bddl_file_path = os.path.join(bddl_files_default_path, problem_folder, bddl_file)
            try:
                env = create_environment(bddl_file_path, seed=0)
                try:
                    benchmark_instance = benchmark_dict[benchmark_name]()
                    task = benchmark_instance.get_task(task_id)
                    init_states = benchmark_instance.get_task_init_states(task_id)
                    processed_state = process_initial_state(
                        init_states[0],
                        task.bddl_file,
                        benchmark_name,
                        len(env.env.objects_dict),
                    )
                    if len(env.get_sim_state()) != len(processed_state):
                        raise RuntimeError(
                            f"State length mismatch for {benchmark_name} task {task_id}: "
                            f"env={len(env.get_sim_state())} processed={len(processed_state)}"
                        )
                    env.set_init_state(processed_state)
                    instruction = str(env.language_instruction)
                    if instruction == "invalid":
                        return False, instruction, tuple()
                    return True, instruction, tuple(str(item) for item in env.obj_of_interest)
                finally:
                    env.close()
            except Exception:
                return False, "unavailable", tuple()

        return select_non_invalid_official_tasks(benchmark_candidates, tasks_per_benchmark, _is_valid)
    finally:
        _restore_cwd(previous_cwd)


def _create_official_env(
    *,
    bddl_file_path: str,
    seed: int,
    scene_properties: dict[str, Any] | None = None,
    ignore_done: bool,
) -> Any:
    from libero.libero.envs import OffScreenRenderEnv

    env = OffScreenRenderEnv(
        bddl_file_name=bddl_file_path,
        camera_names=["front_view", "side_view"],
        camera_heights=256,
        camera_widths=256,
        control_freq=5,
        controller="IK_POSE",
        ignore_done=ignore_done,
        scene_properties=scene_properties,
    )
    env.seed(seed)
    env.reset()
    return env


def _stabilize_scene(env: Any, agent: Any, obs: dict[str, Any], steps: int = 10) -> dict[str, Any]:
    current_obs = obs
    for _ in range(steps):
        if hasattr(agent, "get_current_proprio"):
            action = agent.get_current_proprio(current_obs)
            action[-1] = -1.0
        else:
            action = agent.current_open_action(current_obs)
        current_obs, _reward, _done, _info = env.step(action)
    return current_obs


def _shared_success_definition(lift_threshold_cm: float, hold_steps: int, control_freq: int) -> dict[str, Any]:
    return {
        "lift_cm_min": round(float(lift_threshold_cm), 4),
        "hold_steps": int(hold_steps),
        "hold_s_min": round(float(hold_steps) / float(control_freq), 4),
    }


def _resolve_shared_success_parameters(variant: OfficialAlignmentVariant, control_freq: int) -> tuple[float, int, dict[str, Any]]:
    lift_threshold_cm = (
        float(variant.lift_threshold_cm_override)
        if variant.lift_threshold_cm_override is not None
        else 15.0
    )
    hold_steps_required = (
        int(variant.hold_steps_override)
        if variant.hold_steps_override is not None
        else 10
    )
    return (
        lift_threshold_cm,
        hold_steps_required,
        _shared_success_definition(lift_threshold_cm, hold_steps_required, control_freq),
    )


def _use_official_remote_agent(variant: OfficialAlignmentVariant) -> bool:
    return variant.name == "V1_wrapper_official_parity"


def _build_agent(
    *,
    variant: OfficialAlignmentVariant,
    instruction: str,
    runtime_config: dict[str, Any],
    kinematics: SharedFrankaKinematics | None,
) -> Any:
    if variant.agent_mode == "official" or _use_official_remote_agent(variant):
        from agent import RemoteAgent

        return RemoteAgent(instruction, int(runtime_config["port"]))
    if kinematics is None:
        raise RuntimeError("Wrapper variants require kinematics.")
    return SharedTrackARemoteAgent(
        instruction=instruction,
        host=str(runtime_config["host"]),
        port=int(runtime_config["port"]),
        kinematics=kinematics,
    )


def _agent_step(agent: Any, obs: dict[str, Any], camera_meta: dict[str, Any] | None) -> tuple[Any, Any, dict[str, Any], float]:
    step_start = time.perf_counter()
    if camera_meta is None:
        action, bbox = agent.step(obs)
        debug = {"policy": "official_remote_agent"}
    else:
        action, bbox, debug = agent.step(obs, camera_meta)
    inference_ms = (time.perf_counter() - step_start) * 1000.0
    return action, bbox, debug, inference_ms


def _normalize_object_name(value: str) -> str:
    return "_".join(value.strip().lower().replace("-", " ").split())


def runtime_config_gpu(runtime_config: dict[str, Any]) -> str:
    return str(runtime_config.get("gpu_id", ""))


def _write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _max_lift_cm(current_z: dict[str, float], baseline_z: dict[str, float], instance_names: tuple[str, ...]) -> float:
    return max((current_z[name] - baseline_z[name]) * 100.0 for name in instance_names)


def _official_language_target(instruction: str, obj_of_interest: tuple[str, ...]) -> str:
    if instruction.startswith("pick up "):
        return instruction.removeprefix("pick up ").strip()
    if obj_of_interest:
        return obj_of_interest[0].replace("_", " ")
    return instruction


def _tracked_obj_instances(obs: dict[str, Any], obj_of_interest: tuple[str, ...]) -> tuple[str, ...]:
    tracked = tuple(instance_name for instance_name in obj_of_interest if f"{instance_name}_pos" in obs)
    if tracked:
        return tracked
    return tuple(
        instance_name
        for instance_name in obj_of_interest
        if "region" not in instance_name and "site" not in instance_name and "goal" not in instance_name
    )


def _result_row(
    *,
    variant: OfficialAlignmentVariant,
    task: str,
    scene_id: str,
    object_id: str,
    object_group: str,
    condition: str,
    instruction: str,
    success: bool,
    lift_cm: float,
    hold_s: float,
    inference_ms: float,
    cycle_time_s: float,
    failure_reason: str,
    video_path: str,
    node: str,
    commit: str,
    parent_run_id: str,
    runtime_config: dict[str, Any],
) -> EpisodeResult:
    return EpisodeResult(
        method="graspvla",
        track="official_alignment",
        execution_mode=variant.execution_mode,
        task=task,
        scene_id=scene_id,
        object_id=object_id,
        object_group=object_group,
        condition=condition,
        instruction=instruction,
        sensor_stack="dual_fixed_realsense_rgbd",
        attempts=1,
        success=success,
        lift_cm=round(float(lift_cm), 4),
        hold_s=round(float(hold_s), 4),
        spl=1.0 if success else 0.0,
        inference_ms=round(float(inference_ms), 4),
        cycle_time_s=round(float(cycle_time_s), 4),
        failure_stage="" if success else "task_failure",
        failure_reason="" if success else failure_reason,
        collision=False,
        video_path=video_path,
        node=node,
        commit=commit,
        parent_run_id=parent_run_id,
        shard_id="",
        gpu_id=runtime_config_gpu(runtime_config),
    )

def _run_libero_episode_direct_official(
    *,
    variant: OfficialAlignmentVariant,
    task_spec: OfficialLiberoTaskSpec,
    seed: int,
    artifact_dir: Path,
    runtime_config: dict[str, Any],
    node: str,
    commit: str,
    parent_run_id: str,
) -> tuple[EpisodeResult, dict[str, Any]]:
    import numpy as np
    from agent import RemoteAgent
    from benchmark_runner import create_environment, get_benchmark_dict, process_initial_state, run_episode, setup_benchmark_paths
    from misc.logger import VideoLogger

    paths = setup_benchmark_paths()
    benchmark_dict = get_benchmark_dict()
    benchmark_instance = benchmark_dict[task_spec.benchmark]()
    task = benchmark_instance.get_task(task_spec.task_id)
    bddl_file_path = os.path.join(paths["bddl_files"], task.problem_folder, task.bddl_file)
    env = create_environment(bddl_file_path, seed=0)
    agent: Any = None
    try:
        init_states = benchmark_instance.get_task_init_states(task_spec.task_id)
        initial_state = process_initial_state(
            init_states[seed],
            task.bddl_file,
            task_spec.benchmark,
            len(env.env.objects_dict),
        )
        if len(env.get_sim_state()) != len(initial_state):
            raise RuntimeError(
                f"State length mismatch for {task_spec.benchmark} task {task_spec.task_id} seed {seed}: "
                f"env={len(env.get_sim_state())} init={len(initial_state)}"
            )
        obs = env.set_init_state(initial_state)
        instruction = str(env.language_instruction)
        if instruction == "invalid":
            raise RuntimeError(
                f"Unexpected invalid instruction during selected episode: {task_spec.benchmark} task {task_spec.task_id}"
            )
        obj_of_interest = tuple(str(item) for item in env.obj_of_interest)
        tracked_instances = _tracked_obj_instances(obs, obj_of_interest)
        target_label = _official_language_target(instruction, obj_of_interest)
        baseline_z = {
            instance_name: float(np.asarray(obs[f"{instance_name}_pos"])[2])
            for instance_name in tracked_instances
        }
        agent = RemoteAgent(instruction, int(runtime_config["port"]))
        video_logger = VideoLogger(str(ensure_dir(artifact_dir / "videos")))
        video_logger.start_recording(task_spec.benchmark, str(task_spec.task_id), target_label, seed)
        cycle_start = time.perf_counter()
        run_episode(env, agent, video_logger, obs, max_steps=300, stabilize_steps=10, debug=False)
        cycle_time_s = time.perf_counter() - cycle_start
        final_obs = _refresh_obs(env)
        final_z = {
            instance_name: float(np.asarray(final_obs[f"{instance_name}_pos"])[2])
            for instance_name in tracked_instances
        }
        lift_cm = _max_lift_cm(final_z, baseline_z, tracked_instances) if tracked_instances else 0.0
        video_path = ""
        success = False
        if video_logger.new_video_name:
            video_path = str(Path(video_logger.new_video_name).relative_to(artifact_dir))
            success = "_success.mp4" in video_logger.new_video_name
        failure_reason = "" if success else "Official runner did not report env done within the episode budget."
        payload = {
            "source": "libero",
            "variant": variant.name,
            "benchmark": task_spec.benchmark,
            "task_id": task_spec.task_id,
            "task_name": task_spec.task_name,
            "seed": seed,
            "instruction": instruction,
            "target_label": target_label,
            "obj_of_interest": list(obj_of_interest),
            "tracked_obj_instances": list(tracked_instances),
            "success": success,
            "best_lift_cm": round(lift_cm, 4),
            "hold_s": 0.0,
            "failure_reason": failure_reason,
            "scene_edit_policy": variant.scene_edit_policy,
            "success_mode": variant.success_mode,
            "robot_profile": variant.robot_profile,
            "agent_mode": variant.agent_mode,
            "video_path": video_path,
            "baseline_z": baseline_z,
            "final_z": final_z,
            "direct_official_runner": True,
        }
        episode_json = ensure_dir(artifact_dir / "episodes") / f"{task_spec.episode_prefix}__seed{seed:03d}.json"
        _write_json(episode_json, payload)
        result = _result_row(
            variant=variant,
            task=task_spec.benchmark,
            scene_id=f"{task_spec.episode_prefix}__seed{seed:03d}",
            object_id=_normalize_object_name(target_label),
            object_group=task_spec.benchmark,
            condition=task_spec.task_name,
            instruction=instruction,
            success=success,
            lift_cm=lift_cm,
            hold_s=0.0,
            inference_ms=0.0,
            cycle_time_s=cycle_time_s,
            failure_reason=failure_reason,
            video_path=video_path,
            node=node,
            commit=commit,
            parent_run_id=parent_run_id,
            runtime_config=runtime_config,
        )
        return result, payload
    finally:
        if agent is not None and hasattr(agent, "close"):
            agent.close()
        if env is not None:
            env.close()


def _run_playground_episode_direct_official(
    *,
    variant: OfficialAlignmentVariant,
    seed: int,
    artifact_dir: Path,
    runtime_config: dict[str, Any],
    node: str,
    commit: str,
    parent_run_id: str,
) -> tuple[EpisodeResult, dict[str, Any]]:
    import numpy as np
    from agent import RemoteAgent
    from benchmark_runner import create_environment, get_benchmark_dict, run_episode, set_random_seeds
    from libero.libero import get_libero_path
    from misc.export_as_bddl import export_as_bddl_file
    from misc.logger import VideoLogger
    from misc.sampling import sample_background, sample_init_state, sample_objects

    set_random_seeds(seed)
    benchmark_instance = get_benchmark_dict()["libero_object"]()
    task = benchmark_instance.get_task(10)
    object_root_dir = "assets/playground_assets"
    complete_object_names = sample_objects(object_num=6, object_root_dir=object_root_dir)
    object_names = ["_".join(c.split("_")[:-1]) for c in complete_object_names]
    target_object_name = random.choice(object_names).replace("_", " ")
    init_state = sample_init_state(
        complete_object_names,
        offset=np.array([-0.6, 0.0, 0.0]),
        object_root_dir=object_root_dir,
    )
    bddl_path = ensure_dir(artifact_dir / "bddl") / f"playground_seed{seed:03d}.bddl"
    export_as_bddl_file(object_names, target_object_name, str(bddl_path))
    bddl_file_path = os.path.join(get_libero_path("bddl_files"), task.problem_folder, task.bddl_file)
    env = create_environment(bddl_file_path, seed=seed, scene_properties=sample_background())
    agent: Any = None
    try:
        if len(env.get_sim_state()) != len(init_state):
            raise RuntimeError(
                f"Playground state length mismatch for seed {seed}: env={len(env.get_sim_state())} init={len(init_state)}"
            )
        obs = env.set_init_state(init_state)
        instruction = f"pick up {target_object_name}"
        obj_of_interest = tuple(str(item) for item in env.obj_of_interest)
        baseline_z = {
            instance_name: float(np.asarray(obs[f"{instance_name}_pos"])[2])
            for instance_name in obj_of_interest
        }
        agent = RemoteAgent(instruction, int(runtime_config["port"]))
        video_logger = VideoLogger(str(ensure_dir(artifact_dir / "videos")))
        video_logger.start_recording("", "", target_object_name, seed)
        cycle_start = time.perf_counter()
        run_episode(env, agent, video_logger, obs, max_steps=300, stabilize_steps=10, debug=False)
        cycle_time_s = time.perf_counter() - cycle_start
        final_obs = _refresh_obs(env)
        final_z = {
            instance_name: float(np.asarray(final_obs[f"{instance_name}_pos"])[2])
            for instance_name in obj_of_interest
        }
        lift_cm = _max_lift_cm(final_z, baseline_z, obj_of_interest)
        video_path = ""
        success = False
        if video_logger.new_video_name:
            video_path = str(Path(video_logger.new_video_name).relative_to(artifact_dir))
            success = "_success.mp4" in video_logger.new_video_name
        failure_reason = "" if success else "Official playground runner did not report env done within the episode budget."
        payload = {
            "source": "playground",
            "variant": variant.name,
            "seed": seed,
            "instruction": instruction,
            "target_label": target_object_name,
            "scene_objects": object_names,
            "success": success,
            "best_lift_cm": round(lift_cm, 4),
            "failure_reason": failure_reason,
            "scene_edit_policy": variant.scene_edit_policy,
            "success_mode": variant.success_mode,
            "robot_profile": variant.robot_profile,
            "agent_mode": variant.agent_mode,
            "video_path": video_path,
            "baseline_z": baseline_z,
            "final_z": final_z,
            "direct_official_runner": True,
        }
        episode_json = ensure_dir(artifact_dir / "playground_episodes") / f"playground__seed{seed:03d}.json"
        _write_json(episode_json, payload)
        result = _result_row(
            variant=variant,
            task="playground",
            scene_id=f"playground__seed{seed:03d}",
            object_id=_normalize_object_name(target_object_name),
            object_group="playground",
            condition="playground",
            instruction=instruction,
            success=success,
            lift_cm=lift_cm,
            hold_s=0.0,
            inference_ms=0.0,
            cycle_time_s=cycle_time_s,
            failure_reason=failure_reason,
            video_path=video_path,
            node=node,
            commit=commit,
            parent_run_id=parent_run_id,
            runtime_config=runtime_config,
        )
        return result, payload
    finally:
        if agent is not None and hasattr(agent, "close"):
            agent.close()
        if env is not None:
            env.close()


def _run_libero_episode(
    *,
    variant: OfficialAlignmentVariant,
    task_spec: OfficialLiberoTaskSpec,
    seed: int,
    artifact_dir: Path,
    runtime_config: dict[str, Any],
    node: str,
    commit: str,
    parent_run_id: str,
    trace_steps: bool,
) -> tuple[EpisodeResult, dict[str, Any]]:
    if variant.agent_mode == "official_runner":
        return _run_libero_episode_direct_official(
            variant=variant,
            task_spec=task_spec,
            seed=seed,
            artifact_dir=artifact_dir,
            runtime_config=runtime_config,
            node=node,
            commit=commit,
            parent_run_id=parent_run_id,
        )

    import numpy as np
    import transforms3d as t3d
    from benchmark_runner import process_initial_state, setup_benchmark_paths
    from misc.logger import VideoLogger

    paths = setup_benchmark_paths()
    bddl_files_default_path = paths["bddl_files"]
    from benchmark_runner import get_benchmark_dict

    benchmark_instance = get_benchmark_dict()[task_spec.benchmark]()
    task = benchmark_instance.get_task(task_spec.task_id)
    bddl_file_path = os.path.join(bddl_files_default_path, task.problem_folder, task.bddl_file)
    ignore_done = variant.success_mode != "env_done"
    env = _create_official_env(
        bddl_file_path=bddl_file_path,
        seed=0,
        scene_properties=None,
        ignore_done=ignore_done,
    )
    video_logger: Any = None
    agent: Any = None
    try:
        init_states = benchmark_instance.get_task_init_states(task_spec.task_id)
        if variant.scene_edit_policy == "official":
            initial_state = process_initial_state(
                init_states[seed],
                task.bddl_file,
                task_spec.benchmark,
                len(env.env.objects_dict),
            )
        else:
            initial_state = init_states[seed]
        if len(env.get_sim_state()) != len(initial_state):
            raise RuntimeError(
                f"State length mismatch for {task_spec.benchmark} task {task_spec.task_id} seed {seed}: env={len(env.get_sim_state())} init={len(initial_state)}"
            )
        obs = env.set_init_state(initial_state)
        instruction = str(env.language_instruction)
        if instruction == "invalid":
            raise RuntimeError(f"Unexpected invalid instruction during selected episode: {task_spec.benchmark} task {task_spec.task_id}")
        obj_of_interest = tuple(str(item) for item in env.obj_of_interest)
        tracked_instances = _tracked_obj_instances(obs, obj_of_interest)
        target_label = _official_language_target(instruction, obj_of_interest)
        robot_config_path = _robot_config_path(variant.robot_profile)
        kinematics = None
        camera_meta = None
        if variant.agent_mode == "wrapper" and not _use_official_remote_agent(variant):
            kinematics = SharedFrankaKinematics(robot_config_path)
            env.robots[0].IK_solver = kinematics
            camera_meta = _camera_metadata(env, {"camera_names": {"front": "front_view", "side": "side_view"}})
        agent = _build_agent(
            variant=variant,
            instruction=instruction,
            runtime_config=runtime_config,
            kinematics=kinematics,
        )
        obs = _stabilize_scene(env, agent, obs, steps=10)
        baseline_z = {
            instance_name: float(np.asarray(obs[f"{instance_name}_pos"])[2])
            for instance_name in tracked_instances
        }
        final_z = dict(baseline_z)
        hold_counts = {instance_name: 0 for instance_name in tracked_instances}
        control_freq = 5
        lift_threshold_cm, hold_steps_required, shared_success = _resolve_shared_success_parameters(
            variant,
            control_freq,
        )
        cycle_start = time.perf_counter()
        per_step_inference_ms: list[float] = []
        step_trace: list[dict[str, Any]] = []
        video_logger = VideoLogger(str(ensure_dir(artifact_dir / "videos")))
        video_logger.start_recording(task_spec.benchmark, str(task_spec.task_id), target_label, seed)
        success = False
        best_lift_cm = 0.0
        hold_s = 0.0
        failure_reason = "env done was not reached within the official step budget."
        for step_index in range(300):
            action, bbox, debug, inference_ms = _agent_step(agent, obs, camera_meta)
            per_step_inference_ms.append(inference_ms)
            obs, _reward, done, _info = env.step(action)
            video_logger.log_frame(obs, bbox)
            current_contacts = int(getattr(env.sim.data, "ncon", 0))
            for instance_name in tracked_instances:
                current_z = float(np.asarray(obs[f"{instance_name}_pos"])[2])
                final_z[instance_name] = current_z
                lift_delta_cm = (current_z - baseline_z[instance_name]) * 100.0
                best_lift_cm = max(best_lift_cm, lift_delta_cm)
                if variant.success_mode == "shared_lift_hold":
                    if lift_delta_cm >= lift_threshold_cm:
                        hold_counts[instance_name] += 1
                        if hold_counts[instance_name] >= hold_steps_required:
                            success = True
                            hold_s = round(hold_counts[instance_name] / control_freq, 4)
                            failure_reason = ""
                            break
                    else:
                        hold_counts[instance_name] = 0
            if trace_steps:
                target_name = tracked_instances[0] if tracked_instances else ""
                target_z = float(np.asarray(obs[f"{target_name}_pos"])[2]) if target_name else 0.0
                if kinematics is not None:
                    ee_position, ee_quaternion = kinematics.fk(np.asarray(obs["robot0_joint_pos"], dtype=np.float32))
                    ee_euler = np.asarray(t3d.euler.quat2euler(ee_quaternion, axes="sxyz"), dtype=np.float32)
                    ee_pose = np.concatenate([ee_position, ee_euler])
                else:
                    ee_pose = np.asarray(agent.get_current_proprio(obs)[:6], dtype=np.float32)
                step_trace.append(
                    _step_trace_entry(
                        step_index=step_index,
                        action=action,
                        bbox=bbox,
                        debug=debug,
                        ee_pose=ee_pose,
                        target_z=target_z,
                        max_lift_cm=best_lift_cm,
                        contact=current_contacts > 0,
                        slip=False,
                    )
                )
            if variant.success_mode == "env_done" and done:
                success = True
                failure_reason = ""
                break
            if success:
                break
        video_logger.stop_recording(success=success)
        video_path = ""
        if video_logger.new_video_name:
            video_path = str(Path(video_logger.new_video_name).relative_to(artifact_dir))
        mean_inference_ms = sum(per_step_inference_ms) / len(per_step_inference_ms) if per_step_inference_ms else 0.0
        cycle_time_s = time.perf_counter() - cycle_start
        if variant.success_mode == "shared_lift_hold" and not success:
            failure_reason = "Shared success criterion was not met within the official-aligned step budget."
        payload = {
            "source": "libero",
            "variant": variant.name,
            "benchmark": task_spec.benchmark,
            "task_id": task_spec.task_id,
            "task_name": task_spec.task_name,
            "seed": seed,
            "instruction": instruction,
            "target_label": target_label,
            "obj_of_interest": list(obj_of_interest),
            "tracked_obj_instances": list(tracked_instances),
            "success": success,
            "best_lift_cm": round(best_lift_cm, 4),
            "hold_s": round(hold_s, 4),
            "failure_reason": failure_reason,
            "scene_edit_policy": variant.scene_edit_policy,
            "success_mode": variant.success_mode,
            "robot_profile": variant.robot_profile,
            "agent_mode": variant.agent_mode,
            "video_path": video_path,
            "baseline_z": baseline_z,
            "final_z": final_z,
            "shared_success_definition": shared_success,
            "step_trace": step_trace,
        }
        episode_json = ensure_dir(artifact_dir / "episodes") / f"{task_spec.episode_prefix}__seed{seed:03d}.json"
        _write_json(episode_json, payload)
        result = EpisodeResult(
            method="graspvla",
            track="official_alignment",
            execution_mode=variant.execution_mode,
            task=task_spec.benchmark,
            scene_id=f"{task_spec.episode_prefix}__seed{seed:03d}",
            object_id=_normalize_object_name(target_label),
            object_group=task_spec.benchmark,
            condition=task_spec.task_name,
            instruction=instruction,
            sensor_stack="dual_fixed_realsense_rgbd",
            attempts=1,
            success=success,
            lift_cm=round(best_lift_cm, 4),
            hold_s=round(hold_s, 4),
            spl=1.0 if success else 0.0,
            inference_ms=round(mean_inference_ms, 4),
            cycle_time_s=round(cycle_time_s, 4),
            failure_stage="" if success else "task_failure",
            failure_reason="" if success else failure_reason,
            collision=False,
            video_path=video_path,
            node=node,
            commit=commit,
            parent_run_id=parent_run_id,
            shard_id="",
            gpu_id=runtime_config_gpu(runtime_config),
        )
        return result, payload
    finally:
        if agent is not None and hasattr(agent, "close"):
            agent.close()
        if env is not None:
            env.close()


def _run_playground_episode(
    *,
    variant: OfficialAlignmentVariant,
    seed: int,
    artifact_dir: Path,
    runtime_config: dict[str, Any],
    node: str,
    commit: str,
    parent_run_id: str,
) -> tuple[EpisodeResult, dict[str, Any]]:
    if variant.agent_mode == "official_runner":
        return _run_playground_episode_direct_official(
            variant=variant,
            seed=seed,
            artifact_dir=artifact_dir,
            runtime_config=runtime_config,
            node=node,
            commit=commit,
            parent_run_id=parent_run_id,
        )

    import numpy as np
    from benchmark_runner import set_random_seeds
    from libero.libero import get_libero_path
    from benchmark_runner import get_benchmark_dict
    from misc.export_as_bddl import export_as_bddl_file
    from misc.logger import VideoLogger
    from misc.sampling import sample_background, sample_init_state, sample_objects

    set_random_seeds(seed)
    benchmark_instance = get_benchmark_dict()["libero_object"]()
    task = benchmark_instance.get_task(10)
    object_root_dir = "assets/playground_assets"
    complete_object_names = sample_objects(object_num=6, object_root_dir=object_root_dir)
    object_names = ["_".join(c.split("_")[:-1]) for c in complete_object_names]
    target_object_name = random.choice(object_names).replace("_", " ")
    init_state = sample_init_state(
        complete_object_names,
        offset=np.array([-0.6, 0.0, 0.0]),
        object_root_dir=object_root_dir,
    )
    bddl_path = ensure_dir(artifact_dir / "bddl") / f"playground_seed{seed:03d}.bddl"
    export_as_bddl_file(object_names, target_object_name, str(bddl_path))
    bddl_file_path = os.path.join(get_libero_path("bddl_files"), task.problem_folder, task.bddl_file)
    ignore_done = variant.success_mode != "env_done"
    env = _create_official_env(
        bddl_file_path=bddl_file_path,
        seed=seed,
        scene_properties=sample_background(),
        ignore_done=ignore_done,
    )
    video_logger: Any = None
    agent: Any = None
    try:
        if len(env.get_sim_state()) != len(init_state):
            raise RuntimeError(
                f"Playground state length mismatch for seed {seed}: env={len(env.get_sim_state())} init={len(init_state)}"
            )
        obs = env.set_init_state(init_state)
        instruction = f"pick up {target_object_name}"
        obj_of_interest = tuple(str(item) for item in env.obj_of_interest)
        tracked_instances = _tracked_obj_instances(obs, obj_of_interest)
        robot_config_path = _robot_config_path(variant.robot_profile)
        kinematics = None
        camera_meta = None
        if variant.agent_mode == "wrapper" and not _use_official_remote_agent(variant):
            kinematics = SharedFrankaKinematics(robot_config_path)
            env.robots[0].IK_solver = kinematics
            camera_meta = _camera_metadata(env, {"camera_names": {"front": "front_view", "side": "side_view"}})
        agent = _build_agent(
            variant=variant,
            instruction=instruction,
            runtime_config=runtime_config,
            kinematics=kinematics,
        )
        obs = _stabilize_scene(env, agent, obs, steps=10)
        baseline_z = {
            instance_name: float(np.asarray(obs[f"{instance_name}_pos"])[2])
            for instance_name in tracked_instances
        }
        final_z = dict(baseline_z)
        control_freq = 5
        lift_threshold_cm, hold_steps_required, _shared_success = _resolve_shared_success_parameters(
            variant,
            control_freq,
        )
        hold_counts = {instance_name: 0 for instance_name in tracked_instances}
        cycle_start = time.perf_counter()
        per_step_inference_ms: list[float] = []
        best_lift_cm = 0.0
        success = False
        failure_reason = "env done was not reached within the official playground step budget."
        video_logger = VideoLogger(str(ensure_dir(artifact_dir / "videos")))
        video_logger.start_recording("playground", "seed", target_object_name, seed)
        for _ in range(300):
            action, bbox, _debug, inference_ms = _agent_step(agent, obs, camera_meta)
            per_step_inference_ms.append(inference_ms)
            obs, _reward, done, _info = env.step(action)
            video_logger.log_frame(obs, bbox)
            for instance_name in tracked_instances:
                current_z = float(np.asarray(obs[f"{instance_name}_pos"])[2])
                final_z[instance_name] = current_z
                lift_delta_cm = (current_z - baseline_z[instance_name]) * 100.0
                best_lift_cm = max(best_lift_cm, lift_delta_cm)
                if variant.success_mode == "shared_lift_hold":
                    if lift_delta_cm >= lift_threshold_cm:
                        hold_counts[instance_name] += 1
                        if hold_counts[instance_name] >= hold_steps_required:
                            success = True
                            failure_reason = ""
                            break
                    else:
                        hold_counts[instance_name] = 0
            if variant.success_mode == "env_done" and done:
                success = True
                failure_reason = ""
                break
            if success:
                break
        video_logger.stop_recording(success=success)
        video_path = ""
        if video_logger.new_video_name:
            video_path = str(Path(video_logger.new_video_name).relative_to(artifact_dir))
        mean_inference_ms = sum(per_step_inference_ms) / len(per_step_inference_ms) if per_step_inference_ms else 0.0
        cycle_time_s = time.perf_counter() - cycle_start
        payload = {
            "source": "playground",
            "variant": variant.name,
            "seed": seed,
            "instruction": instruction,
            "target_label": target_object_name,
            "scene_objects": object_names,
            "tracked_obj_instances": list(tracked_instances),
            "success": success,
            "best_lift_cm": round(best_lift_cm, 4),
            "failure_reason": failure_reason,
            "scene_edit_policy": variant.scene_edit_policy,
            "success_mode": variant.success_mode,
            "robot_profile": variant.robot_profile,
            "agent_mode": variant.agent_mode,
            "video_path": video_path,
            "baseline_z": baseline_z,
            "final_z": final_z,
        }
        episode_json = ensure_dir(artifact_dir / "playground_episodes") / f"playground__seed{seed:03d}.json"
        _write_json(episode_json, payload)
        result = EpisodeResult(
            method="graspvla",
            track="official_alignment",
            execution_mode=variant.execution_mode,
            task="playground",
            scene_id=f"playground__seed{seed:03d}",
            object_id=_normalize_object_name(target_object_name),
            object_group="playground",
            condition="playground",
            instruction=instruction,
            sensor_stack="dual_fixed_realsense_rgbd",
            attempts=1,
            success=success,
            lift_cm=round(best_lift_cm, 4),
            hold_s=0.0,
            spl=1.0 if success else 0.0,
            inference_ms=round(mean_inference_ms, 4),
            cycle_time_s=round(cycle_time_s, 4),
            failure_stage="" if success else "task_failure",
            failure_reason="" if success else failure_reason,
            collision=False,
            video_path=video_path,
            node=node,
            commit=commit,
            parent_run_id=parent_run_id,
            shard_id="",
            gpu_id=runtime_config_gpu(runtime_config),
        )
        return result, payload
    finally:
        if agent is not None and hasattr(agent, "close"):
            agent.close()
        if env is not None:
            env.close()


def run_official_aligned_suite(
    *,
    variant: OfficialAlignmentVariant,
    artifact_dir: Path,
    runtime_config: dict[str, Any],
    node: str,
    commit: str,
    parent_run_id: str,
    benchmarks: list[str],
    tasks_per_benchmark: int,
    seeds: list[int],
    playground_seeds: list[int],
    trace_steps: bool = False,
) -> tuple[list[EpisodeResult], dict[str, Any]]:
    playground_root, previous_cwd = _with_playground_imports()
    try:
        selected_tasks = select_official_libero_subset(benchmarks, tasks_per_benchmark)
        results: list[EpisodeResult] = []
        episodes_written: list[dict[str, Any]] = []
        ensure_dir(artifact_dir)
        for task_spec in selected_tasks:
            for seed in seeds:
                result, payload = _run_libero_episode(
                    variant=variant,
                    task_spec=task_spec,
                    seed=seed,
                    artifact_dir=artifact_dir,
                    runtime_config=runtime_config,
                    node=node,
                    commit=commit,
                    parent_run_id=parent_run_id,
                    trace_steps=trace_steps,
                )
                results.append(result)
                episodes_written.append(payload)
        if variant.run_playground_sanity:
            for seed in playground_seeds:
                result, payload = _run_playground_episode(
                    variant=variant,
                    seed=seed,
                    artifact_dir=artifact_dir,
                    runtime_config=runtime_config,
                    node=node,
                    commit=commit,
                    parent_run_id=parent_run_id,
                )
                results.append(result)
                episodes_written.append(payload)
        metadata = {
            "mode": "official_aligned_suite",
            "variant": {
                "name": variant.name,
                "execution_mode": variant.execution_mode,
                "agent_mode": variant.agent_mode,
                "robot_profile": variant.robot_profile,
                "success_mode": variant.success_mode,
                "scene_edit_policy": variant.scene_edit_policy,
                "run_playground_sanity": variant.run_playground_sanity,
            },
            "benchmarks": benchmarks,
            "tasks_per_benchmark": tasks_per_benchmark,
            "selected_tasks": [
                {
                    "benchmark": item.benchmark,
                    "task_id": item.task_id,
                    "task_name": item.task_name,
                    "instruction": item.instruction,
                    "obj_of_interest": list(item.obj_of_interest),
                }
                for item in selected_tasks
            ],
            "seed_list": list(seeds),
            "playground_seed_list": list(playground_seeds),
            "playground_root": str(playground_root),
        }
        _write_json(artifact_dir / "official_subset.json", metadata)
        return results, metadata
    finally:
        _restore_cwd(previous_cwd)
