from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.config import load_named_config
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
        return str(method_config.get("official_sim_env_name", method_config["env_name"]))
    return str(method_config["env_name"])


def _run_dir_name(timestamp: str, method: str, task_set: str, execution_mode: str) -> str:
    suffix = "shared_sim" if execution_mode == "shared_track_a_sim" else execution_mode
    return f"{timestamp}_{method}_{task_set}_{suffix}"


def _preferred_matrix_hosts(method_name: str, method_config: dict) -> list[str]:
    if method_name == "cgn":
        return ["rll_6000_1", "rll_6000_2"]
    return [str(item) for item in method_config.get("preferred_nodes", [])]


def _select_matrix_hosts(
    *,
    method_name: str,
    method_config: dict,
    available_nodes: dict,
    explicit_nodes: str,
) -> list[str]:
    records = _available_node_records(available_nodes)
    dispatch_hosts = set(available_nodes.get("dispatch_hosts", []))
    if explicit_nodes:
        requested = [item.strip() for item in explicit_nodes.split(",") if item.strip()]
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
    shard_index: int = 0,
    shard_count: int = 1,
    gpu_id: str = "",
    parent_run_id: str = "",
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{_remote_env_name(method_config, execution_mode)}'
    smoke_flag = "--smoke-only" if smoke_only else ""
    max_trials_flag = f'--max-trials "{max_trials}"' if max_trials > 0 else ""
    shard_index_flag = f'--shard-index "{shard_index}"'
    shard_count_flag = f'--shard-count "{shard_count}"'
    gpu_flag = f'--gpu-id "{gpu_id}"' if gpu_id != "" else ""
    parent_flag = f'--parent-run-id "{parent_run_id}"' if parent_run_id else ""
    return (
        f'mkdir -p "{run_dir}" && '
        f'source "{miniforge_root}/etc/profile.d/conda.sh" && '
        f'conda activate "{env_prefix}" && '
        f'cd "{remote_root}" && '
        f'export PYTHONPATH="{remote_root}/src${{PYTHONPATH:+:${{PYTHONPATH}}}}" && '
        f'python -m grasp_benchmark.run.worker '
        f'--method "{method_config["name"]}" '
        f'--task-set "{task_set}" '
        f'--sensor-config "{sensor_config}" '
        f'--output-dir "{run_dir}" '
        f'--execution-mode "{execution_mode}" '
        f'{shard_index_flag} '
        f'{shard_count_flag} '
        f'{gpu_flag} '
        f'{parent_flag} '
        f'{max_trials_flag} '
        f'{smoke_flag}'
    ).strip()


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
    max_shards: int,
) -> list[DispatchShard]:
    selected_hosts = _select_matrix_hosts(
        method_name=method_name,
        method_config=method_config,
        available_nodes=available_nodes,
        explicit_nodes=explicit_nodes,
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
            shard_index=shard_index,
            shard_count=shard_count,
            gpu_id=gpu_id,
            parent_run_id=parent_run_id,
        )
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
            f"bash -lc '{remote_command}'",
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
        if process.returncode != 0:
            failures.append(f"{shard.shard_id}@{shard.node}/gpu{shard.gpu_id}: {stderr or stdout}")
            continue
        try:
            _fetch_remote_results(shard.node, shard.remote_run_dir, shard.local_run_dir)
        except Exception as exc:
            failures.append(f"{shard.shard_id}@{shard.node}/gpu{shard.gpu_id}: fetch failed: {exc}")

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
    parser.add_argument("--execution-mode", default="", help="Execution backend to use.")
    parser.add_argument("--gpu-id", default="", help="Single-run GPU id forwarded to the remote worker.")
    parser.add_argument("--matrix", action="store_true", help="Dispatch one shard per visible GPU slot.")
    parser.add_argument("--max-shards", type=int, default=0, help="Optional cap on matrix shard count.")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", args.method)
    task_config = load_named_config("tasks", args.task_set)
    sensor_cfg = load_named_config("sensors", args.sensor_config)
    available_nodes = _load_available_nodes(Path(args.available_nodes))
    execution_mode = _resolve_execution_mode(method_config, args.execution_mode)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = ARTIFACTS_DIR / "runs" / _run_dir_name(timestamp, args.method, args.task_set, execution_mode)
    ensure_dir(run_dir)

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
        "local_commit": resolve_commit(),
        "matrix_mode": args.matrix,
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
            max_shards=args.max_shards,
        )
        manifest["shards"] = [
            {
                "shard_index": shard.shard_index,
                "shard_count": shard.shard_count,
                "node": shard.node,
                "gpu_id": shard.gpu_id,
                "local_run_dir": str(shard.local_run_dir),
                "remote_run_dir": shard.remote_run_dir,
            }
            for shard in shards
        ]
        _write_manifest(run_dir / "dispatch_manifest.json", manifest)
        if args.dry_run:
            print(json.dumps(manifest, indent=2))
            return
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
        shard_index=0,
        shard_count=1,
        gpu_id=args.gpu_id,
        parent_run_id=parent_run_id,
    )
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
            f"bash -lc '{remote_command}'",
        ]
    )
    (run_dir / "dispatch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (run_dir / "dispatch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if not result.ok:
        raise SystemExit(result.stderr or result.stdout)
    _fetch_remote_results(node=node, remote_run_dir=remote_run_dir, local_run_dir=run_dir)
    print(result.stdout.strip() or f"Dispatched run to {node}")


if __name__ == "__main__":
    main()
