from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.shell import run_command, ssh_run


def _build_remote_script(cluster_config: dict, *, host: str, port: int, timeout: int, skip_offline_test: bool) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    core_env = f'{cluster_config["conda_envs_dir"]}/gb-core'
    remote_artifact_root = f"{remote_root}/artifacts/official"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    remote_run_dir = f"{remote_artifact_root}/{run_id}_graspvla_checks"

    offline_block = ""
    if not skip_offline_test:
        offline_block = f"""
set +e
cd "{remote_root}/third_party/upstreams/GraspVLA"
MPLBACKEND=Agg python -u -m vla_network.scripts.offline_test --port {port} > "{remote_run_dir}/offline_test_stdout.txt" 2> "{remote_run_dir}/offline_test_stderr.txt"
OFFLINE_STATUS=$?
set -e
LATEST_VIS="$(ls -t "{remote_root}/third_party/upstreams/GraspVLA"/visualization/*_visualization.png 2>/dev/null | head -n 1 || true)"
if [ -n "$LATEST_VIS" ]; then
  cp "$LATEST_VIS" "{remote_run_dir}/offline_test_visualization.png"
fi
"""
    else:
        offline_block = """
OFFLINE_STATUS=0
printf 'offline_test skipped\n' > "${REMOTE_RUN_DIR}/offline_test_stdout.txt"
: > "${REMOTE_RUN_DIR}/offline_test_stderr.txt"
"""

    return f"""
set -euo pipefail
source "{miniforge_root}/etc/profile.d/conda.sh"
conda activate "{core_env}"
REMOTE_RUN_DIR="{remote_run_dir}"
mkdir -p "$REMOTE_RUN_DIR"
set +e
cd "{remote_root}/third_party/upstreams/GraspVLA-playground"
python validate_server.py --host "{host}" --port {port} --timeout {timeout} > "$REMOTE_RUN_DIR/validate_server_stdout.txt" 2> "$REMOTE_RUN_DIR/validate_server_stderr.txt"
VALIDATE_STATUS=$?
set -e
{offline_block}
echo "__GB_REMOTE_RUN_DIR__=$REMOTE_RUN_DIR"
echo "__GB_VALIDATE_STATUS__=$VALIDATE_STATUS"
echo "__GB_OFFLINE_STATUS__=$OFFLINE_STATUS"
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run official GraspVLA validation entrypoints on a remote node.")
    parser.add_argument("--node", default="em14")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6666)
    parser.add_argument("--timeout", type=int, default=5)
    parser.add_argument("--skip-offline-test", action="store_true")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    result = ssh_run(
        args.node,
        _build_remote_script(
            cluster_config,
            host=args.host,
            port=args.port,
            timeout=args.timeout,
            skip_offline_test=args.skip_offline_test,
        ),
        timeout=1800,
    )

    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.startswith("__GB_"):
            continue
        key, _, value = line.partition("=")
        parsed[key] = value

    remote_run_dir = parsed.get("__GB_REMOTE_RUN_DIR__", "")
    local_output_dir = ensure_dir(ARTIFACTS_DIR / "official")
    local_run_dir = local_output_dir / f'{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}_{args.node}_graspvla_checks'
    local_run_dir.mkdir(parents=True, exist_ok=True)

    if remote_run_dir:
        fetch = run_command(
            ["scp", "-r", f"{args.node}:{remote_run_dir}/.", str(local_run_dir)],
            timeout=1800,
        )
        if not fetch.ok:
            raise SystemExit(fetch.stderr or fetch.stdout)

    validate_status = int(parsed.get("__GB_VALIDATE_STATUS__", "-1") or -1)
    offline_status = int(parsed.get("__GB_OFFLINE_STATUS__", "-1") or -1)
    checks_ok = result.ok and validate_status == 0 and offline_status == 0

    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node": args.node,
        "host": args.host,
        "port": args.port,
        "timeout": args.timeout,
        "skip_offline_test": args.skip_offline_test,
        "ok": checks_ok,
        "ssh_ok": result.ok,
        "validate_status": validate_status,
        "offline_status": offline_status,
        "remote_run_dir": remote_run_dir,
        "local_run_dir": str(local_run_dir),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    artifact_path = local_run_dir / "summary.json"
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    print(f"Wrote official GraspVLA check artifact to {artifact_path}")

    if not checks_ok:
        raise SystemExit(result.stderr or result.stdout or json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
