from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.report.stats import build_pair_matrix, exact_mcnemar, paired_bootstrap_delta, wilson_ci


NUMERIC_FIELDS = {
    "attempts": int,
    "success": int,
    "lift_cm": float,
    "hold_s": float,
    "spl": float,
    "inference_ms": float,
    "cycle_time_s": float,
    "collision": int,
    "replicate_index": int,
    "seed": int,
    "grounding_success": int,
    "mask_nonempty": int,
    "proposal_nonempty": int,
    "plan_success": int,
    "lift_only_success": int,
    "hold_success": int,
    "slip_after_lift": int,
    "collision_count": int,
    "wrong_object": int,
    "wrong_part": int,
}

HEADLINE_TIER_ORDER = [
    "graspvla_official",
    "cgn_full_modular",
    "anygrasp_full_modular",
]

STAGE_METRIC_FIELDS = [
    "grounding_success",
    "mask_nonempty",
    "proposal_nonempty",
    "plan_success",
    "lift_only_success",
    "hold_success",
    "slip_after_lift",
    "collision_count",
    "wrong_object",
    "wrong_part",
]


def _infer_method_tier(row: dict[str, object]) -> str:
    explicit = str(row.get("method_tier", "")).strip()
    if explicit:
        return explicit
    method = str(row.get("method", "")).strip()
    if method == "graspvla":
        return "graspvla_official"
    if method == "cgn":
        return "cgn_full_modular"
    if method == "anygrasp":
        return "anygrasp_full_modular"
    return "unknown_method_tier"


def _infer_parent_run_id(results_path: Path) -> str:
    parent = results_path.parent
    if parent.parent.name == "shards":
        return parent.parent.parent.name
    return parent.name


def _metadata_path_for_results(results_path: Path) -> Path | None:
    candidates = [results_path.parent / "run_metadata.json"]
    if results_path.parent.parent.name == "shards":
        candidates.append(results_path.parent.parent.parent / "run_metadata.json")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _dispatch_manifest_path_for_results(results_path: Path) -> Path | None:
    candidates = [results_path.parent / "dispatch_manifest.json"]
    if results_path.parent.parent.name == "shards":
        candidates.append(results_path.parent.parent.parent / "dispatch_manifest.json")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _coerce_row(
    row: dict[str, str],
    *,
    metadata: dict[str, object],
    dispatch_manifest: dict[str, object],
    parent_run_id: str,
) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in row.items():
        caster = NUMERIC_FIELDS.get(key)
        if caster is None:
            output[key] = value
        else:
            output[key] = caster(value) if value not in {"", None} else caster(0)
    if not str(output.get("scene_recipe_id", "")).strip():
        output["scene_recipe_id"] = str(output.get("scene_id", "")).strip()
    if int(output.get("replicate_index", 0) or 0) <= 0:
        output["replicate_index"] = 1
    output["parent_run_id"] = str(output.get("parent_run_id", "") or parent_run_id)
    output["method_tier"] = _infer_method_tier(output)
    output["task_set"] = str(metadata.get("task_set", ""))
    output["scene_catalog_name"] = str(metadata.get("scene_catalog_name", metadata.get("scene_catalog", "")))
    dispatch_commit = str(dispatch_manifest.get("local_commit", "")).strip()
    if dispatch_commit:
        output["commit"] = dispatch_commit
    return output


def _iter_result_rows(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("results.csv")):
        metadata_path = _metadata_path_for_results(path)
        metadata: dict[str, object] = {}
        if metadata_path is not None:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                metadata = payload
        dispatch_manifest_path = _dispatch_manifest_path_for_results(path)
        dispatch_manifest: dict[str, object] = {}
        if dispatch_manifest_path is not None:
            payload = json.loads(dispatch_manifest_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                dispatch_manifest = payload
        parent_run_id = _infer_parent_run_id(path)
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append(
                    _coerce_row(
                        row,
                        metadata=metadata,
                        dispatch_manifest=dispatch_manifest,
                        parent_run_id=parent_run_id,
                    )
                )
    return rows


def _parse_parent_run_ids(value: str) -> list[str]:
    normalized = value.strip().lower()
    if normalized in {"__none__", "none", "null"}:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_parent_run_ids(
    rows: list[dict[str, object]],
    *,
    track: str,
    execution_mode: str,
    explicit: str,
) -> list[str]:
    if explicit:
        return _parse_parent_run_ids(explicit)
    latest = ""
    for row in rows:
        if str(row.get("track", "")).strip() != track:
            continue
        if str(row.get("execution_mode", "")).strip() != execution_mode:
            continue
        candidate = str(row.get("parent_run_id", "")).strip()
        if candidate:
            latest = candidate
    return [latest] if latest else []


def _filter_rows(
    rows: list[dict[str, object]],
    *,
    track: str,
    execution_mode: str,
    parent_run_ids: list[str],
) -> list[dict[str, object]]:
    filtered = [
        row
        for row in rows
        if str(row.get("track", "")).strip() == track and str(row.get("execution_mode", "")).strip() == execution_mode
    ]
    if not parent_run_ids:
        return filtered
    allowed = set(parent_run_ids)
    return [row for row in filtered if str(row.get("parent_run_id", "")).strip() in allowed]


def _headline_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    allowed = set(HEADLINE_TIER_ORDER)
    return [row for row in rows if str(row.get("method_tier", "")).strip() in allowed]


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _aggregate(rows: list[dict[str, object]], group_keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(key, "") for key in group_keys)].append(row)

    summary_rows: list[dict[str, object]] = []
    for key, group in sorted(grouped.items()):
        successes = sum(int(item.get("success", 0)) for item in group)
        trials = len(group)
        wilson_low, wilson_high = wilson_ci(successes, trials)
        row = {group_keys[index]: value for index, value in enumerate(key)}
        row.update(
            {
                "trials": trials,
                "successes": successes,
                "failures": trials - successes,
                "success_rate": round(successes / trials, 4) if trials else 0.0,
                "wilson_ci_low": wilson_low,
                "wilson_ci_high": wilson_high,
                "mean_spl": _mean([float(item.get("spl", 0.0)) for item in group]),
                "mean_attempts": _mean([float(item.get("attempts", 0.0)) for item in group]),
                "mean_inference_ms": _mean([float(item.get("inference_ms", 0.0)) for item in group]),
                "mean_cycle_time_s": _mean([float(item.get("cycle_time_s", 0.0)) for item in group]),
            }
        )
        summary_rows.append(row)
    return summary_rows


