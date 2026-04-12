from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir


NUMERIC_FIELDS = {
    "attempts": int,
    "success": int,
    "lift_cm": float,
    "hold_s": float,
    "spl": float,
    "inference_ms": float,
    "cycle_time_s": float,
    "collision": int,
}

PRIMARY_TITLE = "Track A-Cal Shared Benchmark"
PRIMARY_BY_CONDITION_TITLE = "Track A-Cal By Condition"
PRIMARY_BY_OBJECT_GROUP_TITLE = "Track A-Cal By Object Group"
STRESS_TITLE = "Track A-Stress Shared Stress Test"
DIAGNOSTIC_TITLE = "GraspVLA Diagnostic Note"
TRACK_B_TITLE = "Track B Native Deployment Reference"
HISTORICAL_TITLE = "Historical / Interim Modular References"
HEADLINE_METHOD_TIERS = {"graspvla_official", "cgn_full_modular", "anygrasp_full_modular"}
INTERIM_METHOD_TIERS = {"cgn_raw_interim"}


def _infer_method_tier(row: dict[str, object]) -> str:
    explicit = str(row.get("method_tier", "")).strip()
    if explicit:
        return explicit
    method = str(row.get("method", "")).strip()
    if method == "graspvla":
        return "graspvla_official"
    if method == "cgn":
        parent_run_id = str(row.get("parent_run_id", "")).strip().lower()
        if any(token in parent_run_id for token in ("full", "modular")):
            return "cgn_full_modular"
        return "cgn_raw_interim"
    if method == "anygrasp":
        return "anygrasp_full_modular"
    return "unknown_method_tier"


def _coerce_row(row: dict[str, str]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in row.items():
        caster = NUMERIC_FIELDS.get(key)
        if caster is None:
            output[key] = value
        else:
            output[key] = caster(value) if value not in {"", None} else caster(0)
    output["method_tier"] = _infer_method_tier(output)
    return output


def _infer_parent_run_id(path: Path) -> str:
    if path.name != "results.csv":
        return ""
    parent = path.parent
    if parent.parent.name == "shards":
        return parent.parent.parent.name
    return parent.name


def _iter_csv_rows(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("results.csv")):
        inferred_parent_run_id = _infer_parent_run_id(path)
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                coerced = _coerce_row(row)
                if inferred_parent_run_id and not str(coerced.get("parent_run_id", "")).strip():
                    coerced["parent_run_id"] = inferred_parent_run_id
                rows.append(coerced)
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _aggregate(rows: list[dict[str, object]], group_keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(key, "") for key in group_keys)].append(row)

    summary_rows: list[dict[str, object]] = []
    for key, group in sorted(grouped.items()):
        successes = [float(item["success"]) for item in group]
        spl = [float(item["spl"]) for item in group]
        attempts = [float(item["attempts"]) for item in group]
        inference = [float(item["inference_ms"]) for item in group]
        cycle = [float(item["cycle_time_s"]) for item in group]
        row = {group_keys[index]: value for index, value in enumerate(key)}
        row.update(
            {
                "trials": len(group),
                "success_rate": _mean(successes),
                "mean_spl": _mean(spl),
                "mean_attempts": _mean(attempts),
                "mean_inference_ms": _mean(inference),
                "mean_cycle_time_s": _mean(cycle),
            }
        )
        summary_rows.append(row)
    return summary_rows


def _rows_for_method_tiers(rows: list[dict[str, object]], allowed_tiers: set[str]) -> list[dict[str, object]]:
    return [row for row in rows if str(row.get("method_tier", "")).strip() in allowed_tiers]


