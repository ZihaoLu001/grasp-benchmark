from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.audit.graspvla_official_alignment import _load_track_a_cal_reference
from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, PROJECT_ROOT, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.serve.graspvla import (
    _build_remote_launch_script,
    _discover_remote_model,
    _validate_remote_server,
)
from grasp_benchmark.shell import run_command, ssh_run


@dataclass(frozen=True, slots=True)
class BoundaryVariant:
    name: str
    task_set: str
    execution_mode: str
    graspvla_view_mode: str


VARIANTS = (
    BoundaryVariant(
        name="boundary_dual_view",
        task_set="graspvla_boundary_probe_v1",
        execution_mode="track_a_diag_boundary_dual",
        graspvla_view_mode="dual",
    ),
    BoundaryVariant(
        name="boundary_front_only",
        task_set="graspvla_boundary_probe_v1",
        execution_mode="track_a_diag_boundary_front_only",
        graspvla_view_mode="front_only_duplicate",
    ),
)


def _docs_reports_dir() -> Path:
    return PROJECT_ROOT / "docs" / "reports"


def _write_text(path: Path, payload: str, *, encoding: str = "utf-8") -> None:
    ensure_dir(path.parent)
    path.write_text(payload, encoding=encoding)


def _write_json(path: Path, payload: object) -> None:
    _write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _build_remote_command(
    *,
    cluster_config: dict,
    method_config: dict,
    sensor_config_name: str,
    task_set: str,
    variant: BoundaryVariant,
    parent_run_id: str,
    remote_output_dir: str,
    scene_ids: str,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["official_sim_env_name"]}'
    remote_root = cluster_config["remote_root"]
    scene_ids_flag = f' --scene-ids "{scene_ids}"' if scene_ids.strip() else ""
    return (
        f'mkdir -p "{remote_output_dir}" && '
        f'source "{miniforge_root}/etc/profile.d/conda.sh" && '
        f'conda activate "{env_prefix}" && '
        f'cd "{remote_root}" && '
        f'export PYTHONPATH="{remote_root}/src${{PYTHONPATH:+:${{PYTHONPATH}}}}" && '
        f'python -m grasp_benchmark.run.worker '
        f'--method "graspvla" '
        f'--task-set "{task_set}" '
        f'--sensor-config "{sensor_config_name}" '
        f'--output-dir "{remote_output_dir}" '
        f'--execution-mode "{variant.execution_mode}" '
        f'--parent-run-id "{parent_run_id}" '
        f'--graspvla-view-mode "{variant.graspvla_view_mode}"'
        f'{scene_ids_flag}'
    ).strip()


def _ensure_graspvla_server(node: str, cluster_config: dict, method_config: dict) -> dict[str, object]:
    ok, payload = _validate_remote_server(
        host=node,
        cluster_config=cluster_config,
        method_config=method_config,
        port=int(method_config["server"]["port"]),
        timeout_s=10,
        retries=2,
        retry_sleep_s=2,
    )
    if ok:
        return {"status": "already_healthy", "validation": payload}

    model_path = _discover_remote_model(node, method_config)
    if not model_path:
        raise RuntimeError("Could not find a remote GraspVLA model before launching the boundary probe server.")

    launch_script = _build_remote_launch_script(
        cluster_config=cluster_config,
        method_config=method_config,
        model_path=model_path,
        port=int(method_config["server"]["port"]),
        compile_model=bool(method_config["server"].get("compile", True)),
    )
    launch_result = ssh_run(node, launch_script, timeout=120)
    if not launch_result.ok:
        raise RuntimeError(launch_result.stderr or launch_result.stdout or "Failed to launch remote GraspVLA server.")

    ok, payload = _validate_remote_server(
        host=node,
        cluster_config=cluster_config,
        method_config=method_config,
        port=int(method_config["server"]["port"]),
        timeout_s=10,
        retries=60,
        retry_sleep_s=10,
    )
    if not ok:
        raise RuntimeError(
            f"Remote GraspVLA server launch did not validate: {json.dumps(payload, ensure_ascii=False)}"
        )
    pid = launch_result.stdout.strip().splitlines()[-1] if launch_result.stdout.strip() else ""
    return {"status": "launched_and_validated", "pid": pid, "validation": payload}


def _fetch_remote_results(node: str, remote_run_dir: str, local_run_dir: Path) -> None:
    ensure_dir(local_run_dir)
    result = run_command(["scp", "-r", f"{node}:{remote_run_dir}/.", str(local_run_dir)])
    (local_run_dir / "fetch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (local_run_dir / "fetch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "Failed to fetch remote boundary probe outputs.")


