from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path

from grasp_benchmark.adapters import build_adapter
from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import PROJECT_ROOT, ensure_dir
from grasp_benchmark.provenance import resolve_commit


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote benchmark worker scaffold.")
    parser.add_argument("--method", required=True)
    parser.add_argument("--task-set", required=True)
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()

    method_config = load_named_config("methods", args.method)
    sensor_config = load_named_config("sensors", args.sensor_config)
    task_config = load_named_config("tasks", args.task_set)
    adapter = build_adapter(args.method, method_config, sensor_config)

    output_dir = Path(args.output_dir)
    ensure_dir(output_dir)
    payload = {
        "method": args.method,
        "task_set": args.task_set,
        "sensor_config": args.sensor_config,
        "node": socket.gethostname(),
        "project_root": str(PROJECT_ROOT),
        "commit": resolve_commit(PROJECT_ROOT),
        "required_upstreams": adapter.required_upstreams(),
        "missing_upstreams": adapter.validate_project_root(PROJECT_ROOT),
        "task_groups": task_config.get("task_groups", []),
    }

    if not args.smoke_only:
        raise SystemExit(
            "Full benchmark worker execution is not implemented yet. "
            "Run with --smoke-only to validate the remote environment and dispatch path."
        )

    (output_dir / "smoke.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
