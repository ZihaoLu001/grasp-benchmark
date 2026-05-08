from __future__ import annotations

import argparse
import csv
import json
import shlex
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.config import load_cluster_config, load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.run.sim import _build_remote_command


def _run(command: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or f"Command failed: {command!r}")
    return result


def _job_script(*, job_name: str, stdout_path: str, stderr_path: str, remote_command: str, wall_time: str) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "#SBATCH -A cs_yifan16_chi",
            "#SBATCH -p batch_gpu2",
            "#SBATCH --gres=gpu:1",
            "#SBATCH --cpus-per-task=2",
            "#SBATCH --mem=48G",
            f"#SBATCH --time={wall_time}",
            f"#SBATCH -J {job_name}",
            f"#SBATCH -o {stdout_path}",
            f"#SBATCH -e {stderr_path}",
            "set -eo pipefail",
            "source /etc/profile.d/modules.sh >/dev/null 2>&1 || true",
            "module load slurm/lakeshore/23.02.4 >/dev/null 2>&1 || true",
            remote_command,
            "",
        ]
    )


def _finalizer_script(*, slurm_dir: str, summary_payload: dict[str, object]) -> str:
    payload_json = json.dumps(summary_payload, indent=2)
    return f"""#!/usr/bin/env bash
#SBATCH -A cs_yifan16_chi
#SBATCH -p batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH -J fair_sensor_final
#SBATCH -o {slurm_dir}/finalizer_%j.out
#SBATCH -e {slurm_dir}/finalizer_%j.err
set -eo pipefail
python3 - <<'PY'
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

payload = {payload_json}
slurm_dir = Path(payload["slurm_dir"])


def _success(row):
    return str(row.get("success", "")).strip().lower() in {{"1", "true", "yes"}}


def _read_rows(paths):
    rows = []
    missing = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            missing.append(str(path))
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows, missing


def _median(rows, key):
    values = []
    for row in rows:
        try:
            values.append(float(row.get(key, "")))
        except ValueError:
            pass
    return round(float(statistics.median(values)), 4) if values else None


def _summarize(label, paths):
    rows, missing = _read_rows(paths)
    successes = sum(1 for row in rows if _success(row))
    trials = len(rows)
    return {{
        "label": label,
        "successes": successes,
        "trials": trials,
        "success_rate": f"{{(successes / trials * 100.0):.2f}}%" if trials else "0.00%",
        "missing_results": missing,
        "median_inference_ms": _median(rows, "inference_ms"),
        "median_cycle_time_s": _median(rows, "cycle_time_s"),
    }}


summaries = []
for item in payload["experiments"]:
    summaries.append(_summarize(item["label"], item["result_paths"]))

reference_path = Path(payload["repo_root"]) / "configs/results/cgn_shared_protocol_h100_20260508.json"
reference = {{}}
if reference_path.exists():
    reference = json.loads(reference_path.read_text(encoding="utf-8"))

final_summary = {{
    "completed_at": payload["generated_at"],
    "batch": payload["batch"],
    "commit": payload["commit"],
    "claim_boundary": "Sensor/view parity diagnostic for the shared simulator environment; not a replacement for the method-interface headline table.",
    "experiments": summaries,
    "cgn_front_rgbd_reference": reference,
}}
(slurm_dir / "final_summary.json").write_text(json.dumps(final_summary, indent=2), encoding="utf-8")

lines = [
    "# Fair Sensor/View Ablation Summary",
    "",
    f"- commit: {{final_summary['commit']}}",
    f"- claim boundary: {{final_summary['claim_boundary']}}",
    "",
    "| Experiment | Successes / trials | Success rate | Median logged latency | Median cycle time |",
    "| --- | ---: | ---: | ---: | ---: |",
]
for row in summaries:
    latency = "n/a" if row["median_inference_ms"] is None else f"{{row['median_inference_ms']}} ms"
    cycle = "n/a" if row["median_cycle_time_s"] is None else f"{{row['median_cycle_time_s']}} s"
    lines.append(
        f"| {{row['label']}} | {{row['successes']}} / {{row['trials']}} | {{row['success_rate']}} | {{latency}} | {{cycle}} |"
    )
lines.extend([
    "",
    "The existing CGN front-view RGB-D reference remains the tracked shared-protocol result in configs/results/cgn_shared_protocol_h100_20260508.json.",
])
(slurm_dir / "final_summary.md").write_text("\\n".join(lines) + "\\n", encoding="utf-8")
print(json.dumps(final_summary, indent=2))
PY
"""


