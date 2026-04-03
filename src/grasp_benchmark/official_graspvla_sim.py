from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.shell import run_command, ssh_run


def _format_benchmarks(benchmarks: list[str]) -> str:
    values = ",".join(benchmarks)
    return f"[{values}]"


def _build_parallel_libero_block(
    *,
    playground_root: str,
    libero_exp: str,
    port: int,
    libero_trial_num: int,
    max_tasks_per_benchmark: int,
    benchmarks: list[str],
    parallel_env_num: int,
) -> str:
    benchmarks_csv = ",".join(benchmarks)
    return f"""
set +e
OUTPUT_DIR="{playground_root}/data/{libero_exp}"
mkdir -p "$OUTPUT_DIR"
export OUTPUT_DIR
export EXP_NAME="{libero_exp}"
export PORT="{port}"
export LIBERO_TRIAL_NUM="{libero_trial_num}"
export MAX_TASKS_PER_BENCHMARK="{max_tasks_per_benchmark}"
export BENCHMARKS_CSV="{benchmarks_csv}"
export PARALLEL_ENV_NUM="{parallel_env_num}"
python - <<'PY'
import json
import os
from pathlib import Path

output_dir = Path(os.environ["OUTPUT_DIR"])
exp_name = os.environ["EXP_NAME"]
port = int(os.environ["PORT"])
trial_num = int(os.environ["LIBERO_TRIAL_NUM"])
max_tasks = int(os.environ["MAX_TASKS_PER_BENCHMARK"])
parallel_env_num = int(os.environ["PARALLEL_ENV_NUM"])
benchmarks = [item.strip() for item in os.environ["BENCHMARKS_CSV"].split(",") if item.strip()]

for index in range(parallel_env_num):
    seeds = list(range(trial_num))[index::parallel_env_num]
    seed_path = output_dir / f"seeds_{{index}}.json"
    seed_path.write_text(json.dumps(seeds), encoding="utf-8")

    config_lines = [
        "# Temporary config for parallel process",
        "defaults:",
        "  - _self_",
        f"name: {{exp_name}}",
        "debug: false",
        f"seed_list_file: {{seed_path.as_posix()}}",
        f"port: {{port}}",
        f"video_save_dir: data/{{exp_name}}/videos",
        f"data_dir: data/{{exp_name}}",
        "benchmarks:",
    ]
    for benchmark in benchmarks:
        config_lines.append(f"  - {{benchmark}}")
    config_lines.append(f"max_tasks_per_benchmark: {{max_tasks}}")
    (output_dir / f"temp_config_{{index}}.yaml").write_text("\\n".join(config_lines) + "\\n", encoding="utf-8")
PY
for i in $(seq 0 $(("$PARALLEL_ENV_NUM" - 1))); do
  python evaluate_libero_tasks.py --config-path="$OUTPUT_DIR" --config-name="temp_config_${{i}}" > "$REMOTE_RUN_DIR/libero_worker_${{i}}_stdout.txt" 2> "$REMOTE_RUN_DIR/libero_worker_${{i}}_stderr.txt" &
done
LIBERO_STATUS=0
for job_pid in $(jobs -p); do
  wait "$job_pid" || LIBERO_STATUS=$?
done
if [ -d "$OUTPUT_DIR" ]; then
  cp -a "$OUTPUT_DIR" "$REMOTE_RUN_DIR/libero_data"
fi
set +e
python misc/get_statistics.py name={libero_exp} > "$REMOTE_RUN_DIR/libero_statistics_stdout.txt" 2> "$REMOTE_RUN_DIR/libero_statistics_stderr.txt"
STATS_STATUS=$?
set -e
if [ -f "{playground_root}/data/{libero_exp}/statistics.txt" ]; then
  cp "{playground_root}/data/{libero_exp}/statistics.txt" "$REMOTE_RUN_DIR/libero_statistics.txt"
fi
"""


