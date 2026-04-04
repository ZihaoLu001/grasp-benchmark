from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.shell import run_command


@dataclass(frozen=True, slots=True)
class AuditVariant:
    name: str
    execution_mode: str
    task_set: str
    agent_mode: str = ""
    robot_profile: str = ""
    success_mode: str = ""
    scene_edit_policy: str = ""
    run_playground_sanity: bool = False


VARIANTS = (
    AuditVariant(
        name="V0_official_runner",
        execution_mode="official_aligned_sim",
        task_set="official_alignment_subset",
        agent_mode="official_runner",
        robot_profile="extended_finger",
        success_mode="env_done",
        scene_edit_policy="official",
        run_playground_sanity=True,
    ),
    AuditVariant(
        name="V1_wrapper_official_parity",
        execution_mode="official_aligned_sim",
        task_set="official_alignment_subset",
        agent_mode="wrapper",
        robot_profile="extended_finger",
        success_mode="env_done",
        scene_edit_policy="official",
        run_playground_sanity=True,
    ),
    AuditVariant(
        name="V2_shared_gripper",
        execution_mode="official_aligned_sim",
        task_set="official_alignment_subset",
        agent_mode="wrapper",
        robot_profile="plain_franka",
        success_mode="env_done",
        scene_edit_policy="official",
    ),
    AuditVariant(
        name="V3_shared_success",
        execution_mode="official_aligned_sim",
        task_set="official_alignment_subset",
        agent_mode="wrapper",
        robot_profile="plain_franka",
        success_mode="shared_lift_hold",
        scene_edit_policy="official",
    ),
    AuditVariant(
        name="V4_no_method_specific_scene_edits",
        execution_mode="official_aligned_sim",
        task_set="official_alignment_subset",
        agent_mode="wrapper",
        robot_profile="plain_franka",
        success_mode="shared_lift_hold",
        scene_edit_policy="shared_only",
    ),
    AuditVariant(
        name="V5_track_a_cal_distribution",
        execution_mode="shared_track_a_sim",
        task_set="track_a_cal_v1",
    ),
)


def _write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _fetch_remote_results(node: str, remote_run_dir: str, local_run_dir: Path) -> None:
    ensure_dir(local_run_dir)
    result = run_command(["scp", "-r", f"{node}:{remote_run_dir}/.", str(local_run_dir)], timeout=14400)
    (local_run_dir / "fetch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (local_run_dir / "fetch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "Failed to fetch remote audit artifacts.")


def _build_remote_worker_command(
    *,
    cluster_config: dict[str, Any],
    method_config: dict[str, Any],
    variant: AuditVariant,
    sensor_config_name: str,
    remote_output_dir: str,
    parent_run_id: str,
    benchmarks: str,
    task_count: int,
    seeds: str,
    playground_seeds: str,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["official_sim_env_name"]}'
    official_flags = ""
    if variant.execution_mode == "official_aligned_sim":
        playground_flag = "--official-run-playground-sanity" if variant.run_playground_sanity else ""
        official_flags = (
            f'--official-benchmarks "{benchmarks}" '
            f'--official-task-count "{task_count}" '
            f'--official-seeds "{seeds}" '
            f'--official-playground-seeds "{playground_seeds}" '
            f'--official-variant-name "{variant.name}" '
            f'--official-agent-mode "{variant.agent_mode}" '
            f'--official-robot-profile "{variant.robot_profile}" '
            f'--official-success-mode "{variant.success_mode}" '
            f'--official-scene-edit-policy "{variant.scene_edit_policy}" '
            f"{playground_flag}"
        ).strip()
    return (
        f'mkdir -p "{remote_output_dir}" && '
        f'source "{miniforge_root}/etc/profile.d/conda.sh" && '
        f'conda activate "{env_prefix}" && '
        f'cd "{remote_root}" && '
        f'export PYTHONPATH="{remote_root}/src${{PYTHONPATH:+:${{PYTHONPATH}}}}" && '
        f'python -m grasp_benchmark.run.worker '
        f'--method "graspvla" '
        f'--task-set "{variant.task_set}" '
        f'--sensor-config "{sensor_config_name}" '
        f'--output-dir "{remote_output_dir}" '
        f'--execution-mode "{variant.execution_mode}" '
        f'--parent-run-id "{parent_run_id}" '
        f'{official_flags}'
    ).strip()


