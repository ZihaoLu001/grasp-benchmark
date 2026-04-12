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
from grasp_benchmark.serve.graspvla import _validate_remote_server
from grasp_benchmark.shell import run_command, ssh_run


@dataclass(frozen=True, slots=True)
class ProtocolVariant:
    name: str
    execution_mode: str
    graspvla_view_mode: str = "dual"
    attempt_budget: int = 3
    lift_threshold_cm: float = 15.0
    hold_steps: int = 10
    camera_jitter_mode: str = ""


VARIANTS = (
    ProtocolVariant(
        name="P0_shared_baseline",
        execution_mode="track_a_diag_protocol_p0",
    ),
    ProtocolVariant(
        name="P1_front_only_duplicate",
        execution_mode="track_a_diag_protocol_p1",
        graspvla_view_mode="front_only_duplicate",
    ),
    ProtocolVariant(
        name="P2_attempt_budget_1",
        execution_mode="track_a_diag_protocol_p2",
        attempt_budget=1,
    ),
    ProtocolVariant(
        name="P3_relaxed_success",
        execution_mode="track_a_diag_protocol_p3",
        lift_threshold_cm=10.0,
        hold_steps=1,
    ),
    ProtocolVariant(
        name="P4_camera_jitter_low",
        execution_mode="track_a_diag_protocol_p4",
        camera_jitter_mode="low",
    ),
)

VARIANT_FACTOR_NAMES = {
    "P1_front_only_duplicate": "view_mode_effect",
    "P2_attempt_budget_1": "attempt_budget_effect",
    "P3_relaxed_success": "success_rule_effect",
    "P4_camera_jitter_low": "camera_jitter_effect",
    "P0_baseline_dual_attempt3_success15_hold2_jitter_none": "baseline",
    "P3_relaxed_success_10cm_1s": "success_rule_effect",
    "P4_low_camera_jitter": "camera_jitter_effect",
}


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


def _ensure_graspvla_server(node: str, cluster_config: dict, method_config: dict) -> dict[str, object]:
    ok, payload = _validate_remote_server(
        host=node,
        cluster_config=cluster_config,
        method_config=method_config,
        port=int(method_config["server"]["port"]),
        timeout_s=10,
        retries=3,
        retry_sleep_s=2,
    )
    if not ok:
        raise RuntimeError(f"Remote GraspVLA server on {node} is not healthy: {json.dumps(payload, ensure_ascii=False)}")
    return payload


def _build_remote_command(
    *,
    cluster_config: dict,
    method_config: dict,
    sensor_config_name: str,
    variant: ProtocolVariant,
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
        f'--task-set "protocol_probe_v2" '
        f'--sensor-config "{sensor_config_name}" '
        f'--output-dir "{remote_output_dir}" '
        f'--execution-mode "{variant.execution_mode}" '
        f'--parent-run-id "{parent_run_id}" '
        f'--graspvla-view-mode "{variant.graspvla_view_mode}" '
        f'--attempt-budget-override "{variant.attempt_budget}" '
        f'--lift-threshold-cm "{variant.lift_threshold_cm}" '
        f'--hold-steps "{variant.hold_steps}" '
        f'--camera-jitter-mode "{variant.camera_jitter_mode}" '
        f'--trace-steps'
        f'{scene_ids_flag}'
    ).strip()


def _fetch_remote_results(node: str, remote_run_dir: str, local_run_dir: Path) -> None:
    ensure_dir(local_run_dir)
    result = run_command(["scp", "-r", f"{node}:{remote_run_dir}/.", str(local_run_dir)], timeout=14400)
    (local_run_dir / "fetch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (local_run_dir / "fetch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "Failed to fetch remote protocol-probe outputs.")


def _read_results(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _aggregate(rows: list[dict[str, str]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)
    output: list[dict[str, object]] = []
    for group_key, group_rows in sorted(grouped.items()):
        trials = len(group_rows)
        successes = sum(int(row["success"]) for row in group_rows)
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
                "mean_cycle_time_s": round(sum(float(row["cycle_time_s"]) for row in group_rows) / trials, 4)
                if trials
                else 0.0,
            }
        )
        output.append(output_row)
    return output


