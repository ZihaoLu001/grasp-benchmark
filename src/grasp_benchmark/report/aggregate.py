from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

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


def _coerce_row(row: dict[str, str]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in row.items():
        caster = NUMERIC_FIELDS.get(key)
        if caster is None:
            output[key] = value
        else:
            output[key] = caster(value) if value not in {"", None} else caster(0)
    return output


def _iter_csv_rows(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("*.csv")):
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows.extend(_coerce_row(row) for row in reader)
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
        counter[(row["track"], row["method"], stage, reason)] += 1

    taxonomy = []
    for (track, method, stage, reason), count in sorted(counter.items()):
        taxonomy.append(
            {
                "track": track,
                "method": method,
                "failure_stage": stage,
                "failure_reason": reason,
                "count": count,
            }
        )
    return taxonomy


def _resolve_parent_run_id(
    rows: list[dict[str, object]],
    *,
    execution_mode: str,
    explicit_parent_run_id: str,
) -> str:
    if explicit_parent_run_id:
        return explicit_parent_run_id
    latest = ""
    for row in rows:
        candidate = str(row.get("parent_run_id", "")).strip()
        if (
            candidate
            and str(row.get("track", "")).startswith("track_a")
            and str(row.get("execution_mode", "")) == execution_mode
        ):
            latest = candidate
    return latest


def _track_a_rows(rows: list[dict[str, object]], *, execution_mode: str, parent_run_id: str = "") -> list[dict[str, object]]:
    filtered = [
        row
        for row in rows
        if str(row.get("track", "")).startswith("track_a") and str(row.get("execution_mode", "")) == execution_mode
    ]
    if not parent_run_id:
        return filtered
    return [row for row in filtered if str(row.get("parent_run_id", "")).strip() == parent_run_id]


def _by_shard(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    shard_rows = [row for row in rows if str(row.get("shard_id", "")).strip()]
    return _aggregate(shard_rows, ["track", "method", "parent_run_id", "shard_id", "node", "gpu_id"])


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


def _write_markdown(
    output: Path,
    summary: list[dict[str, object]],
    conditions: list[dict[str, object]],
    object_groups: list[dict[str, object]],
    taxonomy: list[dict[str, object]],
    track_b_reference: list[dict[str, object]],
    *,
    parent_run_id: str,
) -> None:
    lines = [
        "# Aggregate Report",
        "",
        "## Track A Shared Benchmark",
        "",
    ]
    if parent_run_id:
        lines.extend([f"_Filtered to parent_run_id `{parent_run_id}`._", ""])
    lines.extend(
        _markdown_table(
            ["track", "method", "task", "trials", "success_rate", "mean_spl", "mean_attempts", "mean_inference_ms", "mean_cycle_time_s"],
            summary,
        )
    )
    lines.extend(["", "## Track A By Condition", ""])
    lines.extend(
        _markdown_table(
            ["track", "method", "task", "condition", "trials", "success_rate", "mean_attempts"],
            conditions,
        )
    )
    lines.extend(["", "## Track A By Object Group", ""])
    lines.extend(
        _markdown_table(
            ["track", "method", "task", "object_group", "trials", "success_rate", "mean_attempts"],
            object_groups,
        )
    )
    lines.extend(["", "## Track B Native Deployment Reference", ""])
    lines.extend(
        _markdown_table(
            ["track", "method", "benchmark", "trials", "successes", "success_rate", "reference_type"],
            track_b_reference,
        )
    )
    lines.extend(["", "## Failure Taxonomy", ""])
    if taxonomy:
        for row in taxonomy[:20]:
            lines.append(
                f"- {row['track']} / {row['method']}: {row['failure_stage']} / {row['failure_reason']} ({row['count']})"
            )
    else:
        lines.append("_No failures recorded._")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_teacher_summary(
    output: Path,
    summary: list[dict[str, object]],
    by_condition: list[dict[str, object]],
    track_b_reference: list[dict[str, object]],
    *,
    parent_run_id: str,
) -> None:
    lines = [
        "# Benchmark 汇总说明",
        "",
        "这一页只汇报两套严格分开的结果：",
        "- `Track A shared benchmark`：统一 benchmark setting 下的正式仿真结果。",
        "- `Track B native deployment reference`：官方 release / 官方原生协议下的参考结果，只作为 native reference，不与 Track A 混算。",
        "",
    ]
    if parent_run_id:
        lines.extend([f"- 当前 Track A 汇总的 `parent_run_id`：`{parent_run_id}`", ""])

    lines.extend(["## Track A Shared Benchmark", ""])
    if summary:
        for row in summary:
            lines.append(
                "- "
                f"{row['method']} / {row['task']}: success_rate={row['success_rate']}, trials={row['trials']}, "
                f"mean_attempts={row['mean_attempts']}, mean_inference_ms={row['mean_inference_ms']}, "
                f"mean_cycle_time_s={row['mean_cycle_time_s']}"
            )
    else:
        lines.append("- 没有找到符合 `shared_track_a_sim` 的正式 Track A 结果。")

    lines.extend(["", "## Track A By Condition", ""])
    if by_condition:
        for row in by_condition:
            lines.append(
                f"- {row['method']} / {row['task']} / {row['condition']}: success_rate={row['success_rate']}, trials={row['trials']}"
            )
    else:
        lines.append("- 暂无按 condition 切分的数据。")

    lines.extend(["", "## Track B Native Reference", ""])
    if track_b_reference:
        for row in track_b_reference:
            lines.append(
                f"- {row['benchmark']}: success_rate={row['success_rate']}, trials={row['trials']}, source={row['source_artifact']}"
            )
    else:
        lines.append("- 未提供 Track B 官方 reference。")

    lines.extend(
        [
            "",
            "## 解释口径",
            "",
            "- Track A 才是 benchmark setting 下可用于公平比较的正式分数。",
            "- Track B 只用于说明方法在作者原生 / 官方协议下的表现，不用于最终公平 claim。",
            "",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
        "--track-a-execution-mode",
        default="shared_track_a_sim",
        help="Only Track A rows with this execution_mode are treated as formal benchmark results.",
    )
    parser.add_argument(
        "--parent-run-id",
        default="",
        help="Optional parent_run_id filter. Defaults to the latest Track A parent run when present.",
    )
    args = parser.parse_args()

    input_root = Path(args.input)
    output_dir = Path(args.output_dir)
    rows = _iter_csv_rows(input_root)
    if not rows:
        raise SystemExit(f"No CSV files found under {input_root}")

    parent_run_id = _resolve_parent_run_id(
        rows,
        execution_mode=args.track_a_execution_mode,
        explicit_parent_run_id=args.parent_run_id,
    )
    track_a_rows = _track_a_rows(rows, execution_mode=args.track_a_execution_mode, parent_run_id=parent_run_id)
    summary = _aggregate(track_a_rows, ["track", "method", "task"])
    by_condition = _aggregate(track_a_rows, ["track", "method", "task", "condition"])
    by_object_group = _aggregate(track_a_rows, ["track", "method", "task", "object_group"])
    by_shard = _by_shard(track_a_rows)
    taxonomy = _failure_taxonomy(track_a_rows)
    track_b_reference = _parse_track_b_reference(Path(args.track_b_reference)) if args.track_b_reference else []

    _write_csv(output_dir / "summary.csv", summary)
    _write_csv(output_dir / "by_condition.csv", by_condition)
    _write_csv(output_dir / "by_object_group.csv", by_object_group)
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
        parent_run_id=parent_run_id,
    )
    _write_teacher_summary(
        output_dir / "teacher_summary_zh.md",
        summary,
        by_condition,
        track_b_reference,
        parent_run_id=parent_run_id,
    )
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "by_condition": by_condition,
                "by_object_group": by_object_group,
                "by_shard": by_shard,
                "failure_taxonomy": taxonomy,
                "track_b_reference": track_b_reference,
                "track_a_execution_mode": args.track_a_execution_mode,
                "parent_run_id": parent_run_id,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote aggregate outputs to {output_dir}")


if __name__ == "__main__":
    main()