def _read_results(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _aggregate(rows: list[dict[str, str]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)
    output: list[dict[str, object]] = []
    for group_key, group_rows in sorted(grouped.items()):
        successes = sum(int(row["success"]) for row in group_rows)
        trials = len(group_rows)
        output_row = {keys[index]: group_key[index] for index in range(len(keys))}
        output_row.update(
            {
                "trials": trials,
                "successes": successes,
                "success_rate": round(successes / trials, 4) if trials else 0.0,
                "mean_attempts": round(sum(float(row["attempts"]) for row in group_rows) / trials, 4) if trials else 0.0,
                "mean_inference_ms": round(sum(float(row["inference_ms"]) for row in group_rows) / trials, 4)
                if trials
                else 0.0,
            }
        )
        output.append(output_row)
    return output


def _variant_summary(variant: BoundaryVariant, rows: list[dict[str, str]]) -> dict[str, object]:
    successes = sum(int(row["success"]) for row in rows)
    trials = len(rows)
    return {
        "variant": variant.name,
        "task_set": variant.task_set,
        "view_mode": variant.graspvla_view_mode,
        "trials": trials,
        "successes": successes,
        "success_rate": round(successes / trials, 4) if trials else 0.0,
        "mean_attempts": round(sum(float(row["attempts"]) for row in rows) / trials, 4) if trials else 0.0,
        "mean_inference_ms": round(sum(float(row["inference_ms"]) for row in rows) / trials, 4) if trials else 0.0,
    }


def _paired_task_delta(
    dual_task_rows: list[dict[str, object]],
    front_task_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    front_lookup = {(str(row["task"]), str(row["condition"])): row for row in front_task_rows}
    rows: list[dict[str, object]] = []
    for row in dual_task_rows:
        key = (str(row["task"]), str(row["condition"]))
        other = front_lookup.get(key)
        if other is None:
            continue
        rows.append(
            {
                "task": key[0],
                "condition": key[1],
                "dual_success_rate": row["success_rate"],
                "front_only_success_rate": other["success_rate"],
                "success_rate_delta": round(float(row["success_rate"]) - float(other["success_rate"]), 4),
            }
        )
    return rows


def _render_report(
    *,
    root_dir: Path,
    track_a_cal_reference: dict[str, object],
    overall_rows: list[dict[str, object]],
    task_rows: list[dict[str, object]],
    task_condition_rows: list[dict[str, object]],
    deltas: list[dict[str, object]],
) -> tuple[str, str]:
    dual_summary = next(row for row in overall_rows if row["variant"] == "boundary_dual_view")
    front_summary = next(row for row in overall_rows if row["variant"] == "boundary_front_only")
    dual_condition_only = [item for item in task_condition_rows if item["variant"] == "boundary_dual_view"]
    transparent_row = next(
        (item for item in dual_condition_only if item["task"] == "arbitrary_grasping_transparent"),
        None,
    )
    weakest_dual_condition = min(
        dual_condition_only,
        key=lambda item: (float(item["success_rate"]), str(item["task"]), str(item["condition"])),
    )
    strongest_view_gap = None
    if deltas:
        strongest_view_gap = max(deltas, key=lambda item: abs(float(item["success_rate_delta"])))

    english_lines = [
        "# GraspVLA Boundary Probe Report",
        "",
        "## Headline",
        "",
        f"- Latest formal Main Shared Grasping Benchmark reference remains `{track_a_cal_reference['graspvla_successes']}/{track_a_cal_reference['graspvla_trials']}`.",
        f"- On the dedicated boundary suite, dual-view GraspVLA reaches `{dual_summary['successes']}/{dual_summary['trials']}`.",
        f"- On the same suite with `front_only_duplicate`, GraspVLA reaches `{front_summary['successes']}/{front_summary['trials']}`.",
        f"- The weakest dual-view slice is `{weakest_dual_condition['task']} / {weakest_dual_condition['condition']}` at `{weakest_dual_condition['successes']}/{weakest_dual_condition['trials']}`.",
        "",
        "## Variant Summary",
        "",
        "| variant | view_mode | trials | successes | success_rate | mean_attempts | mean_inference_ms |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in overall_rows:
        english_lines.append(
            f"| {row['variant']} | {row['view_mode']} | {row['trials']} | {row['successes']} | {row['success_rate']} | {row['mean_attempts']} | {row['mean_inference_ms']} |"
        )
    english_lines.extend(
        [
            "",
            "## Dual-View Task Breakdown",
            "",
            "| task | trials | successes | success_rate | mean_attempts | mean_inference_ms |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in [item for item in task_rows if item["variant"] == "boundary_dual_view"]:
        english_lines.append(
            f"| {row['task']} | {row['trials']} | {row['successes']} | {row['success_rate']} | {row['mean_attempts']} | {row['mean_inference_ms']} |"
        )
    english_lines.extend(
        [
            "",
            "## Dual-View Condition Breakdown",
            "",
            "| task | condition | trials | successes | success_rate |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in [item for item in task_condition_rows if item["variant"] == "boundary_dual_view"]:
        english_lines.append(
            f"| {row['task']} | {row['condition']} | {row['trials']} | {row['successes']} | {row['success_rate']} |"
        )
    english_lines.extend(
        [
            "",
            "## View-Dependence Delta",
            "",
            "| task | condition | dual_success_rate | front_only_success_rate | success_rate_delta |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in deltas:
        english_lines.append(
            f"| {row['task']} | {row['condition']} | {row['dual_success_rate']} | {row['front_only_success_rate']} | {row['success_rate_delta']} |"
        )
    english_lines.extend(
        [
            "",
            "## Interpretation Notes",
            "",
            "- `front_only_duplicate` is a view-ablation proxy that duplicates the front camera into both RGB slots; it is not a retrained single-view checkpoint.",
            f"- On this probe, the main observed hotspot is `{weakest_dual_condition['task']} / {weakest_dual_condition['condition']}`.",
        ]
    )
    if transparent_row is not None:
        if float(transparent_row["success_rate"]) >= 1.0:
            english_lines.append("- The transparent subset does not surface as a failure boundary on the current public-release probe.")
        else:
            english_lines.append(
                f"- The transparent subset behaves as a visible boundary here: `{transparent_row['successes']}/{transparent_row['trials']}`."
            )
    if strongest_view_gap is not None:
        english_lines.append(
            f"- The largest measured view-mode delta is `{strongest_view_gap['task']} / {strongest_view_gap['condition']}` = `{strongest_view_gap['success_rate_delta']}`."
        )

    teacher_lines = [
        "# GraspVLA Boundary Probe Benchmark Summary",
        "",
        "## Main Takeaways",
        "",
        f"- The primary Main Shared Grasping Benchmark reference remains `{track_a_cal_reference['graspvla_successes']}/{track_a_cal_reference['graspvla_trials']}`, which indicates strong shared-calibration performance.",
        f"- On the boundary probe suite, the dual-view result is `{dual_summary['successes']}/{dual_summary['trials']}` and the front-only proxy result is `{front_summary['successes']}/{front_summary['trials']}`.",
        "- This suite is designed to answer three questions:",
        "  - whether condition perturbations cause large drops",
        "  - whether paraphrased instructions remain graspable",
        "  - whether transparent objects are an obvious current boundary",
        f"- The weakest dual-view cell is `{weakest_dual_condition['task']} / {weakest_dual_condition['condition']}`, with `{weakest_dual_condition['successes']}/{weakest_dual_condition['trials']}` successes.",
        "",
        "## Dual-View Strengths",
        "",
    ]
    dual_task_lookup = {str(row["task"]): row for row in task_rows if row["variant"] == "boundary_dual_view"}
    for task_name in (
        "language_conditioned_single_target_pick",
        "language_paraphrase_grab",
        "language_paraphrase_lift",
        "language_paraphrase_pickup",
        "arbitrary_grasping_transparent",
    ):
        row = dual_task_lookup.get(task_name)
        if row is None:
            continue
        teacher_lines.append(
            f"- `{task_name}`: `{row['successes']}/{row['trials']}`, success_rate=`{row['success_rate']}`."
        )
    teacher_lines.extend(["", "## Boundary Signals", ""])
    if transparent_row is not None:
        if float(transparent_row["success_rate"]) >= 1.0:
            teacher_lines.append(
                "- Transparent objects are not a visible boundary in this probe version; the current public release succeeds on all 4 transparent scenes."
            )
        else:
            teacher_lines.append(
                f"- The transparent subset currently scores `arbitrary_grasping_transparent = {transparent_row['successes']}/{transparent_row['trials']}`, which makes transparent objects a visible boundary in this run."
            )
    teacher_lines.append(
        f"- The clearest soft boundary is `{weakest_dual_condition['task']} / {weakest_dual_condition['condition']}`, which corresponds to language-conditioned grasping under background perturbation."
    )
    if strongest_view_gap is not None:
        teacher_lines.append(
            f"- The largest measured view-mode gap appears in `{strongest_view_gap['task']} / {strongest_view_gap['condition']}`, with delta `{strongest_view_gap['success_rate_delta']}`."
        )
    teacher_lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This experiment is not a new primary benchmark leaderboard; it is a GraspVLA capability-boundary probe.",
            "- The primary leaderboard remains the Main Shared Grasping Benchmark.",
            "- The probe helps identify where GraspVLA is stable, where it begins to degrade, and whether drops are associated with view mode, condition perturbation, or instruction generalization.",
            "- `front_only_duplicate` is a single-view proxy experiment, not a retrained single-view model.",
        ]
    )

    report_text = "\n".join(english_lines) + "\n"
    teacher_text = "\n".join(teacher_lines) + "\n"
    _write_text(root_dir / "report.md", report_text)
    _write_text(root_dir / "benchmark_summary.md", teacher_text)
    return report_text, teacher_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GraspVLA boundary probes on lakeshore.")
    parser.add_argument("--node", default="lakeshore")
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    parser.add_argument("--scene-ids", default="", help="Optional comma-separated scene ids for smoke runs.")
    parser.add_argument("--skip-ensure-server", action="store_true")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    parent_run_id = f"{timestamp}_graspvla_boundary_probes"
    local_root = ensure_dir(ARTIFACTS_DIR / "audits" / parent_run_id)
    remote_root = f'{cluster_config["remote_root"]}/artifacts/audits/{parent_run_id}'

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node": args.node,
        "sensor_config": args.sensor_config,
        "parent_run_id": parent_run_id,
        "scene_ids_filter": args.scene_ids,
        "variants": [
            {
                "name": variant.name,
                "task_set": variant.task_set,
                "execution_mode": variant.execution_mode,
                "graspvla_view_mode": variant.graspvla_view_mode,
            }
            for variant in VARIANTS
        ],
        "local_commit": resolve_commit(),
        "track_a_cal_reference": _load_track_a_cal_reference(),
    }
    if not args.skip_ensure_server:
        manifest["server_health"] = _ensure_graspvla_server(args.node, cluster_config, method_config)
    (local_root / "dispatch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    overall_rows: list[dict[str, object]] = []
    task_rows: list[dict[str, object]] = []
    task_condition_rows: list[dict[str, object]] = []

    for variant in VARIANTS:
        local_variant_dir = ensure_dir(local_root / variant.name)
        remote_variant_dir = f"{remote_root}/{variant.name}"
        remote_command = _build_remote_command(
            cluster_config=cluster_config,
            method_config=method_config,
            sensor_config_name=args.sensor_config,
            task_set=variant.task_set,
            variant=variant,
            parent_run_id=parent_run_id,
            remote_output_dir=remote_variant_dir,
            scene_ids=args.scene_ids,
        )
        result = run_command(["ssh", "-o", "BatchMode=yes", args.node, f"bash -lc '{remote_command}'"], timeout=28800)
        (local_variant_dir / "dispatch_stdout.txt").write_text(result.stdout, encoding="utf-8")
        (local_variant_dir / "dispatch_stderr.txt").write_text(result.stderr, encoding="utf-8")
        if not result.ok:
            raise SystemExit(result.stderr or result.stdout)
        _fetch_remote_results(args.node, remote_variant_dir, local_variant_dir)

        rows = _read_results(local_variant_dir / "results.csv")
        overall_rows.append(_variant_summary(variant, rows))
        for row in _aggregate(rows, ["task"]):
            row["variant"] = variant.name
            task_rows.append(row)
        for row in _aggregate(rows, ["task", "condition"]):
            row["variant"] = variant.name
            task_condition_rows.append(row)

    dual_condition_rows = [row for row in task_condition_rows if row["variant"] == "boundary_dual_view"]
    front_condition_rows = [row for row in task_condition_rows if row["variant"] == "boundary_front_only"]
    delta_rows = _paired_task_delta(dual_condition_rows, front_condition_rows)

    _write_csv(local_root / "summary.csv", overall_rows)
    _write_csv(local_root / "task_summary.csv", task_rows)
    _write_csv(local_root / "condition_summary.csv", task_condition_rows)
    _write_csv(local_root / "view_delta.csv", delta_rows)
    report_text, teacher_text = _render_report(
        root_dir=local_root,
        track_a_cal_reference=_load_track_a_cal_reference(),
        overall_rows=overall_rows,
        task_rows=task_rows,
        task_condition_rows=task_condition_rows,
        deltas=delta_rows,
    )
    date_token = datetime.now(timezone.utc).strftime("%Y%m%d")
    docs_dir = _docs_reports_dir()
    _write_text(docs_dir / f"graspvla_boundary_probes_{date_token}.md", report_text)
    _write_text(docs_dir / f"graspvla_boundary_probes_{date_token}_benchmark_summary.md", teacher_text)
    _write_json(
        local_root / "summary.json",
        {
            "overall": overall_rows,
            "task_summary": task_rows,
            "condition_summary": task_condition_rows,
            "view_delta": delta_rows,
            "track_a_cal_reference": _load_track_a_cal_reference(),
            "scene_ids_filter": args.scene_ids,
            "server_health": manifest.get("server_health"),
        },
    )
    print(json.dumps({"audit_root": str(local_root), "parent_run_id": parent_run_id}, indent=2))


if __name__ == "__main__":
    main()
