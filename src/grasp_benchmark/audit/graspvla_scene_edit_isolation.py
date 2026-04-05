from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grasp_benchmark.audit.graspvla_official_alignment import _load_track_a_cal_reference
from grasp_benchmark.paths import ARTIFACTS_DIR, PROJECT_ROOT, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.shell import run_command


@dataclass(frozen=True, slots=True)
class SceneEditProbeRow:
    benchmark: str
    task_id: int
    task_name: str
    instruction: str
    seed_count: int
    raw_state_compatible_count: int
    processed_state_compatible_count: int
    requires_official_scene_edit_for_all_seeds: bool
    raw_incompatible_seeds: tuple[int, ...]


def _docs_reports_dir() -> Path:
    return PROJECT_ROOT / "docs" / "reports"


def _write_text(path: Path, payload: str, *, encoding: str = "utf-8") -> None:
    ensure_dir(path.parent)
    path.write_text(payload, encoding=encoding)


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, json.dumps(payload, indent=2))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _parse_seed_list(value: str) -> tuple[int, ...]:
    if not value.strip():
        return tuple()
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def load_scene_edit_probe_summary(path: Path) -> list[SceneEditProbeRow]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        SceneEditProbeRow(
            benchmark=str(row["benchmark"]),
            task_id=int(row["task_id"]),
            task_name=str(row["task_name"]),
            instruction=str(row["instruction"]),
            seed_count=int(row["seed_count"]),
            raw_state_compatible_count=int(row["raw_state_compatible_count"]),
            processed_state_compatible_count=int(row["processed_state_compatible_count"]),
            requires_official_scene_edit_for_all_seeds=bool(int(row["requires_official_scene_edit_for_all_seeds"])),
            raw_incompatible_seeds=_parse_seed_list(str(row["raw_incompatible_seeds"])),
        )
        for row in rows
    ]


def scene_edit_compatible_rows(rows: list[SceneEditProbeRow]) -> list[SceneEditProbeRow]:
    return [
        row
        for row in rows
        if row.raw_state_compatible_count == row.seed_count and row.processed_state_compatible_count == row.seed_count
    ]


def scene_edit_gated_rows(rows: list[SceneEditProbeRow]) -> list[SceneEditProbeRow]:
    return [row for row in rows if row.requires_official_scene_edit_for_all_seeds]


def compatible_benchmarks(rows: list[SceneEditProbeRow]) -> list[str]:
    compatible = scene_edit_compatible_rows(rows)
    benchmark_names = sorted({row.benchmark for row in compatible})
    return benchmark_names


def compatible_tasks_per_benchmark(rows: list[SceneEditProbeRow], benchmarks: list[str]) -> int:
    if not benchmarks:
        return 0
    counts: list[int] = []
    for benchmark in benchmarks:
        counts.append(len([row for row in rows if row.benchmark == benchmark and row in scene_edit_compatible_rows(rows)]))
    return min(counts) if counts else 0


def _latest_probe_summary_path() -> Path:
    candidates = sorted(ARTIFACTS_DIR.glob("audits/scene_edit_compatibility_probe*_summary.csv"))
    if not candidates:
        raise FileNotFoundError("No scene-edit compatibility probe summary was found under artifacts/audits.")
    return candidates[-1]


def _extract_scene_edit_delta(success_delta_path: Path) -> dict[str, object]:
    with success_delta_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if str(row["factor"]) == "scene_edit_effect":
            return {
                "transition": str(row["transition"]),
                "from_success_rate": float(row["from_success_rate"]),
                "to_success_rate": float(row["to_success_rate"]),
                "success_rate_delta": float(row["success_rate_delta"]),
                "interpretation": str(row["interpretation"]),
            }
    raise RuntimeError(f"No scene_edit_effect row found in {success_delta_path}.")


def _run_official_alignment_subset(
    *,
    node: str,
    benchmarks: list[str],
    tasks_per_benchmark: int,
    seeds: str,
    playground_seeds: str,
    smoke_seeds: str,
) -> dict[str, object]:
    command = [
        sys.executable,
        "-m",
        "grasp_benchmark.audit.graspvla_official_alignment",
        "--node",
        node,
        "--benchmarks",
        ",".join(benchmarks),
        "--tasks-per-benchmark",
        str(tasks_per_benchmark),
        "--smoke-benchmarks",
        benchmarks[0],
        "--smoke-task-count",
        "1",
        "--smoke-seeds",
        smoke_seeds,
        "--seeds",
        seeds,
        "--playground-seeds",
        playground_seeds,
        "--force-attribution",
    ]
    result = run_command(command, cwd=ARTIFACTS_DIR.parent, timeout=14400)
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "Failed to run scene-edit isolation alignment audit.")
    payload = json.loads(result.stdout)
    payload["stdout"] = result.stdout
    payload["stderr"] = result.stderr
    return payload


