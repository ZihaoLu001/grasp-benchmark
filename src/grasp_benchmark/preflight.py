from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.config import load_cluster_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.shell import CommandResult, ssh_run


@dataclass(slots=True)
class NodeProbe:
    host: str
    pool: str
    status: str
    exit_code: int
    hostname: str = ""
    pwd: str = ""
    disk_available_gb: float | None = None
    gpu_names: list[str] = field(default_factory=list)
    binaries: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    remote_repo_present: bool = False
    miniforge_present: bool = False
    gpu_error: str = ""
    scheduler: dict[str, object] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""


def _build_probe_script(cluster_config: dict) -> str:
    probe_dir = cluster_config["project_disk_probe"]
    remote_root = cluster_config["remote_root"]
    miniforge_root = cluster_config["miniforge_root"]
    all_bins = cluster_config.get("required_bins", []) + cluster_config.get("optional_bins", [])
    source_files = [str(item) for item in cluster_config.get("source_files", [])]
    module_loads = [str(item) for item in cluster_config.get("module_loads", [])]
    scheduler = cluster_config.get("scheduler", {})
    scheduler_type = str(scheduler.get("type", "")).strip().lower()
    lines = [
        "set +e",
        *[
            f'if [ -f "{source_file}" ]; then . "{source_file}" >/dev/null 2>&1 || true; fi'
            for source_file in source_files
        ],
        *[
            f'if command -v module >/dev/null 2>&1; then module load "{module_name}" >/dev/null 2>&1 || true; fi'
            for module_name in module_loads
        ],
        'echo "__GB_HOSTNAME__=$(hostname)"',
        'echo "__GB_PWD__=$(pwd 2>/dev/null)"',
        f'df -Pk "{probe_dir}" 2>/dev/null | tail -n 1 | awk \'{{print "__GB_DISK_AVAILABLE_KB__="$4}}\'',
        'if command -v nvidia-smi >/dev/null 2>&1; then',
        '  gpu_output="$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1)"',
        '  gpu_status=$?',
        '  if [ "${gpu_status}" -eq 0 ]; then',
        '    printf "%s\\n" "${gpu_output}" | while IFS= read -r line; do',
        '      if [ -n "${line}" ]; then echo "__GB_GPU__=${line}"; fi',
        '    done',
        '  else',
        '    echo "__GB_GPU_ERROR__=${gpu_output}"',
        '  fi',
        "fi",
    ]
    for binary in all_bins:
        lines.append(
            f'if command -v "{binary}" >/dev/null 2>&1; then '
            f'echo "__GB_BIN__={binary}:1"; else echo "__GB_BIN__={binary}:0"; fi'
        )
    if scheduler_type == "slurm":
        partition = str(scheduler.get("partition", "")).strip()
        gres = str(scheduler.get("gres", "gpu:1")).strip()
        matrix_slots = int(scheduler.get("matrix_slots", 1) or 1)
        lines.extend(
            [
                'echo "__GB_SCHEDULER__=slurm"',
                f'echo "__GB_SLURM_ACCOUNT__={str(scheduler.get("account", "")).strip()}"',
                f'echo "__GB_SLURM_PARTITION__={partition}"',
                f'echo "__GB_SLURM_GRES__={gres}"',
                'if command -v sinfo >/dev/null 2>&1; then',
                f'  slurm_info="$(sinfo -h -p "{partition}" -o "%G|%t|%N" 2>&1)"',
                '  slurm_status=$?',
                '  echo "__GB_SLURM_PARTITION_STATUS__=${slurm_status}"',
                '  printf "%s\\n" "${slurm_info}" | while IFS= read -r line; do',
                '    if [ -n "${line}" ]; then echo "__GB_SLURM_PARTITION_INFO__=${line}"; fi',
                '  done',
                '  if [ "${slurm_status}" -eq 0 ] && printf "%s\\n" "${slurm_info}" | grep -qi "gpu"; then',
                *[
                    f'    echo "__GB_GPU__=slurm:{partition}:{gres}:slot{slot_index}"'
                    for slot_index in range(matrix_slots)
                ],
                "  fi",
                "fi",
            ]
        )
    lines.extend(
        [
            f'if [ -d "{remote_root}" ]; then echo "__GB_REMOTE_ROOT__=1"; else echo "__GB_REMOTE_ROOT__=0"; fi',
            f'if [ -d "{miniforge_root}" ]; then echo "__GB_MINIFORGE__=1"; else echo "__GB_MINIFORGE__=0"; fi',
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_probe_output(
    host: str,
    pool: str,
    result: CommandResult,
    cluster_config: dict,
) -> NodeProbe:
    combined = "\n".join(part for part in [result.stdout, result.stderr] if part)
    probe = NodeProbe(
        host=host,
        pool=pool,
        status="failed" if result.returncode != 0 else "available",
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )

    if "Host key verification failed" in combined:
        probe.failures.append("host_key_verification_failed")
    if "Could not chdir to home directory /none/ghr" in combined:
        probe.warnings.append("missing_home_directory")

    for line in result.stdout.splitlines():
        if line.startswith("__GB_HOSTNAME__="):
            probe.hostname = line.split("=", 1)[1].strip()
        elif line.startswith("__GB_PWD__="):
            probe.pwd = line.split("=", 1)[1].strip()
        elif line.startswith("__GB_DISK_AVAILABLE_KB__="):
            raw_kb = line.split("=", 1)[1].strip()
            if raw_kb.isdigit():
                probe.disk_available_gb = round(int(raw_kb) / 1024 / 1024, 2)
        elif line.startswith("__GB_GPU__="):
            probe.gpu_names.append(line.split("=", 1)[1].strip())
        elif line.startswith("__GB_GPU_ERROR__="):
            probe.gpu_error = line.split("=", 1)[1].strip()
        elif line.startswith("__GB_SCHEDULER__="):
            probe.scheduler["type"] = line.split("=", 1)[1].strip()
        elif line.startswith("__GB_SLURM_ACCOUNT__="):
            probe.scheduler["account"] = line.split("=", 1)[1].strip()
        elif line.startswith("__GB_SLURM_PARTITION__="):
            probe.scheduler["partition"] = line.split("=", 1)[1].strip()
        elif line.startswith("__GB_SLURM_GRES__="):
            probe.scheduler["gres"] = line.split("=", 1)[1].strip()
        elif line.startswith("__GB_SLURM_PARTITION_STATUS__="):
            raw_status = line.split("=", 1)[1].strip()
            probe.scheduler["partition_status"] = int(raw_status) if raw_status.isdigit() else raw_status
        elif line.startswith("__GB_SLURM_PARTITION_INFO__="):
            probe.scheduler.setdefault("partition_info", [])
            partition_info = probe.scheduler["partition_info"]
            if isinstance(partition_info, list):
                partition_info.append(line.split("=", 1)[1].strip())
        elif line.startswith("__GB_BIN__="):
            name, enabled = line.split("=", 1)[1].split(":", 1)
            probe.binaries[name] = enabled == "1"
        elif line.startswith("__GB_REMOTE_ROOT__="):
            probe.remote_repo_present = line.endswith("1")
        elif line.startswith("__GB_MINIFORGE__="):
            probe.miniforge_present = line.endswith("1")

    for binary in cluster_config.get("required_bins", []):
        if not probe.binaries.get(binary, False):
            probe.failures.append(f"missing_required_binary:{binary}")
    for binary in cluster_config.get("optional_bins", []):
        if not probe.binaries.get(binary, False):
            probe.notes.append(f"missing_optional_binary:{binary}")

    if not probe.remote_repo_present:
        probe.notes.append("remote_repo_missing")
    if not probe.miniforge_present:
        probe.notes.append("shared_miniforge_missing")

    forced_failure = cluster_config.get("known_failures", {}).get(host)
    if forced_failure:
        probe.failures.append(f"configured_failure:{forced_failure}")
    forced_warning = cluster_config.get("known_warnings", {}).get(host)
    if forced_warning:
        probe.warnings.append(f"configured_warning:{forced_warning}")

    if not probe.gpu_names:
        probe.warnings.append("gpu_not_reported")
    if probe.gpu_error:
        probe.notes.append(f"nvidia_smi_error:{probe.gpu_error[:200]}")

    if result.returncode != 0:
        probe.status = "failed"
    elif probe.failures:
        probe.status = "failed"
    elif probe.warnings:
        probe.status = "warning"
    else:
        probe.status = "available"

    return probe


def _probe_host(host: str, pool: str, cluster_config: dict) -> NodeProbe:
    result = ssh_run(host, _build_probe_script(cluster_config))
    return _parse_probe_output(host=host, pool=pool, result=result, cluster_config=cluster_config)


def _write_report(output: Path, probes: list[NodeProbe], pools: list[str]) -> None:
    ensure_dir(output.parent)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pools": pools,
        "nodes": [asdict(probe) for probe in probes],
        "available_hosts": [probe.host for probe in probes if probe.status == "available"],
        "warning_hosts": [probe.host for probe in probes if probe.status == "warning"],
        "dispatch_hosts": [probe.host for probe in probes if probe.status in {"available", "warning"}],
        "failed_hosts": [probe.host for probe in probes if probe.status == "failed"],
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe cluster nodes and build a dispatch whitelist.")
    parser.add_argument("--pool", default="em,rll", help="Comma-separated pool names to probe.")
    parser.add_argument(
        "--cluster-config",
        default="",
        help="Cluster config name under configs/cluster. Defaults to GRASP_BENCHMARK_CLUSTER_CONFIG or default.",
    )
    parser.add_argument(
        "--output",
        default=str(ARTIFACTS_DIR / "preflight" / "available_nodes.json"),
        help="Path to write the preflight JSON report.",
    )
    args = parser.parse_args()

    cluster_config = load_cluster_config(args.cluster_config)
    pools = [pool.strip() for pool in args.pool.split(",") if pool.strip()]
    probes: list[NodeProbe] = []
    for pool in pools:
        hosts = cluster_config["pool_hosts"].get(pool, [])
        for host in hosts:
            probes.append(_probe_host(host=host, pool=pool, cluster_config=cluster_config))

    output = Path(args.output)
    _write_report(output, probes, pools)

    available = [probe.host for probe in probes if probe.status == "available"]
    warning = [probe.host for probe in probes if probe.status == "warning"]
    failed = [probe.host for probe in probes if probe.status == "failed"]
    print(f"Wrote preflight report to {output}")
    print(f"Available: {', '.join(available) if available else 'none'}")
    print(f"Warning: {', '.join(warning) if warning else 'none'}")
    print(f"Failed: {', '.join(failed) if failed else 'none'}")


if __name__ == "__main__":
    main()
