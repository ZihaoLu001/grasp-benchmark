from __future__ import annotations

import argparse
import csv
import json
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
        grouped[tuple(row[key] for key in group_keys)].append(row)

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
    counter = Counter((row["method"], row["failure_stage"], row["failure_reason"]) for row in rows)
    taxonomy = []
    for (method, stage, reason), count in sorted(counter.items()):
        taxonomy.append(
            {
                "method": method,
                "failure_stage": stage,
                "failure_reason": reason,
                "count": count,
            }
        )
    return taxonomy


def _write_markdown(
    output: Path,
    summary: list[dict[str, object]],
    conditions: list[dict[str, object]],
    taxonomy: list[dict[str, object]],
) -> None:
    lines = [
        "# Aggregate Report",
        "",
        "## Summary",
        "",
    ]
    for row in summary:
        lines.append(
            f"- {row['method']} / {row['task']}: "
            f"success={row['success_rate']:.4f}, spl={row['mean_spl']:.4f}, "
            f"inference_ms={row['mean_inference_ms']:.4f}, cycle_s={row['mean_cycle_time_s']:.4f}"
        )
    lines.extend(["", "## By Condition", ""])
    for row in conditions:
        lines.append(
            f"- {row['method']} / {row['task']} / {row['condition']}: "
            f"success={row['success_rate']:.4f}, attempts={row['mean_attempts']:.4f}"
        )
    lines.extend(["", "## Failure Taxonomy", ""])
    for row in taxonomy[:20]:
        lines.append(
            f"- {row['method']}: {row['failure_stage']} / {row['failure_reason']} ({row['count']})"
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
    args = parser.parse_args()

    input_root = Path(args.input)
    output_dir = Path(args.output_dir)
    rows = _iter_csv_rows(input_root)
    if not rows:
        raise SystemExit(f"No CSV files found under {input_root}")

    summary = _aggregate(rows, ["method", "task"])
    by_condition = _aggregate(rows, ["method", "task", "condition"])
    by_object_group = _aggregate(rows, ["method", "task", "object_group"])
    taxonomy = _failure_taxonomy(rows)

    _write_csv(output_dir / "summary.csv", summary)
    _write_csv(output_dir / "by_condition.csv", by_condition)
    _write_csv(output_dir / "by_object_group.csv", by_object_group)
    _write_csv(output_dir / "failure_taxonomy.csv", taxonomy)
    _write_markdown(output_dir / "report.md", summary, by_condition, taxonomy)
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "by_condition": by_condition,
                "by_object_group": by_object_group,
                "failure_taxonomy": taxonomy,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote aggregate outputs to {output_dir}")


if __name__ == "__main__":
    main()