def _build_remote_script(
    cluster_config: dict,
    method_config: dict,
    *,
    mode: str,
    port: int,
    playground_trials: int,
    libero_trial_num: int,
    max_tasks_per_benchmark: int,
    benchmarks: list[str],
    exp_name_prefix: str,
    parallel_env_num: int,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    sim_env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config.get("official_sim_env_name", "gb-graspvla-sim")}'
    playground_root = f"{remote_root}/third_party/upstreams/GraspVLA-playground"
    libero_config_root = f"{remote_root}/artifacts/libero_config"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    remote_run_dir = f"{remote_root}/artifacts/official_sim/{run_id}_{mode}"
    playground_exp = f"{exp_name_prefix}_playground"
    libero_exp = f"{exp_name_prefix}_libero"
    benchmark_override = _format_benchmarks(benchmarks)

    if mode in {"playground", "full"}:
        playground_block = f"""
set +e
python playground.py name={playground_exp} trial_num={playground_trials} port={port} > "$REMOTE_RUN_DIR/playground_stdout.txt" 2> "$REMOTE_RUN_DIR/playground_stderr.txt"
PLAYGROUND_STATUS=$?
set -e
if [ -d "{playground_root}/data/{playground_exp}" ]; then
  cp -a "{playground_root}/data/{playground_exp}" "$REMOTE_RUN_DIR/playground_data"
fi
"""
    else:
        playground_block = """
PLAYGROUND_STATUS=0
printf 'playground skipped\n' > "$REMOTE_RUN_DIR/playground_stdout.txt"
: > "$REMOTE_RUN_DIR/playground_stderr.txt"
"""

    if mode in {"libero", "full"} and parallel_env_num > 1:
        libero_block = _build_parallel_libero_block(
            playground_root=playground_root,
            libero_exp=libero_exp,
            port=port,
            libero_trial_num=libero_trial_num,
            max_tasks_per_benchmark=max_tasks_per_benchmark,
            benchmarks=benchmarks,
            parallel_env_num=parallel_env_num,
        )
    elif mode in {"libero", "full"}:
        libero_block = f"""
set +e
python evaluate_libero_tasks.py name={libero_exp} trial_num={libero_trial_num} max_tasks_per_benchmark={max_tasks_per_benchmark} 'benchmarks={benchmark_override}' port={port} > "$REMOTE_RUN_DIR/libero_stdout.txt" 2> "$REMOTE_RUN_DIR/libero_stderr.txt"
LIBERO_STATUS=$?
set -e
if [ -d "{playground_root}/data/{libero_exp}" ]; then
  cp -a "{playground_root}/data/{libero_exp}" "$REMOTE_RUN_DIR/libero_data"
fi
set +e
python misc/get_statistics.py name={libero_exp} > "$REMOTE_RUN_DIR/libero_statistics_stdout.txt" 2> "$REMOTE_RUN_DIR/libero_statistics_stderr.txt"
STATS_STATUS=$?
set -e
if [ -f "{playground_root}/data/{libero_exp}/statistics.txt" ]; then
  cp "{playground_root}/data/{libero_exp}/statistics.txt" "$REMOTE_RUN_DIR/libero_statistics.txt"
fi
"""
    else:
        libero_block = """
LIBERO_STATUS=0
STATS_STATUS=0
printf 'libero skipped\n' > "$REMOTE_RUN_DIR/libero_stdout.txt"
: > "$REMOTE_RUN_DIR/libero_stderr.txt"
printf 'statistics skipped\n' > "$REMOTE_RUN_DIR/libero_statistics_stdout.txt"
: > "$REMOTE_RUN_DIR/libero_statistics_stderr.txt"
"""

    return f"""
set -eo pipefail
source "{miniforge_root}/etc/profile.d/conda.sh"
conda activate "{sim_env_prefix}"
export LIBERO_CONFIG_PATH="{libero_config_root}"
REMOTE_RUN_DIR="{remote_run_dir}"
mkdir -p "$REMOTE_RUN_DIR"
cd "{playground_root}"
{playground_block}
{libero_block}
echo "__GB_REMOTE_RUN_DIR__=$REMOTE_RUN_DIR"
echo "__GB_PLAYGROUND_STATUS__=$PLAYGROUND_STATUS"
echo "__GB_LIBERO_STATUS__=$LIBERO_STATUS"
echo "__GB_STATS_STATUS__=$STATS_STATUS"
"""


