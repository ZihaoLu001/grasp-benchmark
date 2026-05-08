from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.shell import run_command
from grasp_benchmark.task_specs import TrialSpec, expand_task_set


DIAGNOSTIC_SCENES = {
    "banana_basic": "language_conditioned_single_target_pick__basic__003",
    "red_mug_basic": "language_conditioned_single_target_pick__basic__001",
    "power_drill_distractors": "language_conditioned_single_target_pick__distractors__005",
    "banana_height": "language_conditioned_single_target_pick__height__003",
    "clear_plastic_cup_transparent": "arbitrary_grasping_transparent__transparent__001",
    "glass_bottle_transparent": "arbitrary_grasping_transparent__transparent__002",
}


@dataclass(frozen=True, slots=True)
class DiagnosticVariant:
    name: str
    execution_mode: str
    robot_config_override: str = ""
    lift_threshold_cm: float | None = None
    hold_steps: int | None = None


VARIANTS = (
    DiagnosticVariant(name="A0_shared", execution_mode="track_a_diag_a0"),
    DiagnosticVariant(
        name="A1_extended_finger",
        execution_mode="track_a_diag_a1",
        robot_config_override="third_party/upstreams/GraspVLA-playground/assets/franka_with_extended_finger/franka.yml",
    ),
    DiagnosticVariant(
        name="A2_extended_finger_official_success",
        execution_mode="track_a_diag_a2",
        robot_config_override="third_party/upstreams/GraspVLA-playground/assets/franka_with_extended_finger/franka.yml",
        lift_threshold_cm=10.0,
        hold_steps=1,
    ),
)


def _build_remote_command(
    *,
    cluster_config: dict,
    method_config: dict,
    sensor_config_name: str,
    task_set: str,
    variant: DiagnosticVariant,
    parent_run_id: str,
    remote_output_dir: str,
    scene_ids: str,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["official_sim_env_name"]}'
    robot_flag = (
        f'--robot-config-override "{variant.robot_config_override}" ' if variant.robot_config_override else ""
    )
    lift_flag = f'--lift-threshold-cm "{variant.lift_threshold_cm}" ' if variant.lift_threshold_cm is not None else ""
    hold_flag = f'--hold-steps "{variant.hold_steps}" ' if variant.hold_steps is not None else ""
    remote_root = cluster_config["remote_root"]
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
        f'--scene-ids "{scene_ids}" '
        f'--trace-steps '
        f'--parent-run-id "{parent_run_id}" '
        f'{robot_flag}{lift_flag}{hold_flag}'
    ).strip()


def _fetch_remote_results(node: str, remote_run_dir: str, local_run_dir: Path) -> None:
    ensure_dir(local_run_dir)
    result = run_command(["scp", "-r", f"{node}:{remote_run_dir}/.", str(local_run_dir)])
    (local_run_dir / "fetch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (local_run_dir / "fetch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "Failed to fetch remote diagnostics.")


def _load_selected_trials(task_set: str) -> list[TrialSpec]:
    task_config = load_named_config("tasks", task_set)
    trials = expand_task_set(task_config)
    wanted = set(DIAGNOSTIC_SCENES.values())
    selected = [trial for trial in trials if trial.scene_id in wanted]
    if set(trial.scene_id for trial in selected) != wanted:
        missing = sorted(wanted - {trial.scene_id for trial in selected})
        raise RuntimeError(f"Diagnostic scene ids were not fully resolved: {missing}")
    return selected


def _read_results_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _attempt_payloads(variant_dir: Path) -> list[dict]:
    payloads: list[dict] = []
    for path in sorted((variant_dir / "episodes").glob("*.json")):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def _has_bbox(step: dict) -> bool:
    bbox = step.get("bbox")
    if bbox is None or bbox == "":
        return False
    if isinstance(bbox, list):
        return len(bbox) > 0
    return True


