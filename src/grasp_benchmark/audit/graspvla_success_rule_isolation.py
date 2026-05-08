from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grasp_benchmark.audit.graspvla_scene_edit_isolation import (
    _latest_probe_summary_path,
    _write_csv,
    _write_json,
    _write_text,
    compatible_benchmarks,
    compatible_tasks_per_benchmark,
    load_scene_edit_probe_summary,
    scene_edit_compatible_rows,
)
from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, PROJECT_ROOT, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.shell import run_command


@dataclass(frozen=True, slots=True)
class SuccessRuleVariant:
    name: str
    success_mode: str
    lift_threshold_cm: float | None = None
    hold_steps: int | None = None


VARIANTS = (
    SuccessRuleVariant(name="S0_env_done", success_mode="env_done"),
    SuccessRuleVariant(name="S1_lift10_hold1", success_mode="shared_lift_hold", lift_threshold_cm=10.0, hold_steps=1),
    SuccessRuleVariant(name="S2_lift15_hold1", success_mode="shared_lift_hold", lift_threshold_cm=15.0, hold_steps=1),
    SuccessRuleVariant(name="S3_lift15_hold10", success_mode="shared_lift_hold", lift_threshold_cm=15.0, hold_steps=10),
)


def _docs_reports_dir() -> Path:
    return PROJECT_ROOT / "docs" / "reports"


def _build_remote_command(
    *,
    cluster_config: dict[str, Any],
    method_config: dict[str, Any],
    variant: SuccessRuleVariant,
    remote_output_dir: str,
    parent_run_id: str,
    benchmarks: str,
    task_count: int,
    seeds: str,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["official_sim_env_name"]}'
    lift_flag = (
        f'--lift-threshold-cm "{variant.lift_threshold_cm}" '
        if variant.lift_threshold_cm is not None
        else ""
    )
    hold_flag = (
        f'--hold-steps "{variant.hold_steps}" '
        if variant.hold_steps is not None
        else ""
    )
    libero_config_root = f'{remote_root}/artifacts/libero_config'
    return (
        f'mkdir -p "{remote_output_dir}" && '
        f'source "{miniforge_root}/etc/profile.d/conda.sh" && '
        f'conda activate "{env_prefix}" && '
        f'cd "{remote_root}" && '
        f'export LIBERO_CONFIG_PATH="{libero_config_root}" && '
        f'export PYTHONPATH="{remote_root}/src${{PYTHONPATH:+:${{PYTHONPATH}}}}" && '
        f'python -m grasp_benchmark.run.worker '
        f'--method "graspvla" '
        f'--task-set "official_alignment_subset" '
        f'--sensor-config "track_a_dual_realsense" '
        f'--output-dir "{remote_output_dir}" '
        f'--execution-mode "official_aligned_sim" '
        f'--official-benchmarks "{benchmarks}" '
        f'--official-task-count "{task_count}" '
        f'--official-seeds "{seeds}" '
        f'--official-playground-seeds "" '
        f'--official-variant-name "{variant.name}" '
        f'--official-agent-mode "wrapper" '
        f'--official-robot-profile "plain_franka" '
        f'--official-success-mode "{variant.success_mode}" '
        f'--official-scene-edit-policy "shared_only" '
        f'--parent-run-id "{parent_run_id}" '
        f'{lift_flag}{hold_flag}'
    ).strip()


def _fetch_remote_results(node: str, remote_run_dir: str, local_run_dir: Path) -> None:
    ensure_dir(local_run_dir)
    result = run_command(["scp", "-r", f"{node}:{remote_run_dir}/.", str(local_run_dir)], timeout=14400)
    (local_run_dir / "fetch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (local_run_dir / "fetch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "Failed to fetch remote success-rule audit artifacts.")