def _read_results(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _compare_variant_rows(reference_rows: list[dict[str, str]], candidate_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    ref_by_scene = {str(row["scene_id"]): row for row in reference_rows}
    cand_by_scene = {str(row["scene_id"]): row for row in candidate_rows}
    scene_ids = sorted(set(ref_by_scene) | set(cand_by_scene))
    diffs: list[dict[str, object]] = []
    for scene_id in scene_ids:
        ref = ref_by_scene.get(scene_id)
        cand = cand_by_scene.get(scene_id)
        issues: list[str] = []
        if ref is None:
            issues.append("missing_in_reference")
        if cand is None:
            issues.append("missing_in_candidate")
        if ref and cand:
            if int(ref["success"]) != int(cand["success"]):
                issues.append("success_mismatch")
            if str(ref["object_id"]) != str(cand["object_id"]):
                issues.append("object_id_mismatch")
            if str(ref["instruction"]) != str(cand["instruction"]):
                issues.append("instruction_mismatch")
        row = {
            "scene_id": scene_id,
            "reference_task": "" if ref is None else ref["task"],
            "candidate_task": "" if cand is None else cand["task"],
            "reference_object_id": "" if ref is None else ref["object_id"],
            "candidate_object_id": "" if cand is None else cand["object_id"],
            "reference_instruction": "" if ref is None else ref["instruction"],
            "candidate_instruction": "" if cand is None else cand["instruction"],
            "reference_success": "" if ref is None else ref["success"],
            "candidate_success": "" if cand is None else cand["success"],
            "reference_video_path": "" if ref is None else ref["video_path"],
            "candidate_video_path": "" if cand is None else cand["video_path"],
            "mismatch": int(bool(issues)),
            "mismatch_reason": ", ".join(issues),
        }
        diffs.append(row)
    return diffs


def _summary_row(variant: AuditVariant, variant_dir: Path) -> dict[str, object]:
    rows = _read_results(variant_dir / "results.csv")
    setup_error = ""
    metadata_path = variant_dir / "run_metadata.json"
    if metadata_path.exists():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        setup_error = str(payload.get("setup_error", ""))
    main_rows = [row for row in rows if row["task"] != "playground"]
    playground_rows = [row for row in rows if row["task"] == "playground"]
    main_successes = sum(int(row["success"]) for row in main_rows)
    playground_successes = sum(int(row["success"]) for row in playground_rows)
    return {
        "variant": variant.name,
        "execution_mode": variant.execution_mode,
        "task_set": variant.task_set,
        "trials": len(main_rows),
        "successes": main_successes,
        "success_rate": round(main_successes / len(main_rows), 4) if main_rows else 0.0,
        "playground_trials": len(playground_rows),
        "playground_successes": playground_successes,
        "playground_success_rate": round(playground_successes / len(playground_rows), 4) if playground_rows else 0.0,
        "results_path": str(variant_dir / "results.csv"),
        "setup_error": setup_error,
    }


def _run_variant(
    *,
    node: str,
    cluster_config: dict[str, Any],
    method_config: dict[str, Any],
    sensor_config_name: str,
    audit_root: Path,
    remote_root: str,
    parent_run_id: str,
    variant: AuditVariant,
    benchmarks: str,
    task_count: int,
    seeds: str,
    playground_seeds: str,
) -> Path:
    local_variant_dir = ensure_dir(audit_root / variant.name)
    remote_variant_dir = f"{remote_root}/{variant.name}"
    remote_command = _build_remote_worker_command(
        cluster_config=cluster_config,
        method_config=method_config,
        variant=variant,
        sensor_config_name=sensor_config_name,
        remote_output_dir=remote_variant_dir,
        parent_run_id=parent_run_id,
        benchmarks=benchmarks,
        task_count=task_count,
        seeds=seeds,
        playground_seeds=playground_seeds,
    )
    result = run_command(["ssh", "-o", "BatchMode=yes", node, f"bash -lc '{remote_command}'"], timeout=14400)
    (local_variant_dir / "dispatch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (local_variant_dir / "dispatch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or f"Failed to dispatch {variant.name}.")
    _fetch_remote_results(node, remote_variant_dir, local_variant_dir)
    return local_variant_dir


def _write_report(
    *,
    audit_root: Path,
    parity_passed: bool,
    summary_rows: list[dict[str, object]],
    diff_rows: list[dict[str, object]],
    mismatch_rows: list[dict[str, object]],
) -> None:
    setup_errors = [str(row.get("setup_error", "")).strip() for row in summary_rows if str(row.get("setup_error", "")).strip()]
    setup_blocked = bool(setup_errors) and all(int(row.get("trials", 0)) == 0 for row in summary_rows)
    lines = [
        "# GraspVLA Official Alignment Audit",
        "",
        f"- parity_status: `{'passed' if parity_passed else 'failed'}`",
        "",
        "## Variant Summary",
        "",
        "| variant | execution_mode | task_set | trials | successes | success_rate | playground_trials | playground_successes | playground_success_rate | setup_error |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['variant']} | {row['execution_mode']} | {row['task_set']} | {row['trials']} | {row['successes']} | {row['success_rate']} | {row['playground_trials']} | {row['playground_successes']} | {row['playground_success_rate']} | {row['setup_error']} |"
        )
    lines.extend(["", "## V0 vs V1 Diff", ""])
    if diff_rows:
        lines.extend(
            [
                "| scene_id | reference_object_id | candidate_object_id | reference_success | candidate_success | mismatch_reason |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in diff_rows:
            lines.append(
                f"| {row['scene_id']} | {row['reference_object_id']} | {row['candidate_object_id']} | {row['reference_success']} | {row['candidate_success']} | {row['mismatch_reason']} |"
            )
    else:
        lines.append("_No rows._")
    lines.extend(["", "## Audit Conclusion", ""])
    if setup_blocked:
        lines.append("- The audit was blocked before any official-aligned episode could run. The current public release / runtime combination could not produce a runnable official subset under the requested benchmark list.")
        lines.append("- This means the current `Track A-Cal` result should remain provisional, but the immediate blocker is now clearly an upstream/runtime reproducibility gap rather than a measured wrapper-vs-official behavioral delta.")
    elif parity_passed:
        lines.append("- `V1_wrapper_official_parity` matches the official subset episode-by-episode, so the main Track A gap is more likely caused by protocol / distribution changes than by wrapper implementation drift.")
    else:
        lines.append("- `V1_wrapper_official_parity` does not match the official subset episode-by-episode, so the current Track A result should stay provisional until the shared runner is repaired.")
    if mismatch_rows:
        lines.append("- See `mismatch_episodes.csv` for the failing seeds, tasks, and artifact paths.")
    report_text = "\n".join(lines) + "\n"
    (audit_root / "report.md").write_text(report_text, encoding="utf-8")

    teacher_lines = [
        "# 老师汇报页",
        "",
        f"- 本轮 `GraspVLA` 官方对齐审计结论：`{'wrapper parity passed' if parity_passed else 'wrapper parity failed'}`。",
        "- 这份审计先检查我们的 wrapper 能不能在官方 gripper、官方 success、官方 scene edits 下复现官方 release 子集。",
    ]
    if setup_blocked:
        teacher_lines.append("- 当前的主要问题不是已经测出了 wrapper 和官方行为不同，而是当前公开 release 在这套官方子集上本身没有成功展开出可运行 episode。")
        teacher_lines.append("- 因此，`Track A-Cal` 暂时仍应视为 provisional；下一步优先修的是官方 release / LIBERO 资产与状态对齐问题。")
    elif parity_passed:
        teacher_lines.append("- 当前可以把 `Track A-Cal` 的低分主要解释为 shared benchmark protocol / distribution gap，而不是代码直接坏掉。")
    else:
        teacher_lines.append("- 当前不能把 `Track A-Cal` 的低分直接解释成协议差异，因为 wrapper 和官方子集本身还没有完全对齐。")
    teacher_text = "\n".join(teacher_lines) + "\n"
    (audit_root / "teacher_summary_zh.md").write_text(teacher_text, encoding="utf-8")
    with (audit_root / "teacher_summary_zh_clean.md").open("w", encoding="utf-8-sig") as handle:
        handle.write(teacher_text)
    (audit_root / "report.json").write_text(
        json.dumps(
            {
                "parity_passed": parity_passed,
                "summary": summary_rows,
                "diff_rows": diff_rows,
                "mismatch_rows": mismatch_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit GraspVLA official-release parity on em14.")
    parser.add_argument("--node", default="em14")
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    parser.add_argument("--benchmarks", default="libero_object,libero_10,libero_goal")
    parser.add_argument("--tasks-per-benchmark", type=int, default=2)
    parser.add_argument("--seeds", default="0,1,2,3,4,5,6,7,8,9")
    parser.add_argument("--playground-seeds", default="0,1,2,3,4")
    parser.add_argument("--smoke-benchmarks", default="libero_object")
    parser.add_argument("--smoke-task-count", type=int, default=1)
    parser.add_argument("--smoke-seeds", default="0,1")
    parser.add_argument("--stop-after-parity", action="store_true")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    parent_run_id = f"{timestamp}_graspvla_official_alignment"
    audit_root = ensure_dir(ARTIFACTS_DIR / "audits" / parent_run_id)
    remote_root = f'{cluster_config["remote_root"]}/artifacts/audits/{parent_run_id}'
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node": args.node,
        "parent_run_id": parent_run_id,
        "benchmarks": args.benchmarks,
        "tasks_per_benchmark": args.tasks_per_benchmark,
        "seeds": args.seeds,
        "playground_seeds": args.playground_seeds,
        "variants": [
            {
                "name": variant.name,
                "execution_mode": variant.execution_mode,
                "task_set": variant.task_set,
                "agent_mode": variant.agent_mode,
                "robot_profile": variant.robot_profile,
                "success_mode": variant.success_mode,
                "scene_edit_policy": variant.scene_edit_policy,
                "run_playground_sanity": variant.run_playground_sanity,
            }
            for variant in VARIANTS
        ],
        "local_commit": resolve_commit(),
    }
    _write_json(audit_root / "dispatch_manifest.json", manifest)

    smoke_root = ensure_dir(audit_root / "smoke")
    for variant in VARIANTS[:2]:
        _run_variant(
            node=args.node,
            cluster_config=cluster_config,
            method_config=method_config,
            sensor_config_name=args.sensor_config,
            audit_root=smoke_root,
            remote_root=f"{remote_root}/smoke",
            parent_run_id=f"{parent_run_id}_smoke",
            variant=variant,
            benchmarks=args.smoke_benchmarks,
            task_count=args.smoke_task_count,
            seeds=args.smoke_seeds,
            playground_seeds="0,1",
        )

    variant_dirs: dict[str, Path] = {}
    for variant in VARIANTS[:2]:
        variant_dirs[variant.name] = _run_variant(
            node=args.node,
            cluster_config=cluster_config,
            method_config=method_config,
            sensor_config_name=args.sensor_config,
            audit_root=audit_root,
            remote_root=remote_root,
            parent_run_id=parent_run_id,
            variant=variant,
            benchmarks=args.benchmarks,
            task_count=args.tasks_per_benchmark,
            seeds=args.seeds,
            playground_seeds=args.playground_seeds,
        )

    v0_rows = _read_results(variant_dirs["V0_official_runner"] / "results.csv")
    v1_rows = _read_results(variant_dirs["V1_wrapper_official_parity"] / "results.csv")
    diff_rows = _compare_variant_rows(v0_rows, v1_rows)
    mismatch_rows = [row for row in diff_rows if int(row["mismatch"])]
    expected_full_episodes = (args.tasks_per_benchmark * len([item for item in args.benchmarks.split(",") if item.strip()]) * len([item for item in args.seeds.split(",") if item.strip()])) + len([item for item in args.playground_seeds.split(",") if item.strip()])
    parity_passed = not mismatch_rows and len(v0_rows) == expected_full_episodes and len(v1_rows) == expected_full_episodes
    if len(v0_rows) != expected_full_episodes:
        mismatch_rows.append(
            {
                "scene_id": "__coverage__",
                "reference_task": "",
                "candidate_task": "",
                "reference_object_id": "",
                "candidate_object_id": "",
                "reference_instruction": "",
                "candidate_instruction": "",
                "reference_success": "",
                "candidate_success": "",
                "reference_video_path": "",
                "candidate_video_path": "",
                "mismatch": 1,
                "mismatch_reason": f"reference_episode_count={len(v0_rows)} expected={expected_full_episodes}",
            }
        )
    if len(v1_rows) != expected_full_episodes:
        mismatch_rows.append(
            {
                "scene_id": "__coverage__",
                "reference_task": "",
                "candidate_task": "",
                "reference_object_id": "",
                "candidate_object_id": "",
                "reference_instruction": "",
                "candidate_instruction": "",
                "reference_success": "",
                "candidate_success": "",
                "reference_video_path": "",
                "candidate_video_path": "",
                "mismatch": 1,
                "mismatch_reason": f"candidate_episode_count={len(v1_rows)} expected={expected_full_episodes}",
            }
        )

    if parity_passed and not args.stop_after_parity:
        for variant in VARIANTS[2:]:
            variant_dirs[variant.name] = _run_variant(
                node=args.node,
                cluster_config=cluster_config,
                method_config=method_config,
                sensor_config_name=args.sensor_config,
                audit_root=audit_root,
                remote_root=remote_root,
                parent_run_id=parent_run_id,
                variant=variant,
                benchmarks=args.benchmarks,
                task_count=args.tasks_per_benchmark,
                seeds=args.seeds,
                playground_seeds=args.playground_seeds,
            )

    summary_rows = [_summary_row(variant, variant_dirs[variant.name]) for variant in VARIANTS if variant.name in variant_dirs]
    _write_csv(audit_root / "summary.csv", summary_rows)
    _write_csv(audit_root / "per_episode_diff.csv", diff_rows)
    _write_csv(audit_root / "mismatch_episodes.csv", mismatch_rows)
    _write_report(
        audit_root=audit_root,
        parity_passed=parity_passed,
        summary_rows=summary_rows,
        diff_rows=diff_rows,
        mismatch_rows=mismatch_rows,
    )
    print(json.dumps({"audit_root": str(audit_root), "parity_passed": parity_passed}, indent=2))


if __name__ == "__main__":
    main()