def _fetch_remote_results(node: str, remote_run_dir: str, local_run_dir: Path) -> None:
    result = run_command(["scp", "-r", f"{node}:{remote_run_dir}/.", str(local_run_dir)], timeout=14400)
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "Failed to fetch official sim artifacts.")


def _read_optional_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_status(raw_value: str | None, *, data_present: bool) -> int:
    value = (raw_value or "").strip()
    if value:
        return int(value)
    return 0 if data_present else -1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the official GraspVLA simulation entrypoints on a remote node.")
    parser.add_argument("--node", default="em14")
    parser.add_argument("--mode", choices=["playground", "libero", "full"], default="full")
    parser.add_argument("--port", type=int, default=6666)
    parser.add_argument("--playground-trials", type=int, default=1)
    parser.add_argument("--libero-trial-num", type=int, default=1)
    parser.add_argument("--max-tasks-per-benchmark", type=int, default=1)
    parser.add_argument("--benchmarks", default="libero_object,libero_10,libero_goal")
    parser.add_argument("--exp-name-prefix", default="graspvla_official")
    parser.add_argument("--parallel-env-num", type=int, default=1)
    parser.add_argument("--ssh-timeout-seconds", type=int, default=43200)
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    benchmarks = [item.strip() for item in args.benchmarks.split(",") if item.strip()]

    result = ssh_run(
        args.node,
        _build_remote_script(
            cluster_config,
            method_config,
            mode=args.mode,
            port=args.port,
            playground_trials=args.playground_trials,
            libero_trial_num=args.libero_trial_num,
            max_tasks_per_benchmark=args.max_tasks_per_benchmark,
            benchmarks=benchmarks,
            exp_name_prefix=args.exp_name_prefix,
            parallel_env_num=args.parallel_env_num,
        ),
        timeout=args.ssh_timeout_seconds,
    )

    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.startswith("__GB_"):
            continue
        key, _, value = line.partition("=")
        parsed[key] = value

    remote_run_dir = parsed.get("__GB_REMOTE_RUN_DIR__", "")
    local_output_dir = ensure_dir(ARTIFACTS_DIR / "official_sim")
    local_run_dir = local_output_dir / f'{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}_{args.node}_{args.mode}'
    local_run_dir.mkdir(parents=True, exist_ok=True)

    if remote_run_dir:
        _fetch_remote_results(args.node, remote_run_dir, local_run_dir)

    playground_data_present = (local_run_dir / "playground_data").exists()
    libero_data_present = (local_run_dir / "libero_data").exists()
    statistics_present = (local_run_dir / "libero_statistics.txt").exists()
    playground_status = _parse_status(parsed.get("__GB_PLAYGROUND_STATUS__", ""), data_present=playground_data_present)
    libero_status = _parse_status(parsed.get("__GB_LIBERO_STATUS__", ""), data_present=libero_data_present or args.mode == "playground")
    stats_status = _parse_status(parsed.get("__GB_STATS_STATUS__", ""), data_present=statistics_present or args.mode == "playground")
    checks_ok = result.ok and playground_status == 0 and libero_status == 0 and stats_status == 0

    statistics_text = _read_optional_text(local_run_dir / "libero_statistics.txt")
    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "graspvla",
        "track": "track_b_native",
        "reference_type": "native_best_case",
        "node": args.node,
        "mode": args.mode,
        "ok": checks_ok,
        "ssh_ok": result.ok,
        "port": args.port,
        "playground_trials": args.playground_trials,
        "libero_trial_num": args.libero_trial_num,
        "max_tasks_per_benchmark": args.max_tasks_per_benchmark,
        "benchmarks": benchmarks,
        "parallel_env_num": args.parallel_env_num,
        "ssh_timeout_seconds": args.ssh_timeout_seconds,
        "remote_run_dir": remote_run_dir,
        "local_run_dir": str(local_run_dir),
        "playground_data_present": playground_data_present,
        "libero_data_present": libero_data_present,
        "statistics_present": statistics_present,
        "playground_status": playground_status,
        "libero_status": libero_status,
        "stats_status": stats_status,
        "statistics_text": statistics_text,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    artifact_path = local_run_dir / "summary.json"
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    print(f"Wrote official GraspVLA simulation artifact to {artifact_path}")

    if not checks_ok:
        raise SystemExit(result.stderr or result.stdout or json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