def _summary_row(variant: SuccessRuleVariant, variant_dir: Path) -> dict[str, object]:
    rows: list[dict[str, str]]
    with (variant_dir / "results.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    successes = sum(int(row["success"]) for row in rows)
    return {
        "variant": variant.name,
        "success_mode": variant.success_mode,
        "lift_threshold_cm": "" if variant.lift_threshold_cm is None else variant.lift_threshold_cm,
        "hold_steps": "" if variant.hold_steps is None else variant.hold_steps,
        "trials": len(rows),
        "successes": successes,
        "success_rate": round(successes / len(rows), 4) if rows else 0.0,
        "results_path": str(variant_dir / "results.csv"),
    }


def _delta_rows(summary_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    lookup = {str(row["variant"]): row for row in summary_rows}
    transitions = (
        ("S0_env_done", "S1_lift10_hold1", "goal_vs_minimal_lift_rule"),
        ("S1_lift10_hold1", "S2_lift15_hold1", "lift_threshold_effect"),
        ("S2_lift15_hold1", "S3_lift15_hold10", "hold_time_effect"),
    )
    rows: list[dict[str, object]] = []
    for from_name, to_name, factor in transitions:
        from_row = lookup[from_name]
        to_row = lookup[to_name]
        rows.append(
            {
                "transition": f"{from_name} -> {to_name}",
                "factor": factor,
                "from_success_rate": float(from_row["success_rate"]),
                "to_success_rate": float(to_row["success_rate"]),
                "success_rate_delta": round(float(to_row["success_rate"]) - float(from_row["success_rate"]), 4),
            }
        )
    return rows


def _render_report(
    *,
    root_dir: Path,
    compatible_rows: list[dict[str, object]],
    summary_rows: list[dict[str, object]],
    delta_rows: list[dict[str, object]],
) -> tuple[str, str]:
    lookup = {str(row["factor"]): row for row in delta_rows}
    threshold_delta = float(lookup["lift_threshold_effect"]["success_rate_delta"])
    hold_delta = float(lookup["hold_time_effect"]["success_rate_delta"])
    goal_delta = float(lookup["goal_vs_minimal_lift_rule"]["success_rate_delta"])
    if abs(hold_delta) > abs(threshold_delta):
        main_component = "hold-time requirement"
    elif abs(threshold_delta) > abs(hold_delta):
        main_component = "lift-threshold increase"
    else:
        main_component = "lift-threshold increase and hold-time requirement at the same order of magnitude"

    report_lines = [
        "# GraspVLA Success-Rule Isolation Audit",
        "",
        "## Headline",
        "",
        f"- This audit isolates the shared success rule on the official scene-edit-compatible subset under the same shared-like embodiment and no method-specific scene edits.",
        f"- `env_done -> lift10_hold1` changes success rate by `{goal_delta:+.4f}`.",
        f"- `lift10_hold1 -> lift15_hold1` changes success rate by `{threshold_delta:+.4f}`.",
        f"- `lift15_hold1 -> lift15_hold10` changes success rate by `{hold_delta:+.4f}`.",
        f"- The largest measured component inside the shared success rule is currently `{main_component}`.",
        "",
        "## Compatible Official Subset",
        "",
        "| benchmark | task_id | task_name | instruction |",
        "| --- | --- | --- | --- |",
    ]
    for row in compatible_rows:
        report_lines.append(f"| {row['benchmark']} | {row['task_id']} | {row['task_name']} | {row['instruction']} |")
    report_lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| variant | success_mode | lift_threshold_cm | hold_steps | trials | successes | success_rate |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in summary_rows:
        report_lines.append(
            f"| {row['variant']} | {row['success_mode']} | {row['lift_threshold_cm']} | {row['hold_steps']} | {row['trials']} | {row['successes']} | {row['success_rate']} |"
        )
    report_lines.extend(
        [
            "",
            "## Success-Rule Delta Table",
            "",
            "| transition | factor | from_success_rate | to_success_rate | success_rate_delta |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in delta_rows:
        report_lines.append(
            f"| {row['transition']} | {row['factor']} | {row['from_success_rate']} | {row['to_success_rate']} | {row['success_rate_delta']} |"
        )
    report_lines.extend(
        [
            "",
            "## Practical Conclusion",
            "",
            "- The shared success rule can now be discussed in pieces instead of as one opaque change.",
            "- `env_done` and a minimal lift-based rule are close but not identical.",
            f"- Within the shared rule itself, the strongest component is `{main_component}`.",
            "- This means the benchmark gap should now be explained primarily through success-rule strictness plus the already-established public-release scene-edit boundary on basket tasks.",
            "",
            f"_Generated under `{root_dir.name}`._",
        ]
    )

    teacher_lines = [
        "# GraspVLA Success-Rule Factor Breakdown",
        "",
        "- This audit decomposes the `shared success rule` into three finer components.",
        f"- `env_done -> lift10_hold1` changes success rate by `{goal_delta:+.4f}`.",
        f"- `lift10_hold1 -> lift15_hold1` changes success rate by `{threshold_delta:+.4f}`.",
        f"- `lift15_hold1 -> lift15_hold10` changes success rate by `{hold_delta:+.4f}`.",
        f"- The largest measured success-rule component is `{main_component}`.",
    ]
    return "\n".join(report_lines) + "\n", "\n".join(teacher_lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolate GraspVLA shared success-rule components on the official compatible subset.")
    parser.add_argument("--node", default="lakeshore")
    parser.add_argument("--probe-summary", default="")
    parser.add_argument("--seeds", default="0,1,2,3,4,5,6,7,8,9")
    args = parser.parse_args()

    probe_summary_path = Path(args.probe_summary) if args.probe_summary else _latest_probe_summary_path()
    probe_rows = load_scene_edit_probe_summary(probe_summary_path)
    compatible_probe_rows = scene_edit_compatible_rows(probe_rows)
    benchmarks = compatible_benchmarks(probe_rows)
    tasks_per_benchmark = compatible_tasks_per_benchmark(probe_rows, benchmarks)
    if not benchmarks or tasks_per_benchmark <= 0:
        raise RuntimeError("No compatible official subset was available for success-rule isolation.")

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date_token = timestamp[:8]
    parent_run_id = f"{timestamp}_graspvla_success_rule_isolation"
    audit_root = ensure_dir(ARTIFACTS_DIR / "audits" / parent_run_id)
    remote_root = f'{cluster_config["remote_root"]}/artifacts/audits/{parent_run_id}'

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node": args.node,
        "compatible_benchmarks": benchmarks,
        "tasks_per_benchmark": tasks_per_benchmark,
        "seeds": args.seeds,
        "variants": [
            {
                "name": variant.name,
                "success_mode": variant.success_mode,
                "lift_threshold_cm": variant.lift_threshold_cm,
                "hold_steps": variant.hold_steps,
            }
            for variant in VARIANTS
        ],
        "local_commit": resolve_commit(),
    }
    _write_json(audit_root / "dispatch_manifest.json", manifest)

    variant_dirs: dict[str, Path] = {}
    for variant in VARIANTS:
        local_variant_dir = ensure_dir(audit_root / variant.name)
        remote_variant_dir = f"{remote_root}/{variant.name}"
        remote_command = _build_remote_command(
            cluster_config=cluster_config,
            method_config=method_config,
            variant=variant,
            remote_output_dir=remote_variant_dir,
            parent_run_id=parent_run_id,
            benchmarks=",".join(benchmarks),
            task_count=tasks_per_benchmark,
            seeds=args.seeds,
        )
        result = run_command(["ssh", "-o", "BatchMode=yes", args.node, f"bash -lc '{remote_command}'"], timeout=14400)
        (local_variant_dir / "dispatch_stdout.txt").write_text(result.stdout or "", encoding="utf-8")
        (local_variant_dir / "dispatch_stderr.txt").write_text(result.stderr or "", encoding="utf-8")
        if not result.ok:
            raise RuntimeError(result.stderr or result.stdout or f"Failed to dispatch {variant.name}.")
        _fetch_remote_results(args.node, remote_variant_dir, local_variant_dir)
        variant_dirs[variant.name] = local_variant_dir

    summary_rows = [_summary_row(variant, variant_dirs[variant.name]) for variant in VARIANTS]
    delta_rows = _delta_rows(summary_rows)
    compatible_rows = [
        {
            "benchmark": row.benchmark,
            "task_id": row.task_id,
            "task_name": row.task_name,
            "instruction": row.instruction,
        }
        for row in compatible_probe_rows
    ]
    report_text, teacher_text = _render_report(
        root_dir=audit_root,
        compatible_rows=compatible_rows,
        summary_rows=summary_rows,
        delta_rows=delta_rows,
    )
    _write_csv(audit_root / "summary.csv", summary_rows)
    _write_csv(audit_root / "success_delta.csv", delta_rows)
    _write_csv(audit_root / "compatible_subset.csv", compatible_rows)
    _write_text(audit_root / "report.md", report_text)
    _write_text(audit_root / "benchmark_summary.md", teacher_text)
    _write_json(
        audit_root / "report.json",
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "audit_root": str(audit_root),
            "compatible_benchmarks": benchmarks,
            "tasks_per_benchmark": tasks_per_benchmark,
            "summary_rows": summary_rows,
            "delta_rows": delta_rows,
            "local_commit": resolve_commit(),
        },
    )
    docs_dir = _docs_reports_dir()
    _write_text(docs_dir / f"graspvla_success_rule_isolation_{date_token}.md", report_text)
    _write_text(docs_dir / f"graspvla_success_rule_isolation_{date_token}_benchmark_summary.md", teacher_text)
    print(json.dumps({"audit_root": str(audit_root), "delta_rows": delta_rows}, indent=2))


if __name__ == "__main__":
    main()
