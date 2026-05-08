from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.config import load_cluster_config, load_named_config, resolve_cluster_config_name
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.shell import run_command
from grasp_benchmark.task_specs import expand_task_set


@dataclass(frozen=True, slots=True)
class DispatchShard:
    shard_index: int
    shard_count: int
    node: str
    gpu_id: str
    local_run_dir: Path
    remote_run_dir: str
    remote_command: str

    @property
    def shard_id(self) -> str:
        return f"shard_{self.shard_index:03d}"


def _load_available_nodes(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _available_node_records(available_nodes: dict) -> dict[str, dict]:
    return {str(node["host"]): node for node in available_nodes.get("nodes", [])}


def _pick_node(method_config: dict, cluster_config: dict, available_nodes: dict, explicit_node: str) -> str:
    if explicit_node:
        return explicit_node
    dispatch_hosts = set(available_nodes.get("dispatch_hosts", []))
    for host in method_config.get("preferred_nodes", []):
        if host in dispatch_hosts:
            return host
    for pool in cluster_config["preferred_dispatch_order"]:
        for host in cluster_config["pool_hosts"].get(pool, []):
            if host in dispatch_hosts:
                return host
    raise RuntimeError("No runnable dispatch hosts found. Run preflight first.")


def _resolve_execution_mode(method_config: dict, explicit_mode: str) -> str:
    if explicit_mode:
        return explicit_mode
    return str(method_config.get("sim", {}).get("execution_mode", "integration_fixture"))


def _remote_env_name(method_config: dict, execution_mode: str) -> str:
    if execution_mode == "shared_track_a_sim":
        return str(
            method_config.get(
                "shared_sim_env_name",
                method_config.get("official_sim_env_name", method_config["env_name"]),
            )
        )
    if execution_mode == "official_aligned_sim":
        return str(method_config.get("official_sim_env_name", method_config["env_name"]))
    return str(method_config["env_name"])


def _libero_config_command(remote_root: str, libero_config_root: str) -> str:
    benchmark_root = f"{remote_root}/third_party/upstreams/GraspVLA-playground/libero/libero"
    datasets_root = f"{remote_root}/third_party/upstreams/GraspVLA-playground/libero/datasets"
    config_path = f"{libero_config_root}/config.yaml"
    return (
        f'mkdir -p "{libero_config_root}" "{datasets_root}" && '
        "printf '%s\\n' "
        f'"assets: {benchmark_root}/assets" '
        f'"bddl_files: {benchmark_root}/bddl_files" '
        f'"benchmark_root: {benchmark_root}" '
        f'"datasets: {datasets_root}" '
        f'"init_states: {benchmark_root}/init_files" '
        f'> "{config_path}"'
    )


def _graspvla_server_bootstrap_command(cluster_config: dict, method_config: dict, run_dir: str) -> str:
    if str(method_config.get("name", "")).strip() != "graspvla":
        return ""

    server_config = method_config.get("server", {})
    if not isinstance(server_config, dict):
        return ""

    remote_root = cluster_config["remote_root"]
    server_env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["env_name"]}'
    server_python = f"{server_env_prefix}/bin/python"
    upstream_dir = f"{remote_root}/third_party/upstreams/GraspVLA"
    model_cache_dir = str(method_config.get("model_cache_dir", "")).strip()
    model_glob = str(method_config.get("model_glob", "*.safetensors")).strip() or "*.safetensors"
    port = int(server_config.get("port", cluster_config.get("default_server_port", 6666)))
    compile_flag = "--compile" if bool(server_config.get("compile", False)) else ""
    log_dir = f"{run_dir}/graspvla_server"
    validate_timeout_s = int(server_config.get("validate_timeout_s", 5) or 5)
    validate_attempts = int(server_config.get("validate_attempts", 120) or 120)
    validate_sleep_s = int(server_config.get("validate_sleep_s", 5) or 5)

    if not model_cache_dir:
        raise ValueError("GraspVLA method config must set model_cache_dir.")

    return f"""
{{
  mkdir -p "{log_dir}";
  GB_GRASPVLA_MODEL="$(find "{model_cache_dir}" -type f -name "{model_glob}" | sort | head -n 1)";
  if [ -z "${{GB_GRASPVLA_MODEL}}" ]; then
    echo "No GraspVLA model file matching {model_glob} under {model_cache_dir}" >&2;
    exit 42;
  fi;
  if [ ! -x "{server_python}" ]; then
    echo "Missing GraspVLA server Python: {server_python}" >&2;
    exit 43;
  fi;
  if [ ! -d "{upstream_dir}" ]; then
    echo "Missing GraspVLA upstream repository: {upstream_dir}" >&2;
    exit 44;
  fi;
  cleanup_graspvla_server() {{
    if [ -n "${{GB_GRASPVLA_SERVER_PID:-}}" ] && kill -0 "${{GB_GRASPVLA_SERVER_PID}}" >/dev/null 2>&1; then
      kill "${{GB_GRASPVLA_SERVER_PID}}" >/dev/null 2>&1 || true;
      wait "${{GB_GRASPVLA_SERVER_PID}}" >/dev/null 2>&1 || true;
    fi;
  }};
  trap cleanup_graspvla_server EXIT;
  (
    cd "{upstream_dir}" &&
    "{server_python}" -u -m vla_network.scripts.serve --path "${{GB_GRASPVLA_MODEL}}" --port "{port}" {compile_flag}
  ) > "{log_dir}/server_stdout.log" 2> "{log_dir}/server_stderr.log" &
  GB_GRASPVLA_SERVER_PID="$!";
  export GB_GRASPVLA_SERVER_PORT="{port}";
  export GB_GRASPVLA_VALIDATE_TIMEOUT_S="{validate_timeout_s}";
  for GB_GRASPVLA_VALIDATE_ATTEMPT in $(seq 1 "{validate_attempts}"); do
    if "{server_python}" - <<'PY'
import os
import sys
import numpy as np
import zmq

port = int(os.environ["GB_GRASPVLA_SERVER_PORT"])
timeout_s = int(os.environ["GB_GRASPVLA_VALIDATE_TIMEOUT_S"])
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.setsockopt(zmq.RCVTIMEO, timeout_s * 1000)
socket.setsockopt(zmq.SNDTIMEO, timeout_s * 1000)
socket.setsockopt(zmq.LINGER, 0)
try:
    socket.connect(f"tcp://127.0.0.1:{port}")
    image = np.zeros((256, 256, 3), dtype=np.uint8)
    proprio = [np.concatenate([np.zeros(6, dtype=np.float32), np.ones(1, dtype=np.float32)]) for _ in range(4)]
    socket.send_pyobj({{
        "front_view_image": [image],
        "side_view_image": [image],
        "proprio_array": proprio,
        "text": "Validation test instruction",
    }})
    response = socket.recv_pyobj()
    if not isinstance(response, dict) or not response.get("result"):
        raise RuntimeError(f"Unexpected GraspVLA response: {{response!r}}")
except Exception as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(1)
finally:
    socket.close()
    context.term()
PY
    then
      echo "GRASPVLA_SERVER_READY attempt=${{GB_GRASPVLA_VALIDATE_ATTEMPT}}";
      break;
    fi;
    if ! kill -0 "${{GB_GRASPVLA_SERVER_PID}}" >/dev/null 2>&1; then
      echo "GraspVLA server exited before validation." >&2;
      cat "{log_dir}/server_stderr.log" >&2 || true;
      exit 45;
    fi;
    if [ "${{GB_GRASPVLA_VALIDATE_ATTEMPT}}" -eq "{validate_attempts}" ]; then
      echo "GraspVLA server did not validate after {validate_attempts} attempts." >&2;
      tail -n 80 "{log_dir}/server_stdout.log" >&2 || true;
      tail -n 80 "{log_dir}/server_stderr.log" >&2 || true;
      exit 46;
    fi;
    sleep "{validate_sleep_s}";
  done;
}}
""".strip()