def _write(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8", newline="\n")


def _submit(node: str, remote_script: str, dependency: str = "") -> str:
    dependency_flag = f"--dependency={dependency}" if dependency else ""
    command = (
        "source /etc/profile.d/modules.sh >/dev/null 2>&1 || true; "
        "module load slurm/lakeshore/23.02.4 >/dev/null 2>&1 || true; "
        f"sbatch --parsable {dependency_flag} {shlex.quote(remote_script)}"
    ).strip()
    result = _run(["ssh", node, command], timeout=60)
    return result.stdout.strip().splitlines()[-1].strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch fair sensor/view ablations on Lakeshore.")
    parser.add_argument("--node", default="lakeshore")
    parser.add_argument("--task-set", default="track_a_cal_v3")
    parser.add_argument("--cluster-config", default="lakeshore")
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    parser.add_argument("--cgn-shards", type=int, default=4)
    args = parser.parse_args()

    cluster_config = load_cluster_config(args.cluster_config)
    repo_root = cluster_config["remote_root"]
    commit = resolve_commit()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch = f"fair_sensor_ablation_{timestamp}_{commit[:7]}"
    local_slurm_dir = ensure_dir(ARTIFACTS_DIR / "slurm" / batch)
    remote_slurm_dir = f"{repo_root}/artifacts/slurm/{batch}"
    remote_runs_root = f"{repo_root}/artifacts/runs"

    graspvla_config = load_named_config("methods", "graspvla")
    cgn_config = load_named_config("methods", "cgn")

    experiments: list[dict[str, object]] = []
    scripts: list[tuple[str, Path, str]] = []

    for view_mode, label, job_suffix in [
        ("front_only_duplicate", "GraspVLA front-only duplicate RGB", "gvl_dup"),
        ("front_only_blank", "GraspVLA front-only blank-side RGB", "gvl_blank"),
    ]:
        run_id = f"{timestamp}_graspvla_{args.task_set}_{view_mode}"
        run_dir = f"{remote_runs_root}/{run_id}"
        remote_command = _build_remote_command(
            cluster_config=cluster_config,
            method_config=graspvla_config,
            task_set=args.task_set,
            sensor_config=args.sensor_config,
            run_dir=run_dir,
            execution_mode="shared_track_a_sim",
            smoke_only=False,
            max_trials=0,
            cluster_config_name=args.cluster_config,
            shard_index=0,
            shard_count=1,
            parent_run_id=run_id,
            graspvla_view_mode=view_mode,
        )
        script_name = f"{job_suffix}.sh"
        script_path = local_slurm_dir / script_name
        _write(
            script_path,
            _job_script(
                job_name=job_suffix,
                stdout_path=f"{remote_slurm_dir}/{job_suffix}_%j.out",
                stderr_path=f"{remote_slurm_dir}/{job_suffix}_%j.err",
                remote_command=remote_command,
                wall_time="04:00:00",
            ),
        )
        scripts.append((label, script_path, f"{remote_slurm_dir}/{script_name}"))
        experiments.append({"label": label, "result_paths": [f"{run_dir}/results.csv"]})

    cgn_parent = f"{timestamp}_cgn_{args.task_set}_two_view_fused"
    cgn_result_paths = []
    for shard_index in range(args.cgn_shards):
        shard_id = f"shard_{shard_index:03d}"
        run_dir = f"{remote_runs_root}/{cgn_parent}/shards/{shard_id}_lakeshore_gpu{shard_index}"
        cgn_result_paths.append(f"{run_dir}/results.csv")
        remote_command = _build_remote_command(
            cluster_config=cluster_config,
            method_config=cgn_config,
            task_set=args.task_set,
            sensor_config=args.sensor_config,
            run_dir=run_dir,
            execution_mode="shared_track_a_sim",
            smoke_only=False,
            max_trials=0,
            cluster_config_name=args.cluster_config,
            shard_index=shard_index,
            shard_count=args.cgn_shards,
            gpu_id=str(shard_index),
            parent_run_id=cgn_parent,
            trace_steps=True,
            native_multiview_fusion=True,
        )
        script_name = f"cgn_fused_{shard_index:03d}.sh"
        script_path = local_slurm_dir / script_name
        _write(
            script_path,
            _job_script(
                job_name=f"cgn_fused_{shard_index}",
                stdout_path=f"{remote_slurm_dir}/cgn_fused_{shard_index:03d}_%j.out",
                stderr_path=f"{remote_slurm_dir}/cgn_fused_{shard_index:03d}_%j.err",
                remote_command=remote_command,
                wall_time="04:00:00",
            ),
        )
        scripts.append((f"CGN two-view fused shard {shard_index}", script_path, f"{remote_slurm_dir}/{script_name}"))
    experiments.append({"label": "Contact-GraspNet two-view fused RGB-D", "result_paths": cgn_result_paths})

    finalizer_path = local_slurm_dir / "finalizer.sh"
    finalizer_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch": batch,
        "commit": commit,
        "repo_root": repo_root,
        "slurm_dir": remote_slurm_dir,
        "experiments": experiments,
    }
    _write(finalizer_path, _finalizer_script(slurm_dir=remote_slurm_dir, summary_payload=finalizer_payload))

    _run(["ssh", args.node, f'mkdir -p "{remote_slurm_dir}"'], timeout=60)
    _run(["scp", "-r", f"{local_slurm_dir}/.", f"{args.node}:{remote_slurm_dir}/"], timeout=120)

    submitted: list[dict[str, str]] = []
    dependency = ""
    for label, _local_script, remote_script in scripts:
        job_id = _submit(args.node, remote_script, dependency=dependency)
        submitted.append({"label": label, "job_id": job_id, "script": remote_script})
        dependency = f"afterany:{job_id}"
    finalizer_job_id = _submit(args.node, f"{remote_slurm_dir}/finalizer.sh", dependency=dependency)

    manifest = {
        "batch": batch,
        "commit": commit,
        "slurm_dir": remote_slurm_dir,
        "experiments": experiments,
        "jobs": submitted,
        "finalizer_job_id": finalizer_job_id,
    }
    _write(local_slurm_dir / "manifest.json", json.dumps(manifest, indent=2))
    _write(
        local_slurm_dir / "manifest.tsv",
        "job_id\tlabel\tscript\n"
        + "\n".join(f"{item['job_id']}\t{item['label']}\t{item['script']}" for item in submitted)
        + f"\n{finalizer_job_id}\tfinalizer\t{remote_slurm_dir}/finalizer.sh\n",
    )
    _run(["scp", str(local_slurm_dir / "manifest.json"), str(local_slurm_dir / "manifest.tsv"), f"{args.node}:{remote_slurm_dir}/"], timeout=120)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