def _mean_applicable_metric(group: list[dict[str, object]], key: str) -> tuple[float | str, int]:
    values = [int(item.get(key, -1)) for item in group if int(item.get(key, -1)) >= 0]
    if not values:
        return ("", 0)
    return (round(sum(values) / len(values), 4), len(values))


def _aggregate_stage_metrics(rows: list[dict[str, object]], group_keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(key, "") for key in group_keys)].append(row)
    output: list[dict[str, object]] = []
    for key, group in sorted(grouped.items()):
        row = {group_keys[index]: value for index, value in enumerate(key)}
        row["trials"] = len(group)
        for metric_name in STAGE_METRIC_FIELDS:
            mean_value, applicable = _mean_applicable_metric(group, metric_name)
            row[f"{metric_name}_mean"] = mean_value
            row[f"{metric_name}_applicable"] = applicable
        output.append(row)
    return output


def _instruction_robustness_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return []
    base_groups: dict[tuple[str, str, str, str, int], dict[str, int]] = defaultdict(dict)
    for row in rows:
        variant_family = str(row.get("instruction_variant_family", "")).strip() or "canonical"
        key = (
            str(row.get("method_tier", "")).strip(),
            str(row.get("task", "")).strip(),
            str(row.get("condition", "")).strip(),
            str(row.get("scene_recipe_id", "")).strip(),
            int(row.get("replicate_index", 0) or 0),
        )
        base_groups[key][variant_family] = int(row.get("success", 0))

    summary_groups: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for (method_tier, task, condition, _scene_recipe_id, _replicate_index), family_success in base_groups.items():
        canonical = family_success.get("canonical", 0)
        worst_case = min(family_success.values()) if family_success else 0
        consistency = int(len(set(family_success.values())) == 1) if family_success else 0
        for family, success in family_success.items():
            summary_groups[(method_tier, task, condition, family)].append(
                {
                    "success": success,
                    "canonical_success": canonical,
                    "worst_case_success": worst_case,
                    "consistency": consistency,
                }
            )

    output: list[dict[str, object]] = []
    for (method_tier, task, condition, family), group in sorted(summary_groups.items()):
        trials = len(group)
        success_rate = _mean([float(item["success"]) for item in group])
        canonical_success_rate = _mean([float(item["canonical_success"]) for item in group])
        output.append(
            {
                "method_tier": method_tier,
                "task": task,
                "condition": condition,
                "instruction_variant_family": family,
                "trials": trials,
                "success_rate": success_rate,
                "canonical_success_rate": canonical_success_rate,
                "canonical_to_variant_success_drop": round(success_rate - canonical_success_rate, 4),
                "paraphrase_consistency_rate": _mean([float(item["consistency"]) for item in group]),
                "worst_case_success_rate": _mean([float(item["worst_case_success"]) for item in group]),
            }
        )
    return output


def _sim2real_proxy_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary = _aggregate(rows, ["method_tier", "task", "condition", "shift_family", "shift_severity"])
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in summary:
        grouped[
            (
                str(row.get("method_tier", "")).strip(),
                str(row.get("task", "")).strip(),
                str(row.get("condition", "")).strip(),
            )
        ].append(row)
    for group_rows in grouped.values():
        best_rate = max((float(item.get("success_rate", 0.0)) for item in group_rows), default=0.0)
        for row in group_rows:
            row["perturbation_gap_vs_best"] = round(float(row.get("success_rate", 0.0)) - best_rate, 4)
    return summary


def _rank_stability_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return []
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("task", "")).strip(), str(row.get("condition", "")).strip())].append(row)
    output: list[dict[str, object]] = []
    for (task, condition), group in sorted(grouped.items()):
        by_shift: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for row in group:
            by_shift[str(row.get("shift_family", "")).strip()].append(
                (str(row.get("method_tier", "")).strip(), float(row.get("success_rate", 0.0)))
            )
        orderings = []
        for shift_family, items in sorted(by_shift.items()):
            ordering = tuple(method for method, _score in sorted(items, key=lambda item: (-item[1], item[0])))
            orderings.append((shift_family, ordering))
        output.append(
            {
                "task": task,
                "condition": condition,
                "shift_families": ",".join(shift for shift, _ordering in orderings),
                "rank_stability": int(len({ordering for _shift, ordering in orderings}) <= 1),
            }
        )
    return output