def _run_dir_name(timestamp: str, method: str, task_set: str, execution_mode: str) -> str:
    if execution_mode == "shared_track_a_sim":
        suffix = "shared_sim"
    elif execution_mode == "official_aligned_sim":
        suffix = "official_aligned"
    else:
        suffix = execution_mode
    return f"{timestamp}_{method}_{task_set}_{suffix}"


def _allocate_run_dir(base_root: Path, base_name: str) -> Path:
    ensure_dir(base_root)
    for suffix_index in range(1000):
        candidate_name = base_name if suffix_index == 0 else f"{base_name}__dup{suffix_index:02d}"
        candidate = base_root / candidate_name
        try:
            candidate.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise RuntimeError(f"Could not allocate a unique run directory for base name '{base_name}'.")


def _preferred_matrix_hosts(method_name: str, method_config: dict) -> list[str]:
    return [str(item) for item in method_config.get("preferred_nodes", [])]


def _select_matrix_hosts(
    *,
    method_name: str,
    method_config: dict,
    available_nodes: dict,
    explicit_nodes: str,
    explicit_node: str,
) -> list[str]:
    records = _available_node_records(available_nodes)
    dispatch_hosts = set(available_nodes.get("dispatch_hosts", []))
    if explicit_nodes:
        requested = [item.strip() for item in explicit_nodes.split(",") if item.strip()]
    elif explicit_node:
        requested = [explicit_node]
    else:
        requested = _preferred_matrix_hosts(method_name, method_config)

    selected: list[str] = []
    for host in requested:
        record = records.get(host)
        if record is None or host not in dispatch_hosts:
            continue
        if str(record.get("status", "")) not in {"available", "warning"}:
            continue
        if not record.get("gpu_names"):
            continue
        selected.append(host)
    if not selected and not explicit_nodes and not explicit_node:
        for host in available_nodes.get("dispatch_hosts", []):
            record = records.get(host)
            if record is None:
                continue
            if str(record.get("status", "")) not in {"available", "warning"}:
                continue
            if not record.get("gpu_names"):
                continue
            selected.append(str(host))
    if not selected:
        raise RuntimeError("No GPU-backed matrix hosts were available for dispatch.")
    return selected