def _attempt_peak_lift(item: dict) -> float:
    peak = float(item.get("lift_cm", 0.0))
    for step in item.get("step_trace", []):
        peak = max(peak, float(step.get("max_lift_cm", 0.0)))
    return peak


def _summarize_variant(variant: DiagnosticVariant, variant_dir: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows = _read_results_csv(variant_dir / "results.csv")
    attempts = _attempt_payloads(variant_dir)
    scene_stats: list[dict[str, object]] = []
    success_count = 0
    max_lifts: list[float] = []
    for row in rows:
        scene_attempts = [item for item in attempts if item.get("scene_id") == row["scene_id"]]
        best_lift = max((_attempt_peak_lift(item) for item in scene_attempts), default=float(row["lift_cm"]))
        bbox_steps = sum(
            1
            for item in scene_attempts
            for step in item.get("step_trace", [])
            if _has_bbox(step)
        )
        contact_steps = sum(
            1
            for item in scene_attempts
            for step in item.get("step_trace", [])
            if step.get("contact")
        )
        slip_attempts = sum(1 for item in scene_attempts if any(step.get("slip") for step in item.get("step_trace", [])))
        success = int(row["success"])
        success_count += success
        max_lifts.append(best_lift)
        scene_stats.append(
            {
                "variant": variant.name,
                "scene_id": row["scene_id"],
                "task": row["task"],
                "condition": row["condition"],
                "object_id": row["object_id"],
                "success": success,
                "attempts": int(row["attempts"]),
                "result_lift_cm": float(row["lift_cm"]),
                "best_attempt_lift_cm": round(best_lift, 4),
                "bbox_steps": bbox_steps,
                "contact_steps": contact_steps,
                "slip_attempts": slip_attempts,
                "failure_reason": row["failure_reason"],
            }
        )
    overall = {
        "variant": variant.name,
        "execution_mode": variant.execution_mode,
        "trial_count": len(rows),
        "successes": success_count,
        "success_rate": round(success_count / len(rows), 4) if rows else 0.0,
        "mean_best_lift_cm": round(sum(max_lifts) / len(max_lifts), 4) if max_lifts else 0.0,
    }
    return scene_stats, overall


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _interpret(overall_rows: list[dict[str, object]]) -> list[str]:
    by_name = {str(row["variant"]): row for row in overall_rows}
    a0 = by_name.get("A0_shared")
    a1 = by_name.get("A1_extended_finger")
    a2 = by_name.get("A2_extended_finger_official_success")
    notes: list[str] = []
    if a0 and a1:
        lift_delta = float(a1["mean_best_lift_cm"]) - float(a0["mean_best_lift_cm"])
        if lift_delta > 1.0:
            notes.append("Extended finger increases lift noticeably, so embodiment / gripper mismatch is a real factor.")
        elif abs(lift_delta) < 0.25:
            notes.append("Switching back to the extended finger changes mean best lift only marginally, so the Track A failure is not explained by the gripper alone.")
    if a1 and a2:
        success_delta = float(a2["success_rate"]) - float(a1["success_rate"])
        lift_delta = float(a2["mean_best_lift_cm"]) - float(a1["mean_best_lift_cm"])
        if success_delta > 0:
            notes.append("Official success rule is easier than the shared Track A rule, so some gap comes from evaluation definition.")
        elif abs(lift_delta) < 0.25:
            notes.append("Relaxing to the official success rule still does not recover any success on the diagnostic set, so the gap is not mainly a threshold artifact.")
    if not notes:
        notes.append("Most of the gap remains even after the ablations, which points to object / scene distribution and control mismatch.")
    return notes


def _write_report(root_dir: Path, scene_rows: list[dict[str, object]], overall_rows: list[dict[str, object]]) -> None:
    report_path = root_dir / "report.md"
    lines = [
        "# GraspVLA Track A Diagnostic Report",
        "",
        "## Variant Summary",
        "",
        "| variant | execution_mode | trial_count | successes | success_rate | mean_best_lift_cm |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in overall_rows:
        lines.append(
            f"| {row['variant']} | {row['execution_mode']} | {row['trial_count']} | {row['successes']} | {row['success_rate']} | {row['mean_best_lift_cm']} |"
        )
    lines.extend(
        [
            "",
            "## Scene Breakdown",
            "",
            "| variant | scene_id | object_id | condition | success | attempts | result_lift_cm | best_attempt_lift_cm | bbox_steps | contact_steps | slip_attempts |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in scene_rows:
        lines.append(
            f"| {row['variant']} | {row['scene_id']} | {row['object_id']} | {row['condition']} | {row['success']} | {row['attempts']} | {row['result_lift_cm']} | {row['best_attempt_lift_cm']} | {row['bbox_steps']} | {row['contact_steps']} | {row['slip_attempts']} |"
        )
    lines.extend(["", "## Diagnostic Note", ""])
    for note in _interpret(overall_rows):
        lines.append(f"- {note}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the GraspVLA Track A diagnostic ablations on lakeshore.")
    parser.add_argument("--node", default="lakeshore")
    parser.add_argument("--task-set", default="track_a_v1")
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    selected_trials = _load_selected_trials(args.task_set)
    scene_ids = ",".join(trial.scene_id for trial in selected_trials)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    parent_run_id = f"{timestamp}_graspvla_track_a_diagnostics"
    local_root = ensure_dir(ARTIFACTS_DIR / "diagnostics" / parent_run_id)
    remote_root = f'{cluster_config["remote_root"]}/artifacts/diagnostics/{parent_run_id}'

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node": args.node,
        "task_set": args.task_set,
        "sensor_config": args.sensor_config,
        "scene_ids": scene_ids,
        "parent_run_id": parent_run_id,
        "variants": [
            {
                "name": variant.name,
                "execution_mode": variant.execution_mode,
                "robot_config_override": variant.robot_config_override,
                "lift_threshold_cm": variant.lift_threshold_cm,
                "hold_steps": variant.hold_steps,
            }
            for variant in VARIANTS
        ],
        "local_commit": resolve_commit(),
    }
    (local_root / "dispatch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for variant in VARIANTS:
        local_variant_dir = ensure_dir(local_root / variant.name)
        remote_variant_dir = f"{remote_root}/{variant.name}"
        remote_command = _build_remote_command(
            cluster_config=cluster_config,
            method_config=method_config,
            sensor_config_name=args.sensor_config,
            task_set=args.task_set,
            variant=variant,
            parent_run_id=parent_run_id,
            remote_output_dir=remote_variant_dir,
            scene_ids=scene_ids,
        )
        result = run_command(["ssh", "-o", "BatchMode=yes", args.node, f"bash -lc '{remote_command}'"])
        (local_variant_dir / "dispatch_stdout.txt").write_text(result.stdout, encoding="utf-8")
        (local_variant_dir / "dispatch_stderr.txt").write_text(result.stderr, encoding="utf-8")
        if not result.ok:
            raise SystemExit(result.stderr or result.stdout)
        _fetch_remote_results(args.node, remote_variant_dir, local_variant_dir)

    scene_rows: list[dict[str, object]] = []
    overall_rows: list[dict[str, object]] = []
    for variant in VARIANTS:
        variant_scene_rows, overall = _summarize_variant(variant, local_root / variant.name)
        scene_rows.extend(variant_scene_rows)
        overall_rows.append(overall)

    _write_csv(local_root / "summary.csv", overall_rows)
    _write_csv(local_root / "scene_breakdown.csv", scene_rows)
    _write_report(local_root, scene_rows, overall_rows)
    (local_root / "summary.json").write_text(
        json.dumps({"overall": overall_rows, "scene_breakdown": scene_rows}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"diagnostic_root": str(local_root), "parent_run_id": parent_run_id}, indent=2))


if __name__ == "__main__":
    main()