def _render_report(
    *,
    compatible_rows: list[SceneEditProbeRow],
    gated_rows: list[SceneEditProbeRow],
    child_audit_root: Path,
    scene_edit_delta: dict[str, object],
    parent_root: Path,
) -> tuple[str, str]:
    track_a_cal = _load_track_a_cal_reference()
    delta = float(scene_edit_delta["success_rate_delta"])
    if abs(delta) <= 0.02:
        scene_edit_summary = "nearly no measurable performance effect"
        scene_edit_summary_zh = "几乎没有可测的性能影响"
    elif abs(delta) <= 0.1:
        scene_edit_summary = "a modest measurable performance effect"
        scene_edit_summary_zh = "有一个有限但可测的性能影响"
    else:
        scene_edit_summary = "a large measurable performance effect"
        scene_edit_summary_zh = "有一个明显且较大的性能影响"
    compatible_table = [
        "| benchmark | task_id | task_name | instruction |",
        "| --- | --- | --- | --- |",
    ]
    for row in compatible_rows:
        compatible_table.append(
            f"| {row.benchmark} | {row.task_id} | {row.task_name} | {row.instruction} |"
        )
    gated_table = [
        "| benchmark | task_id | task_name | incompatible_seeds |",
        "| --- | --- | --- | --- |",
    ]
    for row in gated_rows:
        gated_table.append(
            f"| {row.benchmark} | {row.task_id} | {row.task_name} | {', '.join(str(seed) for seed in row.raw_incompatible_seeds)} |"
        )

    report_lines = [
        "# GraspVLA Scene-Edit Isolation Audit",
        "",
        "## Headline",
        "",
        "- Basket-linked official tasks are not just harder without scene edits; in the current public release they become incompatible with raw init states.",
        "- A clean scene-edit performance delta can still be measured on the scene-edit-compatible overlap subset.",
        f"- On that compatible subset, `V3 -> V4` changes success rate from `{scene_edit_delta['from_success_rate']:.4f}` to `{scene_edit_delta['to_success_rate']:.4f}` (`{scene_edit_delta['success_rate_delta']:+.4f}`).",
        f"- The latest formal Track A-Cal reference remains `{track_a_cal['graspvla_successes']}/{track_a_cal['graspvla_trials']}`.",
        "",
        "## Compatible Overlap Subset",
        "",
        *compatible_table,
        "",
        "These are the official tasks that remain runnable without method-specific scene edits.",
        "",
        "## Scene-Edit Compatibility Gate",
        "",
        *gated_table,
        "",
        "These tasks require the official `process_initial_state` transformation in the current public release, so they cannot be used for a clean no-scene-edit like-for-like ablation.",
        "",
        "## Quantified Scene-Edit Effect",
        "",
        f"- Child audit root: [{child_audit_root.name}]({child_audit_root.as_posix()})",
        f"- Transition: `{scene_edit_delta['transition']}`",
        f"- Success-rate delta: `{scene_edit_delta['success_rate_delta']:+.4f}`",
        f"- Interpretation: `{scene_edit_delta['interpretation']}`",
        "",
        "## Practical Conclusion",
        "",
        "- The public release boundary should be stated in two layers:",
        "  - basket-linked official tasks: scene edits are a compatibility requirement",
        f"  - scene-edit-compatible official tasks: scene edits have {scene_edit_summary}",
        "- This means the earlier large result gap should not be explained as a pure scene-edit effect.",
        "- The current best explanation remains:",
        "  - gripper change is small",
        "  - shared success rule matters a lot",
        "  - basket-linked scene edits are a release-boundary constraint",
        "  - latest Track A-Cal is runnable and should no longer be described as all-zero",
        "",
        f"_Generated from probe and child audit under `{parent_root.name}`._",
    ]

    teacher_lines = [
        "# GraspVLA scene-edit 因子隔离结论",
        "",
        "- 这次已经把 `scene edit` 分成两层讲清楚了。",
        f"- 在可兼容子集上，`V3 -> V4` 的 success rate 变化是 `{scene_edit_delta['success_rate_delta']:+.4f}`，属于有限但真实的影响。",
        "- 但在 basket 相关官方任务上，scene edit 不是单纯影响分数，而是公开 release 的兼容性门槛。",
        f"- 最新正式 `Track A-Cal` 仍是 `{track_a_cal['graspvla_successes']}/{track_a_cal['graspvla_trials']}`，所以 shared calibration 不该再按旧的全 0 口径描述。",
        "",
        "## 该怎么对外解释",
        "",
        "- `2 cm` 加长爪子不是主因。",
        "- 更严格的 shared success rule 是目前最大的单一可测因素。",
        "- `scene edit` 重要，但要分两层：",
        f"- 对 `libero_goal` 这类兼容任务来说，它目前{scene_edit_summary_zh}。",
        "- 对 basket 相关官方任务来说，它还是公开 release 的兼容性边界。",
    ]
    return "\n".join(report_lines) + "\n", "\n".join(teacher_lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolate the official GraspVLA scene-edit effect on the compatible overlap subset.")
    parser.add_argument("--node", default="em14")
    parser.add_argument("--probe-summary", default="")
    parser.add_argument("--seeds", default="0,1,2,3,4,5,6,7,8,9")
    parser.add_argument("--playground-seeds", default="")
    parser.add_argument("--smoke-seeds", default="0,1")
    args = parser.parse_args()

    probe_summary_path = Path(args.probe_summary) if args.probe_summary else _latest_probe_summary_path()
    rows = load_scene_edit_probe_summary(probe_summary_path)
    compatible_rows = scene_edit_compatible_rows(rows)
    gated_rows = scene_edit_gated_rows(rows)
    compatible_sets = compatible_benchmarks(rows)
    tasks_per_benchmark = compatible_tasks_per_benchmark(rows, compatible_sets)
    if not compatible_sets or tasks_per_benchmark <= 0:
        raise RuntimeError("No scene-edit-compatible official subset was found.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date_token = timestamp[:8]
    parent_root = ensure_dir(ARTIFACTS_DIR / "audits" / f"{timestamp}_graspvla_scene_edit_isolation")
    shutil.copy2(probe_summary_path, parent_root / probe_summary_path.name)

    child_payload = _run_official_alignment_subset(
        node=args.node,
        benchmarks=compatible_sets,
        tasks_per_benchmark=tasks_per_benchmark,
        seeds=args.seeds,
        playground_seeds=args.playground_seeds,
        smoke_seeds=args.smoke_seeds,
    )
    child_audit_root = Path(str(child_payload["audit_root"]))
    child_success_delta_path = child_audit_root / "success_delta.csv"
    child_summary_path = child_audit_root / "summary.csv"
    child_report_path = child_audit_root / "report.md"
    scene_edit_delta = _extract_scene_edit_delta(child_success_delta_path)

    report_text, teacher_text = _render_report(
        compatible_rows=compatible_rows,
        gated_rows=gated_rows,
        child_audit_root=child_audit_root,
        scene_edit_delta=scene_edit_delta,
        parent_root=parent_root,
    )
    _write_text(parent_root / "report.md", report_text)
    _write_text(parent_root / "teacher_summary_zh.md", teacher_text)
    _write_text(parent_root / "teacher_summary_zh_clean.md", teacher_text, encoding="utf-8-sig")
    _write_json(
        parent_root / "report.json",
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "parent_root": str(parent_root),
            "probe_summary_path": str(probe_summary_path),
            "compatible_benchmarks": compatible_sets,
            "tasks_per_benchmark": tasks_per_benchmark,
            "child_audit_root": str(child_audit_root),
            "child_summary_path": str(child_summary_path),
            "child_report_path": str(child_report_path),
            "scene_edit_delta": scene_edit_delta,
            "local_commit": resolve_commit(),
        },
    )
    _write_csv(
        parent_root / "compatible_subset.csv",
        [
            {
                "benchmark": row.benchmark,
                "task_id": row.task_id,
                "task_name": row.task_name,
                "instruction": row.instruction,
            }
            for row in compatible_rows
        ],
    )
    _write_csv(
        parent_root / "scene_edit_gate.csv",
        [
            {
                "benchmark": row.benchmark,
                "task_id": row.task_id,
                "task_name": row.task_name,
                "raw_incompatible_seeds": ", ".join(str(seed) for seed in row.raw_incompatible_seeds),
            }
            for row in gated_rows
        ],
    )
    docs_dir = _docs_reports_dir()
    _write_text(docs_dir / f"graspvla_scene_edit_isolation_{date_token}.md", report_text)
    _write_text(docs_dir / f"graspvla_scene_edit_isolation_{date_token}_zh.md", teacher_text, encoding="utf-8-sig")
    print(
        json.dumps(
            {
                "audit_root": str(parent_root),
                "child_audit_root": str(child_audit_root),
                "compatible_benchmarks": compatible_sets,
                "tasks_per_benchmark": tasks_per_benchmark,
                "scene_edit_delta": scene_edit_delta,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