def _build_remote_command(
    cluster_config: dict,
    method_config: dict,
    task_set: str,
    sensor_config: str,
    run_dir: str,
    execution_mode: str,
    smoke_only: bool,
    max_trials: int,
    *,
    cluster_config_name: str = "default",
    shard_index: int = 0,
    shard_count: int = 1,
    gpu_id: str = "",
    parent_run_id: str = "",
    trace_steps: bool = False,
    segmentation_mode: str = "",
    oracle_grasp_mode: str = "",
    native_multiview_fusion: bool = False,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{_remote_env_name(method_config, execution_mode)}'
    libero_config_root = f'{remote_root}/artifacts/libero_config'
    cache_root = f'{remote_root}/artifacts/cache'
    cuda_home = str(cluster_config.get("cuda_home", "")).strip().rstrip("/")
    smoke_flag = "--smoke-only" if smoke_only else ""
    max_trials_flag = f'--max-trials "{max_trials}"' if max_trials > 0 else ""
    shard_index_flag = f'--shard-index "{shard_index}"'
    shard_count_flag = f'--shard-count "{shard_count}"'
    gpu_flag = f'--gpu-id "{gpu_id}"' if gpu_id != "" else ""
    parent_flag = f'--parent-run-id "{parent_run_id}"' if parent_run_id else ""
    trace_steps_flag = "--trace-steps" if trace_steps else ""
    segmentation_mode_flag = f'--segmentation-mode "{segmentation_mode}"' if segmentation_mode else ""
    oracle_grasp_mode_flag = f'--oracle-grasp-mode "{oracle_grasp_mode}"' if oracle_grasp_mode else ""
    native_multiview_flag = "--native-multiview-fusion" if native_multiview_fusion else ""
    cuda_exports = (
        f'export CUDA_HOME="{cuda_home}" && '
        f'export PATH="{cuda_home}/bin:${{PATH}}" && '
        f'export LD_LIBRARY_PATH="{cuda_home}/lib64:${{LD_LIBRARY_PATH:-}}" && '
        if cuda_home
        else ""
    )
    graspvla_server_bootstrap = _graspvla_server_bootstrap_command(cluster_config, method_config, run_dir)
    graspvla_server_bootstrap = f"{graspvla_server_bootstrap} && " if graspvla_server_bootstrap else ""
    return (
        f'mkdir -p "{run_dir}" && '
        f'source "{miniforge_root}/etc/profile.d/conda.sh" && '
        f'conda activate "{env_prefix}" && '
        f'cd "{remote_root}" && '
        f'{_libero_config_command(remote_root, libero_config_root)} && '
        f'mkdir -p "{cache_root}/huggingface" "{cache_root}/torch" "{cache_root}/torch_extensions" && '
        f'{cuda_exports}'
        f'export XDG_CACHE_HOME="{cache_root}" && '
        f'export HF_HOME="{cache_root}/huggingface" && '
        f'export TORCH_HOME="{cache_root}/torch" && '
        f'export TORCH_EXTENSIONS_DIR="{cache_root}/torch_extensions" && '
        f'export LIBERO_CONFIG_PATH="{libero_config_root}" && '
        f'export GRASP_BENCHMARK_CLUSTER_CONFIG="{cluster_config_name}" && '
        f'export GB_FAULTHANDLER_PATH="{run_dir}/faulthandler.log" && '
        f'export PYTHONUNBUFFERED=1 && '
        f'export PYTHONPATH="{remote_root}/src${{PYTHONPATH:+:${{PYTHONPATH}}}}" && '
        f'{graspvla_server_bootstrap}'
        f'python -u -m grasp_benchmark.run.worker '
        f'--cluster-config "{cluster_config_name}" '
        f'--method "{method_config["name"]}" '
        f'--task-set "{task_set}" '
        f'--sensor-config "{sensor_config}" '
        f'--output-dir "{run_dir}" '
        f'--execution-mode "{execution_mode}" '
        f'{shard_index_flag} '
        f'{shard_count_flag} '
        f'{gpu_flag} '
        f'{parent_flag} '
        f'{trace_steps_flag} '
        f'{segmentation_mode_flag} '
        f'{oracle_grasp_mode_flag} '
        f'{native_multiview_flag} '
        f'{max_trials_flag} '
        f'{smoke_flag} '
        f'> "{run_dir}/worker_stdout.log" 2> "{run_dir}/worker_stderr.log"'
    ).strip()


def _cluster_setup_commands(cluster_config: dict) -> list[str]:
    commands: list[str] = []
    for source_file in cluster_config.get("source_files", []):
        quoted_source = shlex.quote(str(source_file))
        commands.append(f"if [ -f {quoted_source} ]; then . {quoted_source}; fi")
    for module_name in cluster_config.get("module_loads", []):
        commands.append(f"module load {shlex.quote(str(module_name))}")
    return commands


def _wrap_scheduler_command(cluster_config: dict, remote_command: str) -> str:
    scheduler = cluster_config.get("scheduler", {})
    if str(scheduler.get("type", "")).strip().lower() != "slurm":
        return remote_command

    srun_parts = ["srun", "--wait=0", "--kill-on-bad-exit=1"]
    account = str(scheduler.get("account", "")).strip()
    partition = str(scheduler.get("partition", "")).strip()
    gres = str(scheduler.get("gres", "")).strip()
    cpus_per_task = str(scheduler.get("cpus_per_task", "")).strip()
    mem = str(scheduler.get("mem", "")).strip()
    wall_time = str(scheduler.get("time", "")).strip()
    if account:
        srun_parts.extend(["-A", shlex.quote(account)])
    if partition:
        srun_parts.extend(["-p", shlex.quote(partition)])
    if gres:
        srun_parts.append(f"--gres={shlex.quote(gres)}")
    if cpus_per_task:
        srun_parts.append(f"--cpus-per-task={shlex.quote(cpus_per_task)}")
    if mem:
        srun_parts.append(f"--mem={shlex.quote(mem)}")
    if wall_time:
        srun_parts.append(f"--time={shlex.quote(wall_time)}")
    srun_parts.extend(["bash", "-lc", shlex.quote(remote_command)])
    return " && ".join([*_cluster_setup_commands(cluster_config), " ".join(srun_parts)])


def _remote_shell_invocation(remote_command: str) -> str:
    return f"bash -lc {shlex.quote(remote_command)}"


def _fetch_remote_results(node: str, remote_run_dir: str, local_run_dir: Path) -> None:
    ensure_dir(local_run_dir)
    result = run_command(
        [
            "scp",
            "-r",
            f"{node}:{remote_run_dir}/.",
            str(local_run_dir),
        ]
    )
    (local_run_dir / "fetch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (local_run_dir / "fetch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "Failed to fetch remote run directory.")


def _gpu_slots_for_host(record: dict) -> list[str]:
    return [str(index) for index, _name in enumerate(record.get("gpu_names", []))]


def _interleaved_gpu_slots(selected_hosts: list[str], records: dict[str, dict]) -> list[tuple[str, str]]:
    slots_by_host = {host: _gpu_slots_for_host(records[host]) for host in selected_hosts}
    max_slots = max((len(slots) for slots in slots_by_host.values()), default=0)
    ordered: list[tuple[str, str]] = []
    for slot_index in range(max_slots):
        for host in selected_hosts:
            slots = slots_by_host[host]
            if slot_index < len(slots):
                ordered.append((host, slots[slot_index]))
    return ordered


def _build_matrix_shards(
    *,
    method_name: str,
    method_config: dict,
    cluster_config: dict,
    available_nodes: dict,
    task_set: str,
    sensor_config: str,
    execution_mode: str,
    smoke_only: bool,
    max_trials: int,
    parent_run_dir: Path,
    parent_run_id: str,
    explicit_nodes: str,
    explicit_node: str,
    max_shards: int,
    cluster_config_name: str = "default",
    trace_steps: bool = False,
    segmentation_mode: str = "",
    oracle_grasp_mode: str = "",
    native_multiview_fusion: bool = False,
) -> list[DispatchShard]:
    selected_hosts = _select_matrix_hosts(
        method_name=method_name,
        method_config=method_config,
        available_nodes=available_nodes,
        explicit_nodes=explicit_nodes,
        explicit_node=explicit_node,
    )
    records = _available_node_records(available_nodes)
    task_count = len(expand_task_set(load_named_config("tasks", task_set), max_trials=max_trials or None))
    if task_count == 0:
        raise RuntimeError("Resolved zero tasks for this matrix dispatch.")

    slots = _interleaved_gpu_slots(selected_hosts, records)
    if not slots:
        raise RuntimeError("Matrix dispatch could not find any visible GPU slots.")

    shard_count = min(task_count, max_shards or len(slots), len(slots))
    shards: list[DispatchShard] = []
    remote_parent = f'{cluster_config["remote_root"]}/artifacts/runs/{parent_run_dir.name}'
    for shard_index in range(shard_count):
        node, gpu_id = slots[shard_index % len(slots)]
        shard_id = f"shard_{shard_index:03d}"
        local_run_dir = parent_run_dir / "shards" / f"{shard_id}_{node}_gpu{gpu_id}"
        remote_run_dir = f"{remote_parent}/shards/{shard_id}_{node}_gpu{gpu_id}"
        remote_command = _build_remote_command(
            cluster_config=cluster_config,
            method_config=method_config,
            task_set=task_set,
            sensor_config=sensor_config,
            run_dir=remote_run_dir,
            execution_mode=execution_mode,
            smoke_only=smoke_only,
            max_trials=max_trials,
            cluster_config_name=cluster_config_name,
            shard_index=shard_index,
            shard_count=shard_count,
            gpu_id=gpu_id,
            parent_run_id=parent_run_id,
            trace_steps=trace_steps,
            segmentation_mode=segmentation_mode,
            oracle_grasp_mode=oracle_grasp_mode,
            native_multiview_fusion=native_multiview_fusion,
        )
        remote_command = _wrap_scheduler_command(cluster_config, remote_command)
        shards.append(
            DispatchShard(
                shard_index=shard_index,
                shard_count=shard_count,
                node=node,
                gpu_id=gpu_id,
                local_run_dir=local_run_dir,
                remote_run_dir=remote_run_dir,
                remote_command=remote_command,
            )
        )
    return shards


def _write_manifest(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _launch_remote_process(node: str, remote_command: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            node,
            _remote_shell_invocation(remote_command),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _dispatch_matrix(parent_run_dir: Path, shards: list[DispatchShard], manifest: dict) -> None:
    processes: list[tuple[DispatchShard, subprocess.Popen[str]]] = []
    for shard in shards:
        ensure_dir(shard.local_run_dir)
        shard_manifest = {
            "generated_at": manifest["generated_at"],
            "method": manifest["method"],
            "task_set": manifest["task_set"],
            "execution_mode": manifest["execution_mode"],
            "parent_run_id": manifest["parent_run_id"],
            "selected_node": shard.node,
            "gpu_id": shard.gpu_id,
            "shard_index": shard.shard_index,
            "shard_count": shard.shard_count,
            "local_run_dir": str(shard.local_run_dir),
            "remote_run_dir": shard.remote_run_dir,
            "remote_command": shard.remote_command,
            "smoke_only": manifest["smoke_only"],
            "max_trials": manifest["max_trials"],
            "local_commit": manifest["local_commit"],
        }
        _write_manifest(shard.local_run_dir / "dispatch_manifest.json", shard_manifest)
        processes.append((shard, _launch_remote_process(shard.node, shard.remote_command)))

    failures: list[str] = []
    for shard, process in processes:
        stdout, stderr = process.communicate()
        (shard.local_run_dir / "dispatch_stdout.txt").write_text(stdout or "", encoding="utf-8")
        (shard.local_run_dir / "dispatch_stderr.txt").write_text(stderr or "", encoding="utf-8")
        fetch_failure = ""
        try:
            _fetch_remote_results(shard.node, shard.remote_run_dir, shard.local_run_dir)
        except Exception as exc:
            fetch_failure = f"fetch failed: {exc}"
        if process.returncode != 0:
            suffix = f"; {fetch_failure}" if fetch_failure else ""
            failures.append(f"{shard.shard_id}@{shard.node}/gpu{shard.gpu_id}: {stderr or stdout}{suffix}")
            continue
        if fetch_failure:
            failures.append(f"{shard.shard_id}@{shard.node}/gpu{shard.gpu_id}: {fetch_failure}")

    completion = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "parent_run_id": manifest["parent_run_id"],
        "shard_count": len(shards),
        "failure_count": len(failures),
        "failures": failures,
    }
    _write_manifest(parent_run_dir / "matrix_completion.json", completion)
    if failures:
        raise SystemExit("\n".join(failures))


def _dispatch_matrix_sequential(parent_run_dir: Path, shards: list[DispatchShard], manifest: dict) -> None:
    failures: list[str] = []
    for shard in shards:
        ensure_dir(shard.local_run_dir)
        shard_manifest = {
            "generated_at": manifest["generated_at"],
            "method": manifest["method"],
            "task_set": manifest["task_set"],
            "execution_mode": manifest["execution_mode"],
            "parent_run_id": manifest["parent_run_id"],
            "selected_node": shard.node,
            "gpu_id": shard.gpu_id,
            "shard_index": shard.shard_index,
            "shard_count": shard.shard_count,
            "local_run_dir": str(shard.local_run_dir),
            "remote_run_dir": shard.remote_run_dir,
            "remote_command": shard.remote_command,
            "smoke_only": manifest["smoke_only"],
            "max_trials": manifest["max_trials"],
            "local_commit": manifest["local_commit"],
            "matrix_mode": "sequential",
        }
        _write_manifest(shard.local_run_dir / "dispatch_manifest.json", shard_manifest)
        process = _launch_remote_process(shard.node, shard.remote_command)
        stdout, stderr = process.communicate()
        (shard.local_run_dir / "dispatch_stdout.txt").write_text(stdout or "", encoding="utf-8")
        (shard.local_run_dir / "dispatch_stderr.txt").write_text(stderr or "", encoding="utf-8")
        fetch_failure = ""
        try:
            _fetch_remote_results(shard.node, shard.remote_run_dir, shard.local_run_dir)
        except Exception as exc:
            fetch_failure = f"fetch failed: {exc}"
        if process.returncode != 0:
            suffix = f"; {fetch_failure}" if fetch_failure else ""
            failures.append(f"{shard.shard_id}@{shard.node}/gpu{shard.gpu_id}: {stderr or stdout}{suffix}")
            continue
        if fetch_failure:
            failures.append(f"{shard.shard_id}@{shard.node}/gpu{shard.gpu_id}: {fetch_failure}")

    completion = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "parent_run_id": manifest["parent_run_id"],
        "shard_count": len(shards),
        "failure_count": len(failures),
        "failures": failures,
        "matrix_mode": "sequential",
    }
    _write_manifest(parent_run_dir / "matrix_completion.json", completion)
    if failures:
        raise SystemExit("\n".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or dispatch a simulation benchmark run.")
    parser.add_argument("--method", required=True, choices=["graspvla", "anygrasp", "cgn"])
    parser.add_argument("--task-set", required=True)
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    parser.add_argument(
        "--available-nodes",
        default=str(ARTIFACTS_DIR / "preflight" / "available_nodes.json"),
        help="Preflight JSON used for node selection.",
    )
    parser.add_argument("--node", default="", help="Explicit node override.")
    parser.add_argument("--nodes", default="", help="Comma-separated node list for matrix mode.")
    parser.add_argument("--dry-run", action="store_true", help="Write the dispatch manifest without executing it.")
    parser.add_argument("--smoke-only", action="store_true", help="Dispatch the remote worker in smoke-only mode.")
    parser.add_argument("--max-trials", type=int, default=0, help="Optional cap on expanded trial count.")
    parser.add_argument("--trace-steps", action="store_true", help="Ask the remote worker to save per-step diagnostics.")
    parser.add_argument("--segmentation-mode", default="", help="Optional modular perception mode, e.g. oracle_gt.")
    parser.add_argument("--oracle-grasp-mode", default="", help="Optional proposal override mode, e.g. topdown_centroid.")
    parser.add_argument(
        "--native-multiview-fusion",
        action="store_true",
        help="Enable CGN native multi-view fused-depth mode in the remote worker.",
    )
    parser.add_argument("--execution-mode", default="", help="Execution backend to use.")
    parser.add_argument(
        "--cluster-config",
        default="",
        help="Cluster config name under configs/cluster. Defaults to GRASP_BENCHMARK_CLUSTER_CONFIG or default.",
    )
    parser.add_argument("--gpu-id", default="", help="Single-run GPU id forwarded to the remote worker.")
    parser.add_argument("--matrix", action="store_true", help="Dispatch one shard per visible GPU slot.")
    parser.add_argument("--max-shards", type=int, default=0, help="Optional cap on matrix shard count.")
    parser.add_argument(
        "--matrix-mode",
        choices=["parallel", "sequential"],
        default="parallel",
        help="Matrix dispatch strategy. Use sequential for server-backed methods that should shard without concurrent requests.",
    )
    args = parser.parse_args()

    cluster_config_name = resolve_cluster_config_name(args.cluster_config)
    cluster_config = load_cluster_config(cluster_config_name)
    method_config = load_named_config("methods", args.method)
    task_config = load_named_config("tasks", args.task_set)
    sensor_cfg = load_named_config("sensors", args.sensor_config)
    available_nodes = _load_available_nodes(Path(args.available_nodes))
    execution_mode = _resolve_execution_mode(method_config, args.execution_mode)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = _allocate_run_dir(
        ARTIFACTS_DIR / "runs",
        _run_dir_name(timestamp, args.method, args.task_set, execution_mode),
    )

    parent_run_id = run_dir.name
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": args.method,
        "task_set": task_config["name"],
        "execution_mode": execution_mode,
        "sensor_config": sensor_cfg["sensor_stack"],
        "local_run_dir": str(run_dir),
        "smoke_only": args.smoke_only,
        "max_trials": args.max_trials,
        "trace_steps": args.trace_steps,
        "segmentation_mode": args.segmentation_mode,
        "oracle_grasp_mode": args.oracle_grasp_mode,
        "native_multiview_fusion": args.native_multiview_fusion,
        "local_commit": resolve_commit(),
        "matrix_mode": args.matrix_mode if args.matrix else "single",
        "parent_run_id": parent_run_id,
    }

    if args.matrix:
        shards = _build_matrix_shards(
            method_name=args.method,
            method_config=method_config,
            cluster_config=cluster_config,
            available_nodes=available_nodes,
            task_set=args.task_set,
            sensor_config=args.sensor_config,
            execution_mode=execution_mode,
            smoke_only=args.smoke_only,
            max_trials=args.max_trials,
            parent_run_dir=run_dir,
            parent_run_id=parent_run_id,
            explicit_nodes=args.nodes,
            explicit_node=args.node,
            max_shards=args.max_shards,
            cluster_config_name=cluster_config_name,
            trace_steps=args.trace_steps,
            segmentation_mode=args.segmentation_mode,
            oracle_grasp_mode=args.oracle_grasp_mode,
            native_multiview_fusion=args.native_multiview_fusion,
        )
        manifest["shards"] = [
            {
                "shard_index": shard.shard_index,
                "shard_count": shard.shard_count,
                "node": shard.node,
                "gpu_id": shard.gpu_id,
                "local_run_dir": str(shard.local_run_dir),
                "remote_run_dir": shard.remote_run_dir,
                "remote_command": shard.remote_command,
            }
            for shard in shards
        ]
        _write_manifest(run_dir / "dispatch_manifest.json", manifest)
        if args.dry_run:
            print(json.dumps(manifest, indent=2))
            return
        if args.matrix_mode == "sequential":
            _dispatch_matrix_sequential(run_dir, shards, manifest)
        else:
            _dispatch_matrix(run_dir, shards, manifest)
        print(f"Completed matrix dispatch for {parent_run_id}")
        return

    node = _pick_node(method_config, cluster_config, available_nodes, args.node)
    remote_run_dir = f'{cluster_config["remote_root"]}/artifacts/runs/{run_dir.name}'
    remote_command = _build_remote_command(
        cluster_config=cluster_config,
        method_config=method_config,
        task_set=args.task_set,
        sensor_config=args.sensor_config,
        run_dir=remote_run_dir,
        execution_mode=execution_mode,
        smoke_only=args.smoke_only,
        max_trials=args.max_trials,
        cluster_config_name=cluster_config_name,
        shard_index=0,
        shard_count=1,
        gpu_id=args.gpu_id,
        parent_run_id=parent_run_id,
        trace_steps=args.trace_steps,
        segmentation_mode=args.segmentation_mode,
        oracle_grasp_mode=args.oracle_grasp_mode,
        native_multiview_fusion=args.native_multiview_fusion,
    )
    remote_command = _wrap_scheduler_command(cluster_config, remote_command)
    manifest.update(
        {
            "selected_node": node,
            "remote_run_dir": remote_run_dir,
            "remote_command": remote_command,
            "gpu_id": args.gpu_id,
        }
    )
    _write_manifest(run_dir / "dispatch_manifest.json", manifest)

    if args.dry_run:
        print(json.dumps(manifest, indent=2))
        return

    result = run_command(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            node,
            _remote_shell_invocation(remote_command),
        ]
    )
    (run_dir / "dispatch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (run_dir / "dispatch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    fetch_failure = ""
    try:
        _fetch_remote_results(node=node, remote_run_dir=remote_run_dir, local_run_dir=run_dir)
    except Exception as exc:
        fetch_failure = f"fetch failed: {exc}"
    if not result.ok:
        suffix = f"\n{fetch_failure}" if fetch_failure else ""
        raise SystemExit(f"{result.stderr or result.stdout}{suffix}")
    if fetch_failure:
        raise SystemExit(fetch_failure)
    print(result.stdout.strip() or f"Dispatched run to {node}")


if __name__ == "__main__":
    main()