def _failure_taxonomy(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counter = Counter()
    for row in rows:
        if int(row.get("success", 0)):
            continue
        stage = str(row.get("failure_stage", "")).strip() or "task_failure"
        reason = str(row.get("failure_reason", "")).strip() or "unknown"
        counter[(str(row.get("track", "")), str(row.get("method_tier", "")), stage, reason)] += 1
    return [
        {
            "track": track,
            "method_tier": method_tier,
            "failure_stage": stage,
            "failure_reason": reason,
            "count": count,
        }
        for (track, method_tier, stage, reason), count in sorted(counter.items())
    ]


def _pairwise_stats(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    methods = [
        method
        for method in HEADLINE_TIER_ORDER
        if any(str(row.get("method_tier", "")).strip() == method for row in rows)
    ]
    stats_rows: list[dict[str, object]] = []
    for method_a, method_b in combinations(methods, 2):
        matrix = build_pair_matrix(rows, method_a=method_a, method_b=method_b)
        pairs = [(int(a), int(b)) for a, b in matrix["pairs"]]
        n_01 = sum(1 for a, b in pairs if a == 0 and b == 1)
        n_10 = sum(1 for a, b in pairs if a == 1 and b == 0)
        delta = round(sum(b - a for a, b in pairs) / len(pairs), 4) if pairs else 0.0
        ci_low, ci_high = paired_bootstrap_delta(pairs)
        stats_rows.append(
            {
                "method_a": method_a,
                "method_b": method_b,
                "paired_scenes": len(pairs),
                "coverage_complete": int(not matrix["missing_for_a"] and not matrix["missing_for_b"]),
                "missing_for_a": len(matrix["missing_for_a"]),
                "missing_for_b": len(matrix["missing_for_b"]),
                "n_01": n_01,
                "n_10": n_10,
                "mcnemar_p_exact": exact_mcnemar(n_01, n_10),
                "delta_success_rate": delta,
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
            }
        )
    return stats_rows


def _parse_track_b_reference(summary_path: Path) -> list[dict[str, object]]:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    artifact_root = summary_path.parent
    method = str(payload.get("method", "graspvla"))
    track = str(payload.get("track", "track_b_native"))
    rows: list[dict[str, object]] = []

    playground_dir = artifact_root / "playground_data" / "videos"
    if playground_dir.exists():
        video_names = [path.name for path in playground_dir.iterdir() if path.is_file()]
        successes = sum(1 for name in video_names if "success" in name)
        trials = sum(1 for name in video_names if "success" in name or "fail" in name)
        if trials:
            low, high = wilson_ci(successes, trials)
            rows.append(
                {
                    "section": "track_b_reference",
                    "track": track,
                    "method": method,
                    "method_tier": "graspvla_official",
                    "benchmark": "playground",
                    "trials": trials,
                    "successes": successes,
                    "success_rate": round(successes / trials, 4),
                    "wilson_ci_low": low,
                    "wilson_ci_high": high,
                    "source_artifact": str(summary_path),
                }
            )

    pattern = re.compile(r"^(?P<benchmark>[\w_]+): (?P<success>\d+)/(?P<trials>\d+) = (?P<rate>\d+\.\d+)$")
    for line in str(payload.get("statistics_text", "")).splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        successes = int(match.group("success"))
        trials = int(match.group("trials"))
        low, high = wilson_ci(successes, trials)
        rows.append(
            {
                "section": "track_b_reference",
                "track": track,
                "method": method,
                "method_tier": "graspvla_official",
                "benchmark": match.group("benchmark"),
                "trials": trials,
                "successes": successes,
                "success_rate": float(match.group("rate")),
                "wilson_ci_low": low,
                "wilson_ci_high": high,
                "source_artifact": str(summary_path),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(headers: list[str], rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["_No rows._"]
    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        output.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return output


def _load_json(path: str) -> dict[str, object]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _paper_rows(section: str, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        output.append({"section": section, **row})
    return output


def _render_report(
    *,
    cal_summary: list[dict[str, object]],
    cal_by_condition: list[dict[str, object]],
    cal_by_object_group: list[dict[str, object]],
    stress_summary: list[dict[str, object]],
    stress_by_condition: list[dict[str, object]],
    stress_by_object_group: list[dict[str, object]],
    instruction_summary: list[dict[str, object]],
    sim2real_summary: list[dict[str, object]],
    sim2real_rank_stability: list[dict[str, object]],
    phase2_summary: list[dict[str, object]],
    stage_metrics_summary: list[dict[str, object]],
    native_appendix_summary: list[dict[str, object]],
    native_appendix_by_condition: list[dict[str, object]],
    pairwise_stats: list[dict[str, object]],
    failure_taxonomy: list[dict[str, object]],
    track_b_reference: list[dict[str, object]],
    protocol_probe: dict[str, object],
    cgn_bottleneck: dict[str, object],
    alignment_summary: dict[str, object],
    cal_parent_run_ids: list[str],
    stress_parent_run_ids: list[str],
    instruction_parent_run_ids: list[str],
    sim2real_parent_run_ids: list[str],
    phase2_parent_run_ids: list[str],
    native_appendix_parent_run_ids: list[str],
    cal_task_sets: list[str],
    stress_task_sets: list[str],
    instruction_task_sets: list[str],
    sim2real_task_sets: list[str],
    phase2_task_sets: list[str],
    native_appendix_task_sets: list[str],
) -> str:
    cal_label = "Track A-Cal Shared Benchmark"
    stress_label = "Track A-Stress Shared Stress Test"
    protocol_label = "GraspVLA Protocol / Transfer Audit"
    instruction_label = "Instruction Robustness"
    sim2real_label = "Sim-to-Real Proxy Robustness"
    stage_metrics_label = "Stage-Level Diagnostic Metrics"
    phase2_label = "Phase 2 Pilot"
    native_label = "Track B Native-Like Appendix"
    lines = [
        "# CoRL 2026 Simulator Bundle",
        "",
        "## Headline Claims",
        "",
        "- Published/native GraspVLA numbers cannot be used directly as the fair shared benchmark claim.",
        "- Under the frozen shared protocol, public GraspVLA is compared against the public CGN modular lane on the same paired scenes.",
        "- The modular gap should be interpreted with both scoreboard evidence and bottleneck/audit evidence.",
        "",
        f"## {cal_label}",
        "",
    ]
    if cal_parent_run_ids:
        lines.append(f"_parent_run_id(s): `{', '.join(cal_parent_run_ids)}`_")
        lines.append("")
    if cal_task_sets:
        lines.append(f"_task_set(s): `{', '.join(cal_task_sets)}`_")
        lines.append("")
    lines.extend(
        _markdown_table(
            [
                "track",
                "method_tier",
                "task",
                "trials",
                "successes",
                "success_rate",
                "wilson_ci_low",
                "wilson_ci_high",
                "mean_attempts",
                "mean_spl",
                "mean_inference_ms",
                "mean_cycle_time_s",
            ],
            cal_summary,
        )
    )
    lines.extend(["", f"## {cal_label} Pairwise Statistics", ""])
    lines.extend(
        _markdown_table(
            [
                "method_a",
                "method_b",
                "paired_scenes",
                "coverage_complete",
                "n_01",
                "n_10",
                "mcnemar_p_exact",
                "delta_success_rate",
                "bootstrap_ci_low",
                "bootstrap_ci_high",
            ],
            pairwise_stats,
        )
    )
    lines.extend(["", f"## {cal_label} By Condition", ""])
    lines.extend(
        _markdown_table(
            [
                "track",
                "method_tier",
                "task",
                "condition",
                "trials",
                "success_rate",
                "wilson_ci_low",
                "wilson_ci_high",
                "mean_attempts",
            ],
            cal_by_condition,
        )
    )
    lines.extend(["", f"## {cal_label} By Object Group", ""])
    lines.extend(
        _markdown_table(
            [
                "track",
                "method_tier",
                "task",
                "object_group",
                "trials",
                "success_rate",
                "wilson_ci_low",
                "wilson_ci_high",
                "mean_attempts",
            ],
            cal_by_object_group,
        )
    )
    lines.extend(["", f"## {stress_label}", ""])
    if stress_parent_run_ids:
        lines.append(f"_parent_run_id(s): `{', '.join(stress_parent_run_ids)}`_")
        lines.append("")
    if stress_task_sets:
        lines.append(f"_task_set(s): `{', '.join(stress_task_sets)}`_")
        lines.append("")
    lines.extend(
        _markdown_table(
            [
                "track",
                "method_tier",
                "task",
                "trials",
                "successes",
                "success_rate",
                "wilson_ci_low",
                "wilson_ci_high",
                "mean_attempts",
            ],
            stress_summary,
        )
    )
    lines.extend(["", f"## {stress_label} By Condition", ""])
    lines.extend(
        _markdown_table(
            ["track", "method_tier", "task", "condition", "trials", "success_rate", "wilson_ci_low", "wilson_ci_high"],
            stress_by_condition,
        )
    )
    lines.extend(["", f"## {stress_label} By Object Group", ""])
    lines.extend(
        _markdown_table(
            ["track", "method_tier", "task", "object_group", "trials", "success_rate", "wilson_ci_low", "wilson_ci_high"],
            stress_by_object_group,
        )
    )
    lines.extend(["", "## Failure Taxonomy", ""])
    lines.extend(_markdown_table(["track", "method_tier", "failure_stage", "failure_reason", "count"], failure_taxonomy))
    lines.extend(["", f"## {protocol_label}", ""])
    if protocol_probe:
        lines.extend(_markdown_table(["variant", "success_rate", "mean_attempts"], list(protocol_probe.get("overall") or [])))
    else:
        lines.append("_No protocol or transfer-audit summary supplied._")
    lines.extend(["", "## CGN Bottleneck Audit", ""])
    if cgn_bottleneck:
        lines.extend(
            _markdown_table(
                ["variant", "success_rate", "mean_attempts"],
                list(cgn_bottleneck.get("summary") or cgn_bottleneck.get("overall") or []),
            )
        )
    else:
        lines.append("_No CGN bottleneck summary supplied._")
    lines.extend(["", "## GraspVLA Official Alignment", ""])
    if alignment_summary:
        overall = list(alignment_summary.get("overall") or alignment_summary.get("variant_summary") or [])
        if overall:
            lines.extend(_markdown_table(list(overall[0].keys()), overall))
        else:
            lines.append("```json")
            lines.append(json.dumps(alignment_summary, indent=2, ensure_ascii=False))
            lines.append("```")
    else:
        lines.append("_No alignment summary supplied._")
    lines.extend(["", "## Track B Native Reference", ""])
    lines.extend(
        _markdown_table(
            ["track", "method_tier", "benchmark", "trials", "successes", "success_rate", "wilson_ci_low", "wilson_ci_high"],
            track_b_reference,
        )
    )
    lines.extend(["", f"## {native_label}", ""])
    if native_appendix_summary:
        if native_appendix_parent_run_ids:
            lines.append(f"_parent_run_id(s): `{', '.join(native_appendix_parent_run_ids)}`_")
            lines.append("")
        if native_appendix_task_sets:
            lines.append(f"_task_set(s): `{', '.join(native_appendix_task_sets)}`_")
            lines.append("")
        lines.extend(
            _markdown_table(
                [
                    "track",
                    "method",
                    "method_tier",
                    "task",
                    "trials",
                    "successes",
                    "success_rate",
                    "wilson_ci_low",
                    "wilson_ci_high",
                    "mean_attempts",
                    "mean_spl",
                    "mean_inference_ms",
                    "mean_cycle_time_s",
                ],
                native_appendix_summary,
            )
        )
        lines.extend(["", f"### {native_label} By Condition", ""])
        lines.extend(
            _markdown_table(
                [
                    "track",
                    "method_tier",
                    "task",
                    "condition",
                    "trials",
                    "success_rate",
                    "wilson_ci_low",
                    "wilson_ci_high",
                    "mean_attempts",
                ],
                native_appendix_by_condition,
            )
        )
    else:
        lines.append("_No native appendix rows supplied._")
    lines.extend(["", f"## {instruction_label}", ""])
    if instruction_parent_run_ids:
        lines.append(f"_parent_run_id(s): `{', '.join(instruction_parent_run_ids)}`_")
        lines.append("")
    if instruction_task_sets:
        lines.append(f"_task_set(s): `{', '.join(instruction_task_sets)}`_")
        lines.append("")
    lines.extend(
        _markdown_table(
            [
                "method_tier",
                "task",
                "condition",
                "instruction_variant_family",
                "trials",
                "success_rate",
                "canonical_success_rate",
                "canonical_to_variant_success_drop",
                "paraphrase_consistency_rate",
                "worst_case_success_rate",
            ],
            instruction_summary,
        )
    )
    lines.extend(["", f"## {sim2real_label}", ""])
    if sim2real_parent_run_ids:
        lines.append(f"_parent_run_id(s): `{', '.join(sim2real_parent_run_ids)}`_")
        lines.append("")
    if sim2real_task_sets:
        lines.append(f"_task_set(s): `{', '.join(sim2real_task_sets)}`_")
        lines.append("")
    lines.extend(
        _markdown_table(
            [
                "method_tier",
                "task",
                "condition",
                "shift_family",
                "shift_severity",
                "trials",
                "success_rate",
                "wilson_ci_low",
                "wilson_ci_high",
                "perturbation_gap_vs_best",
            ],
            sim2real_summary,
        )
    )
    lines.extend(["", f"### {sim2real_label} Rank Stability", ""])
    lines.extend(_markdown_table(["task", "condition", "shift_families", "rank_stability"], sim2real_rank_stability))
    lines.extend(["", f"## {stage_metrics_label}", ""])
    lines.extend(
        _markdown_table(
            [
                "track",
                "method_tier",
                "task",
                "condition",
                "trials",
                "grounding_success_mean",
                "mask_nonempty_mean",
                "proposal_nonempty_mean",
                "plan_success_mean",
                "lift_only_success_mean",
                "hold_success_mean",
                "slip_after_lift_mean",
                "wrong_object_mean",
                "wrong_part_mean",
            ],
            stage_metrics_summary,
        )
    )
    lines.extend(["", f"## {phase2_label}", ""])
    if phase2_parent_run_ids:
        lines.append(f"_parent_run_id(s): `{', '.join(phase2_parent_run_ids)}`_")
        lines.append("")
    if phase2_task_sets:
        lines.append(f"_task_set(s): `{', '.join(phase2_task_sets)}`_")
        lines.append("")
    lines.extend(
        _markdown_table(
            [
                "track",
                "method_tier",
                "task",
                "trials",
                "successes",
                "success_rate",
                "wilson_ci_low",
                "wilson_ci_high",
                "mean_attempts",
            ],
            phase2_summary,
        )
    )
    return "\n".join(lines) + "\n"


def _render_teacher_summary(
    *,
    cal_summary: list[dict[str, object]],
    stress_summary: list[dict[str, object]],
    instruction_summary: list[dict[str, object]],
    sim2real_summary: list[dict[str, object]],
    phase2_summary: list[dict[str, object]],
    native_appendix_summary: list[dict[str, object]],
    pairwise_stats: list[dict[str, object]],
    protocol_probe: dict[str, object],
    cgn_bottleneck: dict[str, object],
    track_b_reference: list[dict[str, object]],
    cal_task_sets: list[str],
    stress_task_sets: list[str],
    instruction_task_sets: list[str],
    sim2real_task_sets: list[str],
    phase2_task_sets: list[str],
    native_appendix_task_sets: list[str],
) -> str:
    total_cal_trials = sum(int(row.get("trials", 0)) for row in cal_summary)
    total_cal_successes = sum(int(row.get("successes", 0)) for row in cal_summary)
    total_stress_trials = sum(int(row.get("trials", 0)) for row in stress_summary)
    total_stress_successes = sum(int(row.get("successes", 0)) for row in stress_summary)

    def _snapshot(rows: list[dict[str, object]], label: str) -> list[str]:
        output: list[str] = []
        for row in rows:
            method = str(row.get("method_tier", "")).strip()
            task = str(row.get("task", "")).strip()
            if not method or not task:
                continue
            output.append(
                f"- {label}: `{method}` 在 `{task}` 上为 `{row.get('successes', 0)}/{row.get('trials', 0)}` "
                f"(`{row.get('success_rate', 0.0)}`)"
            )
        return output

    lines = [
        "# CoRL 2026 仿真阶段总结",
        "",
        "- 论文 framing 固定为 `shared benchmark + protocol audit`，不是只看 scoreboard，也不是只做 release 诊断。",
        "- `Track A-Cal v3` 是唯一 headline fair table；`Track A-Stress v4`、instruction robustness、sim-to-real proxy、Phase 2 pilot 和 `Track B` 都是补强层。",
        "- `AnyGrasp` 在没有 node-matched 新 license 前不进入 submission 版主结论。",
    ]
    if total_cal_trials:
        lines.append(f"- 当前主榜单累计写入 `{total_cal_successes}/{total_cal_trials}` 的正式 paired 结果。")
    if total_stress_trials:
        lines.append(f"- 当前 hardest-slice appendix 已累计写入 `{total_stress_successes}/{total_stress_trials}` 的结果。")
    if cal_task_sets:
        lines.append(f"- 当前主榜单 task set: `{', '.join(cal_task_sets)}`。")
    if stress_task_sets:
        lines.append(f"- 当前 stress task set: `{', '.join(stress_task_sets)}`。")
    if instruction_task_sets:
        lines.append(f"- 当前 instruction robustness task set: `{', '.join(instruction_task_sets)}`。")
    if sim2real_task_sets:
        lines.append(f"- 当前 sim-to-real proxy task set: `{', '.join(sim2real_task_sets)}`。")
    if phase2_task_sets:
        lines.append(f"- 当前 phase 2 pilot task set: `{', '.join(phase2_task_sets)}`。")
    if pairwise_stats:
        best = pairwise_stats[0]
        lines.append(
            f"- 当前 paper bundle 已输出配对统计：`{best['method_a']} vs {best['method_b']}` 有 `{best['paired_scenes']}` 个 paired scenes，McNemar exact p 值为 `{best['mcnemar_p_exact']}`。"
        )
    if protocol_probe:
        lines.append("- GraspVLA 的 protocol / transfer audit 单独进入 audit section，不混入 headline 结果。")
    if cgn_bottleneck:
        lines.append("- CGN bottleneck 会拆开 grounding、proposal、planning 和 strict success semantics 来解释，不把低分归因成一个简单配置错误。")
    if instruction_summary:
        lines.append(
            f"- instruction robustness 已进入 bundle，当前共有 `{sum(int(row.get('trials', 0)) for row in instruction_summary)}` 个方法-变体汇总单元。"
        )
    if sim2real_summary:
        lines.append(
            f"- sim-to-real proxy 已进入 bundle，当前共有 `{sum(int(row.get('trials', 0)) for row in sim2real_summary)}` 个方法-扰动汇总单元。"
        )
    if phase2_summary:
        lines.append(
            f"- Phase 2 pilot 已进入 extension section，当前共有 `{sum(int(row.get('trials', 0)) for row in phase2_summary)}` 个方法-任务汇总单元。"
        )
    if track_b_reference:
        lines.append("- `Track B` 继续只保留 native reference，用来解释公开 release 的能力上限，不参与公平主结论。")
    if native_appendix_summary:
        lines.append("- `CGN native-like appendix` 已经接入 bundle，用来回答 modular baseline 是否只是因为 shared lane 才显得过低。")
    if native_appendix_task_sets:
        lines.append(f"- 当前 native-like appendix task set: `{', '.join(native_appendix_task_sets)}`。")
    lines.extend(
        [
            "",
            "## 这份 bundle 的用途",
            "",
            "- `paper_ready_report.md` 直接用于论文写作、组会汇报和导师过稿。",
            "- `paper_summary.csv` 与 `paper_stats.json` 提供主表、统计检验和 appendix 的结构化数据。",
            "- `figures/` 下的 CSV 可直接喂给后续画图脚本。",
            "",
            "## 主结果快照",
            "",
        ]
    )
    lines.extend(_snapshot(cal_summary, "Track A-Cal"))
    lines.extend(_snapshot(stress_summary, "Track A-Stress"))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble a paper-ready CoRL benchmark bundle.")
    parser.add_argument("--input", required=True, help="Root directory containing results.csv artifacts.")
    parser.add_argument(
        "--output-dir",
        default=str(ARTIFACTS_DIR / "reports" / "paper_bundle_latest"),
        help="Output directory for the paper-ready bundle.",
    )
    parser.add_argument("--execution-mode", default="shared_track_a_sim")
    parser.add_argument("--track-a-cal-parent-run-id", default="")
    parser.add_argument("--track-a-stress-parent-run-id", default="")
    parser.add_argument("--instruction-parent-run-id", default="")
    parser.add_argument("--sim2real-parent-run-id", default="")
    parser.add_argument("--phase2-parent-run-id", default="")
    parser.add_argument("--track-b-reference", default="")
    parser.add_argument("--track-b-native-parent-run-id", default="")
    parser.add_argument("--protocol-probe-summary", default="")
    parser.add_argument("--cgn-bottleneck-summary", default="")
    parser.add_argument("--alignment-summary", default="")
    args = parser.parse_args()

    rows = _iter_result_rows(Path(args.input))
    if not rows:
        raise SystemExit(f"No results.csv files found under {args.input}")

    cal_parent_run_ids = _resolve_parent_run_ids(
        rows,
        track="track_a_cal",
        execution_mode=args.execution_mode,
        explicit=args.track_a_cal_parent_run_id,
    )
    stress_parent_run_ids = _resolve_parent_run_ids(
        rows,
        track="track_a_stress",
        execution_mode=args.execution_mode,
        explicit=args.track_a_stress_parent_run_id,
    )
    instruction_parent_run_ids = _resolve_parent_run_ids(
        rows,
        track="track_a_instruction",
        execution_mode=args.execution_mode,
        explicit=args.instruction_parent_run_id,
    )
    sim2real_parent_run_ids = _resolve_parent_run_ids(
        rows,
        track="track_a_transfer",
        execution_mode=args.execution_mode,
        explicit=args.sim2real_parent_run_id,
    )
    phase2_parent_run_ids = _resolve_parent_run_ids(
        rows,
        track="track_a_phase2",
        execution_mode=args.execution_mode,
        explicit=args.phase2_parent_run_id,
    )
    native_appendix_parent_run_ids = _resolve_parent_run_ids(
        rows,
        track="track_b_native",
        execution_mode=args.execution_mode,
        explicit=args.track_b_native_parent_run_id,
    )

    cal_rows = _headline_rows(
        _filter_rows(rows, track="track_a_cal", execution_mode=args.execution_mode, parent_run_ids=cal_parent_run_ids)
    )
    stress_rows = _headline_rows(
        _filter_rows(rows, track="track_a_stress", execution_mode=args.execution_mode, parent_run_ids=stress_parent_run_ids)
    )
    instruction_rows = _headline_rows(
        _filter_rows(rows, track="track_a_instruction", execution_mode=args.execution_mode, parent_run_ids=instruction_parent_run_ids)
    )
    sim2real_rows = _headline_rows(
        _filter_rows(rows, track="track_a_transfer", execution_mode=args.execution_mode, parent_run_ids=sim2real_parent_run_ids)
    )
    phase2_rows = _headline_rows(
        _filter_rows(rows, track="track_a_phase2", execution_mode=args.execution_mode, parent_run_ids=phase2_parent_run_ids)
    )
    native_appendix_rows = _filter_rows(
        rows,
        track="track_b_native",
        execution_mode=args.execution_mode,
        parent_run_ids=native_appendix_parent_run_ids,
    )

    if not cal_rows:
        raise SystemExit("No Track A-Cal rows matched the requested execution mode / parent_run_id filter.")

    cal_task_sets = sorted({str(row.get("task_set", "")).strip() for row in cal_rows if str(row.get("task_set", "")).strip()})
    stress_task_sets = sorted({str(row.get("task_set", "")).strip() for row in stress_rows if str(row.get("task_set", "")).strip()})
    instruction_task_sets = sorted(
        {str(row.get("task_set", "")).strip() for row in instruction_rows if str(row.get("task_set", "")).strip()}
    )
    sim2real_task_sets = sorted(
        {str(row.get("task_set", "")).strip() for row in sim2real_rows if str(row.get("task_set", "")).strip()}
    )
    phase2_task_sets = sorted({str(row.get("task_set", "")).strip() for row in phase2_rows if str(row.get("task_set", "")).strip()})
    native_appendix_task_sets = sorted(
        {str(row.get("task_set", "")).strip() for row in native_appendix_rows if str(row.get("task_set", "")).strip()}
    )

    cal_summary = _aggregate(cal_rows, ["track", "method", "method_tier", "task"])
    cal_by_condition = _aggregate(cal_rows, ["track", "method", "method_tier", "task", "condition"])
    cal_by_object_group = _aggregate(cal_rows, ["track", "method", "method_tier", "task", "object_group"])
    stress_summary = _aggregate(stress_rows, ["track", "method", "method_tier", "task"])
    stress_by_condition = _aggregate(stress_rows, ["track", "method", "method_tier", "task", "condition"])
    stress_by_object_group = _aggregate(stress_rows, ["track", "method", "method_tier", "task", "object_group"])
    instruction_summary = _instruction_robustness_summary(instruction_rows)
    sim2real_summary = _sim2real_proxy_summary(sim2real_rows)
    sim2real_rank_stability = _rank_stability_summary(sim2real_summary)
    phase2_summary = _aggregate(phase2_rows, ["track", "method", "method_tier", "task"])
    stage_metrics_summary = _aggregate_stage_metrics(
        cal_rows + stress_rows + instruction_rows + sim2real_rows + phase2_rows + native_appendix_rows,
        ["track", "method", "method_tier", "task", "condition"],
    )
    native_appendix_summary = _aggregate(native_appendix_rows, ["track", "method", "method_tier", "task"])
    native_appendix_by_condition = _aggregate(
        native_appendix_rows,
        ["track", "method", "method_tier", "task", "condition"],
    )
    pairwise_stats = _pairwise_stats(cal_rows)
    failure_taxonomy = _failure_taxonomy(
        cal_rows + stress_rows + instruction_rows + sim2real_rows + phase2_rows + native_appendix_rows
    )
    track_b_reference = _parse_track_b_reference(Path(args.track_b_reference)) if args.track_b_reference else []
    protocol_probe = _load_json(args.protocol_probe_summary)
    cgn_bottleneck = _load_json(args.cgn_bottleneck_summary)
    alignment_summary = _load_json(args.alignment_summary)

    output_dir = ensure_dir(Path(args.output_dir))
    figures_dir = ensure_dir(output_dir / "figures")

    paper_summary_rows = (
        _paper_rows("track_a_cal", cal_summary)
        + _paper_rows("track_a_stress", stress_summary)
        + _paper_rows("instruction_robustness", instruction_summary)
        + _paper_rows("sim2real_proxy", sim2real_summary)
        + _paper_rows("phase2_pilot", phase2_summary)
        + _paper_rows("track_b_native_appendix", native_appendix_summary)
        + track_b_reference
    )
    paper_stats = {
        "track_a_cal": {
            "parent_run_ids": cal_parent_run_ids,
            "task_sets": cal_task_sets,
            "summary": cal_summary,
            "by_condition": cal_by_condition,
            "by_object_group": cal_by_object_group,
        },
        "track_a_stress": {
            "parent_run_ids": stress_parent_run_ids,
            "task_sets": stress_task_sets,
            "summary": stress_summary,
            "by_condition": stress_by_condition,
            "by_object_group": stress_by_object_group,
        },
        "instruction_robustness": {
            "parent_run_ids": instruction_parent_run_ids,
            "task_sets": instruction_task_sets,
            "summary": instruction_summary,
        },
        "sim2real_proxy": {
            "parent_run_ids": sim2real_parent_run_ids,
            "task_sets": sim2real_task_sets,
            "summary": sim2real_summary,
            "rank_stability": sim2real_rank_stability,
        },
        "phase2_pilot": {
            "parent_run_ids": phase2_parent_run_ids,
            "task_sets": phase2_task_sets,
            "summary": phase2_summary,
        },
        "track_b_native_appendix": {
            "parent_run_ids": native_appendix_parent_run_ids,
            "task_sets": native_appendix_task_sets,
            "summary": native_appendix_summary,
            "by_condition": native_appendix_by_condition,
        },
        "stage_metrics_summary": stage_metrics_summary,
        "pairwise_stats": pairwise_stats,
        "failure_taxonomy": failure_taxonomy,
        "track_b_reference": track_b_reference,
        "protocol_probe": protocol_probe,
        "cgn_bottleneck": cgn_bottleneck,
        "alignment_summary": alignment_summary,
    }

    _write_csv(output_dir / "paper_summary.csv", paper_summary_rows)
    (output_dir / "paper_stats.json").write_text(json.dumps(paper_stats, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "paper_ready_report.md").write_text(
        _render_report(
            cal_summary=cal_summary,
            cal_by_condition=cal_by_condition,
            cal_by_object_group=cal_by_object_group,
            stress_summary=stress_summary,
            stress_by_condition=stress_by_condition,
            stress_by_object_group=stress_by_object_group,
            instruction_summary=instruction_summary,
            sim2real_summary=sim2real_summary,
            sim2real_rank_stability=sim2real_rank_stability,
            phase2_summary=phase2_summary,
            stage_metrics_summary=stage_metrics_summary,
            native_appendix_summary=native_appendix_summary,
            native_appendix_by_condition=native_appendix_by_condition,
            pairwise_stats=pairwise_stats,
            failure_taxonomy=failure_taxonomy,
            track_b_reference=track_b_reference,
            protocol_probe=protocol_probe,
            cgn_bottleneck=cgn_bottleneck,
            alignment_summary=alignment_summary,
            cal_parent_run_ids=cal_parent_run_ids,
            stress_parent_run_ids=stress_parent_run_ids,
            instruction_parent_run_ids=instruction_parent_run_ids,
            sim2real_parent_run_ids=sim2real_parent_run_ids,
            phase2_parent_run_ids=phase2_parent_run_ids,
            native_appendix_parent_run_ids=native_appendix_parent_run_ids,
            cal_task_sets=cal_task_sets,
            stress_task_sets=stress_task_sets,
            instruction_task_sets=instruction_task_sets,
            sim2real_task_sets=sim2real_task_sets,
            phase2_task_sets=phase2_task_sets,
            native_appendix_task_sets=native_appendix_task_sets,
        ),
        encoding="utf-8",
    )
    teacher_summary = _render_teacher_summary(
        cal_summary=cal_summary,
        stress_summary=stress_summary,
        instruction_summary=instruction_summary,
        sim2real_summary=sim2real_summary,
        phase2_summary=phase2_summary,
        native_appendix_summary=native_appendix_summary,
        pairwise_stats=pairwise_stats,
        protocol_probe=protocol_probe,
        cgn_bottleneck=cgn_bottleneck,
        track_b_reference=track_b_reference,
        cal_task_sets=cal_task_sets,
        stress_task_sets=stress_task_sets,
        instruction_task_sets=instruction_task_sets,
        sim2real_task_sets=sim2real_task_sets,
        phase2_task_sets=phase2_task_sets,
        native_appendix_task_sets=native_appendix_task_sets,
    )
    (output_dir / "teacher_summary_zh.md").write_text(
        teacher_summary,
        encoding="utf-8-sig",
    )
    (output_dir / "teacher_summary_zh_clean.md").write_text(
        _render_teacher_summary(
            cal_summary=cal_summary,
            stress_summary=stress_summary,
            instruction_summary=instruction_summary,
            sim2real_summary=sim2real_summary,
            phase2_summary=phase2_summary,
            native_appendix_summary=native_appendix_summary,
            pairwise_stats=pairwise_stats,
            protocol_probe=protocol_probe,
            cgn_bottleneck=cgn_bottleneck,
            track_b_reference=track_b_reference,
            cal_task_sets=cal_task_sets,
            stress_task_sets=stress_task_sets,
            instruction_task_sets=instruction_task_sets,
            sim2real_task_sets=sim2real_task_sets,
            phase2_task_sets=phase2_task_sets,
            native_appendix_task_sets=native_appendix_task_sets,
        ),
        encoding="utf-8",
    )

    _write_csv(figures_dir / "track_a_cal_summary.csv", cal_summary)
    _write_csv(figures_dir / "track_a_cal_by_condition.csv", cal_by_condition)
    _write_csv(figures_dir / "track_a_cal_by_object_group.csv", cal_by_object_group)
    _write_csv(figures_dir / "track_a_stress_summary.csv", stress_summary)
    _write_csv(figures_dir / "track_a_stress_by_condition.csv", stress_by_condition)
    _write_csv(figures_dir / "track_a_stress_by_object_group.csv", stress_by_object_group)
    _write_csv(figures_dir / "instruction_robustness_summary.csv", instruction_summary)
    _write_csv(figures_dir / "sim2real_proxy_summary.csv", sim2real_summary)
    _write_csv(figures_dir / "stage_metrics_summary.csv", stage_metrics_summary)
    _write_csv(figures_dir / "phase2_pilot_summary.csv", phase2_summary)
    _write_csv(figures_dir / "sim2real_rank_stability.csv", sim2real_rank_stability)
    _write_csv(figures_dir / "track_b_native_appendix_summary.csv", native_appendix_summary)
    _write_csv(figures_dir / "track_b_native_appendix_by_condition.csv", native_appendix_by_condition)
    _write_csv(figures_dir / "pairwise_stats.csv", pairwise_stats)
    _write_csv(figures_dir / "failure_taxonomy.csv", failure_taxonomy)
    _write_csv(figures_dir / "track_b_reference.csv", track_b_reference)

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "cal_parent_run_ids": cal_parent_run_ids,
                "stress_parent_run_ids": stress_parent_run_ids,
                "instruction_parent_run_ids": instruction_parent_run_ids,
                "sim2real_parent_run_ids": sim2real_parent_run_ids,
                "phase2_parent_run_ids": phase2_parent_run_ids,
                "track_b_native_parent_run_ids": native_appendix_parent_run_ids,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