def _variant_summary(variant: ProtocolVariant, rows: list[dict[str, str]]) -> dict[str, object]:
    successes = sum(int(row["success"]) for row in rows)
    trials = len(rows)
    return {
        "variant": variant.name,
        "execution_mode": variant.execution_mode,
        "view_mode": variant.graspvla_view_mode,
        "attempt_budget": variant.attempt_budget,
        "lift_threshold_cm": variant.lift_threshold_cm,
        "hold_steps": variant.hold_steps,
        "camera_jitter_mode": variant.camera_jitter_mode or "none",
        "trials": trials,
        "successes": successes,
        "success_rate": round(successes / trials, 4) if trials else 0.0,
        "mean_attempts": round(sum(float(row["attempts"]) for row in rows) / trials, 4) if trials else 0.0,
        "mean_inference_ms": round(sum(float(row["inference_ms"]) for row in rows) / trials, 4) if trials else 0.0,
        "mean_cycle_time_s": round(sum(float(row["cycle_time_s"]) for row in rows) / trials, 4) if trials else 0.0,
    }


def _delta_vs_baseline(rows: list[dict[str, object]], keys: list[str]) -> list[dict[str, object]]:
    baseline = [row for row in rows if str(row.get("variant")) == "P0_shared_baseline"]
    baseline_lookup = {
        tuple(str(row.get(key, "")) for key in keys): row
        for row in baseline
    }
    deltas: list[dict[str, object]] = []
    for row in rows:
        variant = str(row.get("variant", ""))
        if variant == "P0_shared_baseline":
            continue
        lookup_key = tuple(str(row.get(key, "")) for key in keys)
        baseline_row = baseline_lookup.get(lookup_key)
        if baseline_row is None:
            continue
        delta_row = {"variant": variant}
        for key in keys:
            delta_row[key] = row.get(key, "")
        delta_row.update(
            {
                "baseline_success_rate": baseline_row["success_rate"],
                "variant_success_rate": row["success_rate"],
                "success_rate_delta": round(float(row["success_rate"]) - float(baseline_row["success_rate"]), 4),
                "baseline_mean_attempts": baseline_row["mean_attempts"],
                "variant_mean_attempts": row["mean_attempts"],
            }
        )
        deltas.append(delta_row)
    return deltas