def _failure_taxonomy(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counter = Counter()
    for row in rows:
        stage = str(row.get("failure_stage", "")).strip()
        reason = str(row.get("failure_reason", "")).strip()
        success = int(row.get("success", 0))
        if success and not stage and not reason:
            continue
        if not stage and not reason:
            continue
        counter[(row["track"], row["method"], row.get("method_tier", ""), stage, reason)] += 1

    taxonomy: list[dict[str, object]] = []
    for (track, method, method_tier, stage, reason), count in sorted(counter.items()):
        taxonomy.append(
            {
                "track": track,
                "method": method,
                "method_tier": method_tier,
                "failure_stage": stage,
                "failure_reason": reason,
                "count": count,
            }
        )
    return taxonomy


def _parse_parent_run_ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_parent_run_ids(
    rows: list[dict[str, object]],
    *,
    execution_mode: str,
    explicit_parent_run_id: str,
) -> list[str]:
    if explicit_parent_run_id:
        return _parse_parent_run_ids(explicit_parent_run_id)
    latest = ""
    for row in rows:
        candidate = str(row.get("parent_run_id", "")).strip()
        if (
            candidate
            and str(row.get("track", "")).startswith("track_a")
            and str(row.get("execution_mode", "")) == execution_mode
        ):
            latest = candidate
    return [latest] if latest else []


def _track_a_rows(
    rows: list[dict[str, object]],
    *,
    execution_mode: str,
    parent_run_ids: list[str] | None = None,
) -> list[dict[str, object]]:
    filtered = [
        row
        for row in rows
        if str(row.get("track", "")).startswith("track_a") and str(row.get("execution_mode", "")) == execution_mode
    ]
    if not parent_run_ids:
        return filtered
    allowed = set(parent_run_ids)
    return [row for row in filtered if str(row.get("parent_run_id", "")).strip() in allowed]


def _by_shard(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    shard_rows = [row for row in rows if str(row.get("shard_id", "")).strip()]
    return _aggregate(shard_rows, ["track", "method", "method_tier", "parent_run_id", "shard_id", "node", "gpu_id"])


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
            rows.append(
                {
                    "track": track,
                    "method": method,
                    "method_tier": "graspvla_official",
                    "reference_type": "native_best_case",
                    "benchmark": "playground",
                    "trials": trials,
                    "successes": successes,
                    "success_rate": _mean([1.0] * successes + [0.0] * (trials - successes)),
                    "source_artifact": str(summary_path),
                }
            )

    pattern = re.compile(r"^(?P<benchmark>[\w_]+): (?P<success>\d+)/(?P<trials>\d+) = (?P<rate>\d+\.\d+)$")
    for line in str(payload.get("statistics_text", "")).splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        rows.append(
            {
                "track": track,
                "method": method,
                "method_tier": "graspvla_official",
                "reference_type": "native_best_case",
                "benchmark": match.group("benchmark"),
                "trials": int(match.group("trials")),
                "successes": int(match.group("success")),
                "success_rate": float(match.group("rate")),
                "source_artifact": str(summary_path),
            }
        )
    return rows


def _markdown_table(headers: list[str], rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["_No rows._"]
    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return [header_line, separator, *body]


def _load_diagnostic_note(report_path: Path | None) -> list[str]:
    if report_path is None or not report_path.exists():
        return []
    lines = report_path.read_text(encoding="utf-8").splitlines()
    start_index = None
    for index, line in enumerate(lines):
        if line.strip() == "## Diagnostic Note":
            start_index = index + 1
            break
    if start_index is None:
        return []
    note_lines: list[str] = []
    for line in lines[start_index:]:
        stripped = line.strip()
        if stripped.startswith("## "):
            break
        if stripped:
            note_lines.append(stripped)
    return note_lines


def _load_reference_report(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_markdown(
    output: Path,
    summary: list[dict[str, object]],
    conditions: list[dict[str, object]],
    object_groups: list[dict[str, object]],
    taxonomy: list[dict[str, object]],
    track_b_reference: list[dict[str, object]],
    *,
    interim_summary: list[dict[str, object]],
    parent_run_ids: list[str],
    diagnostic_note: list[str],
    stress_reference: dict[str, Any],
    stress_reference_path: str,
) -> None:
    lines = ["# Aggregate Report", "", f"## {PRIMARY_TITLE}", ""]
    if parent_run_ids:
        lines.extend([f"_Filtered to parent_run_id(s) `{', '.join(parent_run_ids)}`._", ""])
    lines.extend(
        _markdown_table(
            [
                "track",
                "method",
                "method_tier",
                "task",
                "trials",
                "success_rate",
                "mean_spl",
                "mean_attempts",
                "mean_inference_ms",
                "mean_cycle_time_s",
            ],
            summary,
        )
    )
    if summary and all(float(row.get("success_rate", 0.0)) == 0.0 for row in summary):
        lines.extend(
            [
                "",
                "_Health check triggered: Track A-Cal is still all-zero across headline methods, so the next action is to audit shared-runner / released-distribution alignment before expanding the benchmark further._",
            ]
        )

    lines.extend(["", f"## {PRIMARY_BY_CONDITION_TITLE}", ""])
    lines.extend(
        _markdown_table(
            ["track", "method", "method_tier", "task", "condition", "trials", "success_rate", "mean_attempts"],
            conditions,
        )
    )

    lines.extend(["", f"## {PRIMARY_BY_OBJECT_GROUP_TITLE}", ""])
    lines.extend(
        _markdown_table(
            ["track", "method", "method_tier", "task", "object_group", "trials", "success_rate", "mean_attempts"],
            object_groups,
        )
    )

    lines.extend(["", f"## {HISTORICAL_TITLE}", ""])
    lines.extend(
        _markdown_table(
            ["track", "method", "method_tier", "task", "trials", "success_rate", "mean_attempts"],
            interim_summary,
        )
    )

    lines.extend(["", f"## {STRESS_TITLE}", ""])
    if stress_reference_path:
        lines.extend([f"_Stress reference loaded from `{stress_reference_path}`._", ""])
    lines.extend(
        _markdown_table(
            ["track", "method", "task", "trials", "success_rate", "mean_attempts"],
            list(stress_reference.get("summary") or []),
        )
    )

    lines.extend(["", f"## {DIAGNOSTIC_TITLE}", ""])
    lines.extend(diagnostic_note or ["_No diagnostic note provided._"])

    lines.extend(["", f"## {TRACK_B_TITLE}", ""])
    lines.extend(
        _markdown_table(
            ["track", "method", "method_tier", "benchmark", "trials", "successes", "success_rate", "reference_type"],
            track_b_reference,
        )
    )

    lines.extend(["", "## Failure Taxonomy", ""])
    if taxonomy:
        for row in taxonomy[:20]:
            lines.append(
                f"- {row['track']} / {row['method']} / {row.get('method_tier', '')}: "
                f"{row['failure_stage']} / {row['failure_reason']} ({row['count']})"
            )
    else:
        lines.append("_No failures recorded._")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _render_teacher_summary(
    output: Path,
    summary: list[dict[str, object]],
    by_condition: list[dict[str, object]],
    by_object_group: list[dict[str, object]],
    track_b_reference: list[dict[str, object]],
    *,
    interim_summary: list[dict[str, object]],
    parent_run_ids: list[str],
    diagnostic_note: list[str],
    stress_reference: dict[str, Any],
    stress_reference_path: str,
) -> str:
    parent_run_id = ", ".join(parent_run_ids)
    lines = [
        "# Benchmark 汇总说明",
        "",
        "这份总结把三层结果严格分开：",
        "- `Track A-Cal`：共享 benchmark setting 下的主公平结论。",
        "- `Track A-Stress`：共享协议下的压力测试，只做 stress / appendix，不做 headline claim。",
        "- `Track B`：官方 native reference，只做工程参考，不参与最终公平结论。",
        "- `Historical / Interim Modular References`：工程调试期的 raw modular 结果，只保留做历史参考。",
        "",
    ]
    if parent_run_id:
        lines.extend([f"- 当前 `Track A-Cal` 汇总的 `parent_run_id`：`{parent_run_id}`", ""])

    lines.extend([f"## {PRIMARY_TITLE}", ""])
    if summary:
        for row in summary:
            lines.append(
                "- "
                f"{row['method']} / {row['method_tier']} / {row['task']}: success_rate={row['success_rate']}, "
                f"trials={row['trials']}, mean_attempts={row['mean_attempts']}, "
                f"mean_inference_ms={row['mean_inference_ms']}, mean_cycle_time_s={row['mean_cycle_time_s']}"
            )
    else:
        lines.append("- 没有找到符合 `shared_track_a_sim` 的正式 `Track A-Cal` 结果。")
    if summary and all(float(row.get("success_rate", 0.0)) == 0.0 for row in summary):
        lines.append("- 本轮 `Track A-Cal` 仍然是所有 headline 方法全 0，已经触发 health check。下一步优先做 shared runner 与 released distribution 的对齐审计，而不是继续扩 benchmark。")

    lines.extend(["", f"## {PRIMARY_BY_CONDITION_TITLE}", ""])
    if by_condition:
        for row in by_condition:
            lines.append(
                f"- {row['method']} / {row['method_tier']} / {row['task']} / {row['condition']}: "
                f"success_rate={row['success_rate']}, trials={row['trials']}"
            )
    else:
        lines.append("- 暂无按 condition 切分的数据。")

    lines.extend(["", f"## {PRIMARY_BY_OBJECT_GROUP_TITLE}", ""])
    if by_object_group:
        for row in by_object_group:
            lines.append(
                f"- {row['method']} / {row['method_tier']} / {row['task']} / {row['object_group']}: "
                f"success_rate={row['success_rate']}, trials={row['trials']}"
            )
    else:
        lines.append("- 暂无按 object group 切分的数据。")

    lines.extend(["", f"## {HISTORICAL_TITLE}", ""])
    if interim_summary:
        for row in interim_summary:
            lines.append(
                f"- {row['method']} / {row['method_tier']} / {row['task']}: "
                f"success_rate={row['success_rate']}, trials={row['trials']}, mean_attempts={row['mean_attempts']}"
            )
    else:
        lines.append("- 暂无 interim / raw modular 历史参考。")

    lines.extend(["", f"## {STRESS_TITLE}", ""])
    if stress_reference_path:
        lines.append(f"- Stress reference source: `{stress_reference_path}`")
    stress_summary = list(stress_reference.get("summary") or [])
    if stress_summary:
        for row in stress_summary:
            lines.append(
                f"- {row['method']} / {row['task']}: success_rate={row['success_rate']}, trials={row['trials']}, "
                f"mean_attempts={row.get('mean_attempts', '')}"
            )
    else:
        lines.append("- 未提供 `Track A-Stress` 历史参考结果。")

    lines.extend(["", f"## {DIAGNOSTIC_TITLE}", ""])
    lines.extend(diagnostic_note or ["- 暂无诊断说明。"])

    lines.extend(["", f"## {TRACK_B_TITLE}", ""])
    if track_b_reference:
        for row in track_b_reference:
            lines.append(
                f"- {row['benchmark']} / {row['method_tier']}: success_rate={row['success_rate']}, "
                f"trials={row['trials']}, source={row['source_artifact']}"
            )
    else:
        lines.append("- 未提供 `Track B` 官方 reference。")

    lines.extend(
        [
            "",
            "## 解释口径",
            "",
            "- `Track A-Cal` 才是 benchmark setting 下用于公平比较的主榜单。",
            "- `cgn_raw_interim` 这类 raw modular 结果只保留在历史 / appendix，不进入 headline table。",
            "- `Track A-Stress` 继续保留，但它代表共享协议下的压力测试，不再承担第一页 headline table 的职责。",
            "- `Track B` 只说明方法在作者原生 / 官方协议下的表现，不用于最终公平 claim。",
            "- 如果 `Track A-Cal` 再次出现所有方法全 0，就先审计 shared runner 与 released distribution 的对齐，而不是继续扩 benchmark 范围。",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    output.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate benchmark result CSV files.")
    parser.add_argument("--input", required=True, help="Root directory containing benchmark result CSV files.")
    parser.add_argument(
        "--output-dir",
        default=str(ARTIFACTS_DIR / "reports" / "latest"),
        help="Directory for summary outputs.",
    )
    parser.add_argument(
        "--track-b-reference",
        default="",
        help="Optional path to an official GraspVLA simulation summary.json to render as Track B native reference.",
    )
    parser.add_argument(
        "--track-a-stress-reference",
        default="",
        help="Optional path to a prior aggregate report.json used as the Track A-Stress reference section.",
    )
    parser.add_argument(
        "--track-a-execution-mode",
        default="shared_track_a_sim",
        help="Only Track A rows with this execution_mode are treated as formal benchmark results.",
    )
    parser.add_argument(
        "--parent-run-id",
        default="",
        help="Optional comma-separated parent_run_id filter. Defaults to the latest Track A parent run when present.",
    )
    parser.add_argument(
        "--diagnostic-report",
        default="",
        help="Optional path to a GraspVLA diagnostic report.md whose note section should be included in the aggregate output.",
    )
    args = parser.parse_args()

    input_root = Path(args.input)
    output_dir = Path(args.output_dir)
    rows = _iter_csv_rows(input_root)
    if not rows:
        raise SystemExit(f"No CSV files found under {input_root}")

    parent_run_ids = _resolve_parent_run_ids(
        rows,
        execution_mode=args.track_a_execution_mode,
        explicit_parent_run_id=args.parent_run_id,
    )
    track_a_rows = _track_a_rows(rows, execution_mode=args.track_a_execution_mode, parent_run_ids=parent_run_ids)
    headline_rows = _rows_for_method_tiers(track_a_rows, HEADLINE_METHOD_TIERS)
    interim_rows = _rows_for_method_tiers(track_a_rows, INTERIM_METHOD_TIERS)

    summary = _aggregate(headline_rows, ["track", "method", "method_tier", "task"])
    by_condition = _aggregate(headline_rows, ["track", "method", "method_tier", "task", "condition"])
    by_object_group = _aggregate(headline_rows, ["track", "method", "method_tier", "task", "object_group"])
    interim_summary = _aggregate(interim_rows, ["track", "method", "method_tier", "task"])
    by_shard = _by_shard(track_a_rows)
    taxonomy = _failure_taxonomy(track_a_rows)
    track_b_reference = _parse_track_b_reference(Path(args.track_b_reference)) if args.track_b_reference else []
    diagnostic_report = Path(args.diagnostic_report) if args.diagnostic_report else None
    diagnostic_note = _load_diagnostic_note(diagnostic_report)
    stress_reference_path = str(Path(args.track_a_stress_reference)) if args.track_a_stress_reference else ""
    stress_reference = _load_reference_report(Path(args.track_a_stress_reference)) if args.track_a_stress_reference else {}

    _write_csv(output_dir / "summary.csv", summary)
    _write_csv(output_dir / "by_condition.csv", by_condition)
    _write_csv(output_dir / "by_object_group.csv", by_object_group)
    _write_csv(output_dir / "historical_interim_summary.csv", interim_summary)
    _write_csv(output_dir / "by_shard.csv", by_shard)
    _write_csv(output_dir / "failure_taxonomy.csv", taxonomy)
    _write_csv(output_dir / "track_b_reference.csv", track_b_reference)
    _write_markdown(
        output_dir / "report.md",
        summary,
        by_condition,
        by_object_group,
        taxonomy,
        track_b_reference,
        interim_summary=interim_summary,
        parent_run_ids=parent_run_ids,
        diagnostic_note=diagnostic_note,
        stress_reference=stress_reference,
        stress_reference_path=stress_reference_path,
    )
    teacher_summary_text = _render_teacher_summary(
        output_dir / "teacher_summary_zh.md",
        summary,
        by_condition,
        by_object_group,
        track_b_reference,
        interim_summary=interim_summary,
        parent_run_ids=parent_run_ids,
        diagnostic_note=diagnostic_note,
        stress_reference=stress_reference,
        stress_reference_path=stress_reference_path,
    )
    with (output_dir / "teacher_summary_zh_clean.md").open("w", encoding="utf-8-sig") as handle:
        handle.write(teacher_summary_text)
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "by_condition": by_condition,
                "by_object_group": by_object_group,
                "historical_interim_summary": interim_summary,
                "by_shard": by_shard,
                "failure_taxonomy": taxonomy,
                "track_b_reference": track_b_reference,
                "track_a_stress_reference": stress_reference,
                "track_a_stress_reference_path": stress_reference_path,
                "diagnostic_report": str(diagnostic_report) if diagnostic_report else "",
                "diagnostic_note": diagnostic_note,
                "track_a_execution_mode": args.track_a_execution_mode,
                "parent_run_ids": parent_run_ids,
                "primary_title": PRIMARY_TITLE,
                "stress_title": STRESS_TITLE,
                "track_b_title": TRACK_B_TITLE,
                "historical_title": HISTORICAL_TITLE,
                "headline_method_tiers": sorted(HEADLINE_METHOD_TIERS),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Wrote aggregate outputs to {output_dir}")


if __name__ == "__main__":
    main()
