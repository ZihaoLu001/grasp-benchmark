from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path

from grasp_benchmark.adapters import build_adapter
from grasp_benchmark.config import load_named_config
from grasp_benchmark.execution import run_integration_suite
from grasp_benchmark.paths import PROJECT_ROOT, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.task_specs import expand_task_set
from grasp_benchmark.types import append_episode_results_csv


def _runtime_config(method_config: dict) -> dict:
    runtime = {"timeout_ms": 10000}
    server = method_config.get("server")
    if isinstance(server, dict):
        runtime.update(server)
    return runtime


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote benchmark worker scaffold.")
    parser.add_argument("--method", required=True)
    parser.add_argument("--task-set", required=True)
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--max-trials", type=int, default=0, help="Optional cap on expanded trial count.")
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

    if args.smoke_only:
        (output_dir / "smoke.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return

    max_trials = args.max_trials or None
    task_specs = expand_task_set(task_config, max_trials=max_trials)
    payload["execution_mode"] = "integration_fixture"
    payload["trial_count"] = len(task_specs)
    payload["task_specs"] = [task_spec.to_task_spec() for task_spec in task_specs]
    (output_dir / "run_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    adapter.setup(_runtime_config(method_config))
    try:
        results = run_integration_suite(
            adapter=adapter,
            sensor_config=sensor_config,
            task_specs=task_specs,
            artifact_dir=output_dir / "episodes",
            node=payload["node"],
            commit=payload["commit"],
        )
    finally:
        adapter.close()

    append_episode_results_csv(output_dir / "results.csv", results)
    summary = {
        "method": args.method,
        "task_set": args.task_set,
        "trial_count": len(results),
        "successes": sum(1 for result in results if result.success),
        "failures": sum(1 for result in results if not result.success),
        "results_path": str(output_dir / "results.csv"),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