def _delta_rows(summary_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    baseline_row = next((row for row in summary_rows if str(row.get("variant", "")).startswith("P0_")), None)
    if baseline_row is None:
        raise ValueError("Protocol probe delta rows require a baseline variant that starts with 'P0_'.")
    baseline_success_rate = float(baseline_row.get("success_rate", 0.0))
    deltas: list[dict[str, object]] = []
    for row in summary_rows:
        variant = str(row.get("variant", "")).strip()
        if variant.startswith("P0_"):
            continue
        variant_success_rate = float(row.get("success_rate", 0.0))
        deltas.append(
            {
                "variant": variant,
                "factor": VARIANT_FACTOR_NAMES.get(variant, variant.lower()),
                "baseline_success_rate": baseline_success_rate,
                "variant_success_rate": variant_success_rate,
                "success_rate_delta": round(variant_success_rate - baseline_success_rate, 4),
            }
        )
    return deltas


def _render_report(
    *,
    root_dir: Path,
    track_a_cal_reference: dict[str, object],
    overall_rows: list[dict[str, object]],
    task_rows: list[dict[str, object]],
    condition_rows: list[dict[str, object]],
    delta_rows: list[dict[str, object]],
    factor_rows: list[dict[str, object]],
) -> tuple[str, str]:
    baseline_row = next(row for row in overall_rows if row["variant"] == "P0_shared_baseline")
    weakest_variant = min(
        [row for row in overall_rows if row["variant"] != "P0_shared_baseline"],
        key=lambda row: (float(row["success_rate"]), str(row["variant"])),
    )
    strongest_drop = min(delta_rows, key=lambda row: (float(row["success_rate_delta"]), str(row["variant"]))) if delta_rows else None

    report_lines = [
        "# GraspVLA Protocol Probe v2",
        "",
        "## Headline",
        "",
        f"- Latest formal `Track A-Cal` reference remains `{track_a_cal_reference['graspvla_successes']}/{track_a_cal_reference['graspvla_trials']}`.",
        f"- On the fixed `protocol_probe_v2` suite, the shared baseline reaches `{baseline_row['successes']}/{baseline_row['trials']}`.",
        f"- The weakest single-factor variant is `{weakest_variant['variant']}` at `{weakest_variant['successes']}/{weakest_variant['trials']}`.",
    ]
    if strongest_drop is not None:
        report_lines.append(
            f"- The largest measured drop versus baseline is `{strongest_drop['variant']} / {strongest_drop.get('task', 'overall')} / {strongest_drop.get('condition', '')}` = `{strongest_drop['success_rate_delta']}`."
        )
    report_lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| variant | view_mode | attempt_budget | lift_threshold_cm | hold_steps | camera_jitter_mode | trials | successes | success_rate | mean_attempts | mean_inference_ms | mean_cycle_time_s |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in overall_rows:
        report_lines.append(
            f"| {row['variant']} | {row['view_mode']} | {row['attempt_budget']} | {row['lift_threshold_cm']} | {row['hold_steps']} | {row['camera_jitter_mode']} | {row['trials']} | {row['successes']} | {row['success_rate']} | {row['mean_attempts']} | {row['mean_inference_ms']} | {row['mean_cycle_time_s']} |"
        )
    report_lines.extend(
        [
            "",
            "## By Task",
            "",
            "| variant | task | trials | successes | success_rate | mean_attempts |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in task_rows:
        report_lines.append(
            f"| {row['variant']} | {row['task']} | {row['trials']} | {row['successes']} | {row['success_rate']} | {row['mean_attempts']} |"
        )
    report_lines.extend(
        [
            "",
            "## By Condition",
            "",
            "| variant | task | condition | trials | successes | success_rate |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in condition_rows:
        report_lines.append(
            f"| {row['variant']} | {row['task']} | {row['condition']} | {row['trials']} | {row['successes']} | {row['success_rate']} |"
        )
    report_lines.extend(
        [
            "",
            "## Delta vs Shared Baseline",
            "",
            "| variant | task | condition | baseline_success_rate | variant_success_rate | success_rate_delta | baseline_mean_attempts | variant_mean_attempts |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in delta_rows:
        report_lines.append(
            f"| {row['variant']} | {row.get('task', '')} | {row.get('condition', '')} | {row['baseline_success_rate']} | {row['variant_success_rate']} | {row['success_rate_delta']} | {row['baseline_mean_attempts']} | {row['variant_mean_attempts']} |"
        )
    report_lines.extend(
        [
            "",
            "## Factor Deltas",
            "",
            "| factor | variant | baseline_success_rate | variant_success_rate | success_rate_delta |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in factor_rows:
        report_lines.append(
            f"| {row['factor']} | {row['variant']} | {row['baseline_success_rate']} | {row['variant_success_rate']} | {row['success_rate_delta']} |"
        )
    report_lines.extend(["", f"_Generated under `{root_dir.name}`._"])

    teacher_lines = [
        "# GraspVLA protocol probe v2 总结",
        "",
        f"- 当前正式 `Track A-Cal` 参考仍然是 `{track_a_cal_reference['graspvla_successes']}/{track_a_cal_reference['graspvla_trials']}`。",
        f"- 在固定的 `protocol_probe_v2` 套件上，共享基线 `P0_shared_baseline` 的结果是 `{baseline_row['successes']}/{baseline_row['trials']}`。",
        f"- 这组 probe 只改四类协议因素：视角、attempt budget、success rule、轻微标定扰动。",
        f"- 当前掉得最厉害的单因子版本是 `{weakest_variant['variant']}`，结果是 `{weakest_variant['successes']}/{weakest_variant['trials']}`。",
    ]
    if strongest_drop is not None:
        teacher_lines.append(
            f"- 相对共享基线，最大的 success-rate drop 出现在 `{strongest_drop['variant']} / {strongest_drop.get('task', 'overall')} / {strongest_drop.get('condition', '')}`，差值是 `{strongest_drop['success_rate_delta']}`。"
        )
    teacher_lines.extend(
        [
            "",
            "## 解读口径",
            "",
            "- 这不是新的 benchmark 主榜单，而是 protocol sensitivity audit。",
            "- 它的作用是回答：在不改方法权重的前提下，协议变化会不会改变 GraspVLA 的表现边界。",
            "- 后续论文里这部分进入 audit section，不替代 `Track A-Cal` 主公平表。",
        ]
    )
    return "\n".join(report_lines) + "\n", "\n".join(teacher_lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the GraspVLA protocol probe v2 on em14.")
    parser.add_argument("--node", default="em14")
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    parser.add_argument("--scene-ids", default="", help="Optional comma-separated scene ids for smoke runs.")
    parser.add_argument("--skip-ensure-server", action="store_true")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date_token = timestamp[:8]
    parent_run_id = f"{timestamp}_graspvla_protocol_probe_v2"
    local_root = ensure_dir(ARTIFACTS_DIR / "audits" / parent_run_id)
    remote_root = f'{cluster_config["remote_root"]}/artifacts/audits/{parent_run_id}'

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node": args.node,
        "sensor_config": args.sensor_config,
        "task_set": "protocol_probe_v2",
        "parent_run_id": parent_run_id,
        "scene_ids_filter": args.scene_ids,
        "variants": [
            {
                "name": variant.name,
                "execution_mode": variant.execution_mode,
                "graspvla_view_mode": variant.graspvla_view_mode,
                "attempt_budget": variant.attempt_budget,
                "lift_threshold_cm": variant.lift_threshold_cm,
                "hold_steps": variant.hold_steps,
                "camera_jitter_mode": variant.camera_jitter_mode,
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
    condition_rows: list[dict[str, object]] = []

    for variant in VARIANTS:
        local_variant_dir = ensure_dir(local_root / variant.name)
        remote_variant_dir = f"{remote_root}/{variant.name}"
        remote_command = _build_remote_command(
            cluster_config=cluster_config,
            method_config=method_config,
            sensor_config_name=args.sensor_config,
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
            condition_rows.append(row)

    delta_rows = _delta_vs_baseline(task_rows, ["task"])
    condition_delta_rows = _delta_vs_baseline(condition_rows, ["task", "condition"])
    factor_delta_rows = _delta_rows(overall_rows)
    report_text, teacher_text = _render_report(
        root_dir=local_root,
        track_a_cal_reference=_load_track_a_cal_reference(),
        overall_rows=overall_rows,
        task_rows=task_rows,
        condition_rows=condition_rows,
        delta_rows=condition_delta_rows,
        factor_rows=factor_delta_rows,
    )
    _write_csv(local_root / "summary.csv", overall_rows)
    _write_csv(local_root / "task_summary.csv", task_rows)
    _write_csv(local_root / "condition_summary.csv", condition_rows)
    _write_csv(local_root / "task_delta_vs_baseline.csv", delta_rows)
    _write_csv(local_root / "condition_delta_vs_baseline.csv", condition_delta_rows)
    _write_csv(local_root / "factor_delta_vs_baseline.csv", factor_delta_rows)
    _write_text(local_root / "report.md", report_text)
    _write_text(local_root / "teacher_summary_zh.md", teacher_text)
    _write_text(local_root / "teacher_summary_zh_clean.md", teacher_text, encoding="utf-8-sig")
    _write_json(
        local_root / "summary.json",
        {
            "overall": overall_rows,
            "task_summary": task_rows,
            "condition_summary": condition_rows,
            "task_delta_vs_baseline": delta_rows,
            "condition_delta_vs_baseline": condition_delta_rows,
            "factor_delta_vs_baseline": factor_delta_rows,
            "track_a_cal_reference": _load_track_a_cal_reference(),
            "scene_ids_filter": args.scene_ids,
            "server_health": manifest.get("server_health"),
        },
    )
    docs_dir = _docs_reports_dir()
    _write_text(docs_dir / f"graspvla_protocol_probe_v2_{date_token}.md", report_text)
    _write_text(docs_dir / f"graspvla_protocol_probe_v2_{date_token}_zh.md", teacher_text, encoding="utf-8-sig")
    print(json.dumps({"audit_root": str(local_root), "parent_run_id": parent_run_id}, indent=2))


if __name__ == "__main__":
    main()
