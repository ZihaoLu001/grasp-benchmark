from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.shell import run_command


def _load_available_nodes(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def _build_remote_command(
    cluster_config: dict,
    method_config: dict,
    task_set: str,
    sensor_config: str,
    run_dir: str,
    smoke_only: bool,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["env_name"]}'
    smoke_flag = "--smoke-only" if smoke_only else ""
    return (
        f'source "{miniforge_root}/etc/profile.d/conda.sh" && '
        f'conda activate "{env_prefix}" && '
        f'cd "{remote_root}" && '
        f'python -m grasp_benchmark.run.worker '
        f'--method "{method_config["name"]}" '
        f'--task-set "{task_set}" '
        f'--sensor-config "{sensor_config}" '
        f'--output-dir "{run_dir}" '
        f'{smoke_flag}'
    ).strip()


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
    parser.add_argument("--dry-run", action="store_true", help="Write the dispatch manifest without executing it.")
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Dispatch the remote worker in smoke-only mode.",
    )
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", args.method)
    task_config = load_named_config("tasks", args.task_set)
    sensor_config = load_named_config("sensors", args.sensor_config)
    available_nodes = _load_available_nodes(Path(args.available_nodes))
    node = _pick_node(method_config, cluster_config, available_nodes, args.node)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = ARTIFACTS_DIR / "runs" / f"{timestamp}_{args.method}_{args.task_set}"
    ensure_dir(run_dir)

    remote_run_dir = f'{cluster_config["remote_root"]}/artifacts/runs/{run_dir.name}'
    remote_command = _build_remote_command(
        cluster_config=cluster_config,
        method_config=method_config,
        task_set=args.task_set,
        sensor_config=args.sensor_config,
        run_dir=remote_run_dir,
        smoke_only=args.smoke_only,
    )
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": args.method,
        "task_set": task_config["name"],
        "sensor_config": sensor_config["sensor_stack"],
        "selected_node": node,
        "local_run_dir": str(run_dir),
        "remote_run_dir": remote_run_dir,
        "remote_command": remote_command,
        "smoke_only": args.smoke_only,
        "local_commit": resolve_commit(),
    }
    (run_dir / "dispatch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

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
    print(result.stdout.strip() or f"Dispatched run to {node}")


if __name__ == "__main__":
    main()
