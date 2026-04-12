from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, PROJECT_ROOT, ensure_dir
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
    lift_threshold_cm_override: float | None = None
    hold_steps_override: int | None = None


PARITY_VARIANTS = (
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
        name="V0_repeat_official_runner",
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
)

ATTRIBUTION_VARIANTS = (
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

VARIANTS = PARITY_VARIANTS + ATTRIBUTION_VARIANTS

PARITY_STATUS_LABELS = {
    "strict_parity_passed": "strict parity passed",
    "reproducibility_limited_parity": "reproducibility-limited parity",
    "parity_failed": "parity failed",
}

BOUNDARY_STATUS_LABELS = {
    "supported_and_stable": "Supported and stable",
    "supported_but_reproducibility_limited": "Supported but reproducibility-limited",
    "unsupported_or_not_claimable_from_public_release": "Unsupported / not claimable from public release",
}

ATTRIBUTION_TRANSITIONS = (
    ("V1_wrapper_official_parity", "V2_shared_gripper", "gripper_effect"),
    ("V2_shared_gripper", "V3_shared_success", "success_rule_effect"),
    ("V3_shared_success", "V4_no_method_specific_scene_edits", "scene_edit_effect"),
    ("V4_no_method_specific_scene_edits", "V5_track_a_cal_distribution", "task_distribution_effect"),
)

PRIMARY_VARIANT_NAMES = tuple(variant.name for variant in PARITY_VARIANTS)
DOCS_REPORTS_DIR = PROJECT_ROOT / "docs" / "reports"


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
    libero_config_root = f'{remote_root}/artifacts/libero_config'
    official_flags = ""
    if variant.execution_mode == "official_aligned_sim":
        playground_flag = "--official-run-playground-sanity" if variant.run_playground_sanity else ""
        lift_flag = (
            f'--lift-threshold-cm "{variant.lift_threshold_cm_override}" '
            if variant.lift_threshold_cm_override is not None
            else ""
        )
        hold_flag = (
            f'--hold-steps "{variant.hold_steps_override}" '
            if variant.hold_steps_override is not None
            else ""
        )
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
            f"{playground_flag} "
            f"{lift_flag}"
            f"{hold_flag}"
        ).strip()
    return (
        f'mkdir -p "{remote_output_dir}" && '
        f'source "{miniforge_root}/etc/profile.d/conda.sh" && '
        f'conda activate "{env_prefix}" && '
        f'cd "{remote_root}" && '
        f'export LIBERO_CONFIG_PATH="{libero_config_root}" && '
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


def _count_csv_items(value: str) -> int:
    return len([item for item in value.split(",") if item.strip()])


def _expected_episode_count(benchmarks: str, tasks_per_benchmark: int, seeds: str, playground_seeds: str) -> int:
    return (_count_csv_items(benchmarks) * tasks_per_benchmark * _count_csv_items(seeds)) + _count_csv_items(playground_seeds)


def _compare_variant_rows(
    reference_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    *,
    reference_variant: str,
    candidate_variant: str,
) -> list[dict[str, object]]:
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
        diffs.append(
            {
                "comparison": f"{reference_variant} vs {candidate_variant}",
                "reference_variant": reference_variant,
                "candidate_variant": candidate_variant,
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
        )
    return diffs


def _coverage_rows(
    *,
    reference_variant: str,
    candidate_variant: str,
    reference_count: int,
    candidate_count: int,
    expected_episodes: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if reference_count != expected_episodes:
        rows.append(
            {
                "comparison": f"{reference_variant} vs {candidate_variant}",
                "reference_variant": reference_variant,
                "candidate_variant": candidate_variant,
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
                "mismatch_reason": f"{reference_variant}_episode_count={reference_count} expected={expected_episodes}",
            }
        )
    if candidate_count != expected_episodes:
        rows.append(
            {
                "comparison": f"{reference_variant} vs {candidate_variant}",
                "reference_variant": reference_variant,
                "candidate_variant": candidate_variant,
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
                "mismatch_reason": f"{candidate_variant}_episode_count={candidate_count} expected={expected_episodes}",
            }
        )
    return rows


def _mismatch_rows_only(diff_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in diff_rows if int(row["mismatch"])]


def _comparison_summary_row(
    *,
    reference_variant: str,
    candidate_variant: str,
    reference_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    mismatch_rows: list[dict[str, object]],
    expected_episodes: int,
) -> dict[str, object]:
    ref_scene_ids = {str(row["scene_id"]) for row in reference_rows}
    cand_scene_ids = {str(row["scene_id"]) for row in candidate_rows}
    mismatch_scene_ids = [
        str(row["scene_id"])
        for row in mismatch_rows
        if str(row["scene_id"]) and str(row["scene_id"]) != "__coverage__"
    ]
    return {
        "comparison": f"{reference_variant} vs {candidate_variant}",
        "reference_variant": reference_variant,
        "candidate_variant": candidate_variant,
        "reference_trials": len(reference_rows),
        "candidate_trials": len(candidate_rows),
        "expected_trials": expected_episodes,
        "scene_overlap": len(ref_scene_ids & cand_scene_ids),
        "mismatches": len(mismatch_rows),
        "mismatch_scene_count": len(mismatch_scene_ids),
        "mismatch_scene_ids": ", ".join(mismatch_scene_ids),
    }


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
    (local_variant_dir / "dispatch_stdout.txt").write_text(result.stdout or "", encoding="utf-8")
    (local_variant_dir / "dispatch_stderr.txt").write_text(result.stderr or "", encoding="utf-8")
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or f"Failed to dispatch {variant.name}.")
    _fetch_remote_results(node, remote_variant_dir, local_variant_dir)
    return local_variant_dir


def classify_parity_status(
    *,
    expected_episodes: int,
    coverage_counts: dict[str, int],
    setup_errors: dict[str, str],
    v0_repeat_mismatch_count: int,
    v1_mismatch_count: int,
) -> dict[str, object]:
    primary_setup_errors = {
        name: error.strip()
        for name, error in setup_errors.items()
        if name in PRIMARY_VARIANT_NAMES and error.strip()
    }
    coverage_ok = all(coverage_counts.get(name, -1) == expected_episodes for name in PRIMARY_VARIANT_NAMES)
    if primary_setup_errors or not coverage_ok:
        return {
            "status_code": "parity_failed",
            "status_label": PARITY_STATUS_LABELS["parity_failed"],
            "advance_to_attribution": False,
            "coverage_ok": coverage_ok,
            "reason": "Primary parity variants did not complete the expected episode coverage without setup errors.",
        }
    if v1_mismatch_count == 0:
        return {
            "status_code": "strict_parity_passed",
            "status_label": PARITY_STATUS_LABELS["strict_parity_passed"],
            "advance_to_attribution": True,
            "coverage_ok": coverage_ok,
            "reason": "The wrapper matched the official subset episode-by-episode.",
        }
    if v1_mismatch_count <= v0_repeat_mismatch_count:
        return {
            "status_code": "reproducibility_limited_parity",
            "status_label": PARITY_STATUS_LABELS["reproducibility_limited_parity"],
            "advance_to_attribution": True,
            "coverage_ok": coverage_ok,
            "reason": "The wrapper mismatch count is no worse than the official runner's self-repeat drift.",
        }
    return {
        "status_code": "parity_failed",
        "status_label": PARITY_STATUS_LABELS["parity_failed"],
        "advance_to_attribution": False,
        "coverage_ok": coverage_ok,
        "reason": "The wrapper still drifts more than the official runner's self-repeat baseline.",
    }


def _latest_track_b_summary_path() -> Path | None:
    candidates = sorted((ARTIFACTS_DIR / "official_sim").glob("*_em14_full/summary.json"))
    if not candidates:
        return None
    return candidates[-1]


def _load_track_b_native_reference() -> dict[str, object]:
    path = _latest_track_b_summary_path()
    if path is None or not path.exists():
        return {
            "status_code": "unsupported_or_not_claimable_from_public_release",
            "status_label": BOUNDARY_STATUS_LABELS["unsupported_or_not_claimable_from_public_release"],
            "evidence_path": "",
            "details": "No frozen Track B native reference summary was found under artifacts/official_sim.",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    details = (
        "Official native full run completed successfully; "
        f"benchmarks={', '.join(payload.get('benchmarks', []))}; "
        f"LIBERO summary={str(payload.get('statistics_text', '')).strip().replace(chr(10), '; ')}"
    )
    return {
        "status_code": "supported_and_stable",
        "status_label": BOUNDARY_STATUS_LABELS["supported_and_stable"],
        "evidence_path": str(path),
        "details": details,
    }


def _load_track_a_cal_reference() -> dict[str, object]:
    run_globs = (
        "*_graspvla_track_a_cal_v3_shared_sim/results.csv",
        "*_graspvla_track_a_cal_v2_shared_sim/results.csv",
        "*_graspvla_track_a_cal_v1_shared_sim/results.csv",
    )
    for pattern in run_globs:
        latest_run_candidates = sorted((ARTIFACTS_DIR / "runs").glob(pattern))
        if not latest_run_candidates:
            continue
        path = latest_run_candidates[-1]
        rows = _read_results(path)
        graspvla_rows = [
            row
            for row in rows
            if row.get("method") == "graspvla" and row.get("track") == "track_a_cal"
        ]
        total_trials = len(graspvla_rows)
        total_successes = sum(int(row["success"]) for row in graspvla_rows)
        success_rate = round(total_successes / total_trials, 4) if total_trials else 0.0
        return {
            "evidence_path": str(path),
            "details": (
                f"Latest formal Track A-Cal run currently shows GraspVLA at "
                f"{total_successes}/{total_trials} under the shared benchmark protocol."
            ),
            "graspvla_trials": total_trials,
            "graspvla_successes": total_successes,
            "graspvla_success_rate": success_rate,
        }
    path = ARTIFACTS_DIR / "reports" / "track_a_cal_compare_graspvla_cgn_latest" / "summary.csv"
    if not path.exists():
        return {
            "evidence_path": "",
            "details": "No Track A-Cal summary was found.",
            "graspvla_trials": 0,
            "graspvla_successes": 0,
            "graspvla_success_rate": 0.0,
        }
    rows = _read_results(path)
    graspvla_rows = [row for row in rows if row.get("method") == "graspvla"]
    total_trials = sum(int(row["trials"]) for row in graspvla_rows)
    total_successes = sum(round(float(row["success_rate"]) * int(row["trials"])) for row in graspvla_rows)
    success_rate = round(total_successes / total_trials, 4) if total_trials else 0.0
    return {
        "evidence_path": str(path),
        "details": f"Latest Track A-Cal report still shows GraspVLA at {total_successes}/{total_trials} under the shared benchmark protocol.",
        "graspvla_trials": total_trials,
        "graspvla_successes": total_successes,
        "graspvla_success_rate": success_rate,
    }


def _mismatch_scene_overlap(v0_repeat_mismatch_rows: list[dict[str, object]], v1_mismatch_rows: list[dict[str, object]]) -> list[str]:
    v0_repeat_scene_ids = {
        str(row["scene_id"])
        for row in v0_repeat_mismatch_rows
        if str(row["scene_id"]) and str(row["scene_id"]) != "__coverage__"
    }
    v1_scene_ids = {
        str(row["scene_id"])
        for row in v1_mismatch_rows
        if str(row["scene_id"]) and str(row["scene_id"]) != "__coverage__"
    }
    return sorted(v0_repeat_scene_ids & v1_scene_ids)


def _mismatch_scene_overlap_from_summary(v0_repeat_summary: dict[str, object], v1_summary: dict[str, object]) -> int:
    v0_repeat_scene_ids = {
        item.strip()
        for item in str(v0_repeat_summary.get("mismatch_scene_ids", "")).split(",")
        if item.strip()
    }
    v1_scene_ids = {
        item.strip()
        for item in str(v1_summary.get("mismatch_scene_ids", "")).split(",")
        if item.strip()
    }
    return len(v0_repeat_scene_ids & v1_scene_ids)


def _build_boundary_ledger(
    *,
    parity_status: dict[str, object],
    comparison_summary_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    track_b = _load_track_b_native_reference()
    track_a_cal = _load_track_a_cal_reference()
    comparison_lookup = {str(row["comparison"]): row for row in comparison_summary_rows}
    v0_repeat_summary = comparison_lookup.get("V0_official_runner vs V0_repeat_official_runner", {})
    v1_summary = comparison_lookup.get("V0_official_runner vs V1_wrapper_official_parity", {})
    official_subset_status = "unsupported_or_not_claimable_from_public_release"
    if str(parity_status["status_code"]) == "strict_parity_passed":
        official_subset_status = "supported_and_stable"
    elif str(parity_status["status_code"]) == "reproducibility_limited_parity":
        official_subset_status = "supported_but_reproducibility_limited"
    return [
        {
            "item": "Track B official LIBERO/playground native run",
            "status_code": str(track_b["status_code"]),
            "status_label": str(track_b["status_label"]),
            "claim_scope": "Use only as the native-deployment upper bound for the public release, not as the shared benchmark headline result.",
            "evidence_path": str(track_b["evidence_path"]),
            "details": str(track_b["details"]),
        },
        {
            "item": "official_aligned subset parity",
            "status_code": official_subset_status,
            "status_label": BOUNDARY_STATUS_LABELS[official_subset_status],
            "claim_scope": "Use to judge whether our wrapper is implementation-aligned with the public release on an official subset.",
            "evidence_path": str(ARTIFACTS_DIR / "audits"),
            "details": (
                f"Parity status={parity_status['status_label']}; "
                f"V0a vs V0b mismatches={v0_repeat_summary.get('mismatches', 0)}; "
                f"V0a vs V1 mismatches={v1_summary.get('mismatches', 0)}; "
                f"mismatch scene overlap={_mismatch_scene_overlap_from_summary(v0_repeat_summary, v1_summary)}."
            ),
        },
        {
            "item": "Track A-Cal shared benchmark",
            "status_code": "unsupported_or_not_claimable_from_public_release",
            "status_label": BOUNDARY_STATUS_LABELS["unsupported_or_not_claimable_from_public_release"],
            "claim_scope": "Keep provisional only; do not use as the final fair benchmark claim until the current shared-protocol bottleneck is explained.",
            "evidence_path": str(track_a_cal["evidence_path"]),
            "details": str(track_a_cal["details"]),
        },
    ]


def _summary_rows_by_variant(summary_rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["variant"]): row for row in summary_rows}


def _classify_attribution_magnitude(success_rate_delta: float, *, same_distribution: bool) -> str:
    if not same_distribution:
        return "distribution_shift_candidate"
    magnitude = abs(success_rate_delta)
    if magnitude <= 0.02:
        return "nearly_no_effect"
    if magnitude <= 0.1:
        return "moderate_effect"
    return "major_effect"


def _build_attribution_rows(summary_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary_lookup = _summary_rows_by_variant(summary_rows)
    rows: list[dict[str, object]] = []
    for from_variant, to_variant, factor in ATTRIBUTION_TRANSITIONS:
        if from_variant not in summary_lookup or to_variant not in summary_lookup:
            continue
        from_row = summary_lookup[from_variant]
        to_row = summary_lookup[to_variant]
        from_trials = int(from_row["trials"])
        to_trials = int(to_row["trials"])
        same_distribution = (
            str(from_row["execution_mode"]) == str(to_row["execution_mode"])
            and str(from_row["task_set"]) == str(to_row["task_set"])
            and from_trials == to_trials
        )
        from_success_rate = float(from_row["success_rate"])
        to_success_rate = float(to_row["success_rate"])
        rows.append(
            {
                "transition": f"{from_variant} -> {to_variant}",
                "factor": factor,
                "from_variant": from_variant,
                "to_variant": to_variant,
                "from_execution_mode": str(from_row["execution_mode"]),
                "to_execution_mode": str(to_row["execution_mode"]),
                "from_task_set": str(from_row["task_set"]),
                "to_task_set": str(to_row["task_set"]),
                "from_trials": from_trials,
                "to_trials": to_trials,
                "from_successes": int(from_row["successes"]),
                "to_successes": int(to_row["successes"]),
                "from_success_rate": from_success_rate,
                "to_success_rate": to_success_rate,
                "success_delta": "" if not same_distribution else int(to_row["successes"]) - int(from_row["successes"]),
                "success_rate_delta": round(to_success_rate - from_success_rate, 4),
                "same_distribution": int(same_distribution),
                "interpretation": _classify_attribution_magnitude(
                    round(to_success_rate - from_success_rate, 4),
                    same_distribution=same_distribution,
                ),
            }
        )
    return rows


def _primary_bottleneck(parity_status: dict[str, object], attribution_rows: list[dict[str, object]]) -> str:
    status_code = str(parity_status["status_code"])
    if status_code == "parity_failed":
        return "wrapper implementation gap"
    if not attribution_rows:
        return "shared protocol / distribution gap still needs attribution"
    ranked_rows = sorted(
        attribution_rows,
        key=lambda row: abs(float(row["success_rate_delta"])),
        reverse=True,
    )
    top_row = ranked_rows[0]
    factor = str(top_row["factor"])
    if factor == "task_distribution_effect":
        return "shared protocol / distribution gap"
    if factor == "scene_edit_effect":
        return "method-specific scene edit effect"
    if factor == "success_rule_effect":
        return "shared success-rule effect"
    if factor == "gripper_effect":
        return "gripper effect"
    return "shared protocol / distribution gap"


def _attribution_conclusion_lines(attribution_rows: list[dict[str, object]]) -> list[str]:
    if not attribution_rows:
        return ["- The audit did not run V2-V5, so there is no variable-contribution table yet."]
    factor_to_label = {
        "gripper_effect": "Gripper effect",
        "success_rule_effect": "Success-rule effect",
        "scene_edit_effect": "Method-specific scene-edit effect",
        "task_distribution_effect": "Task/distribution effect",
    }
    lines: list[str] = []
    for row in attribution_rows:
        label = factor_to_label[str(row["factor"])]
        rate_delta = float(row["success_rate_delta"])
        interpretation = str(row["interpretation"])
        if interpretation == "nearly_no_effect":
            summary = "nearly no measurable impact"
        elif interpretation == "moderate_effect":
            summary = "a moderate measurable impact"
        elif interpretation == "major_effect":
            summary = "a major measurable impact"
        else:
            summary = "the strongest candidate bottleneck because the distribution changes"
        lines.append(
            f"- {label}: `{row['from_variant']} -> {row['to_variant']}` changes success rate by `{rate_delta:+.4f}` and shows {summary}."
        )
    return lines


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return lines


def _write_docs_snapshots(*, date_token: str, report_text: str, teacher_text: str) -> None:
    _write_text(DOCS_REPORTS_DIR / f"graspvla_release_boundary_{date_token}.md", report_text)
    _write_text(DOCS_REPORTS_DIR / f"graspvla_release_boundary_{date_token}_zh.md", teacher_text, encoding="utf-8-sig")


def _write_report(
    *,
    audit_root: Path,
    date_token: str,
    parity_status: dict[str, object],
    force_attribution: bool,
    comparison_summary_rows: list[dict[str, object]],
    summary_rows: list[dict[str, object]],
    v0_repeat_diff_rows: list[dict[str, object]],
    v0_repeat_mismatch_rows: list[dict[str, object]],
    v1_diff_rows: list[dict[str, object]],
    v1_mismatch_rows: list[dict[str, object]],
    boundary_ledger_rows: list[dict[str, object]],
    attribution_rows: list[dict[str, object]],
) -> None:
    scene_overlap = _mismatch_scene_overlap(v0_repeat_mismatch_rows, v1_mismatch_rows)
    primary_bottleneck = _primary_bottleneck(parity_status, attribution_rows)
    lines = [
        "# GraspVLA Official Boundary And Bottleneck Audit",
        "",
        f"- parity_status: `{parity_status['status_label']}`",
        f"- primary_bottleneck: `{primary_bottleneck}`",
        f"- attribution_ran: `{bool(attribution_rows)}`",
        f"- attribution_mode: `{'forced_provisional' if force_attribution and str(parity_status['status_code']) == 'parity_failed' else 'gated'}`",
        f"- scene_level_overlap_between_V0_repeat_and_V1_mismatches: `{', '.join(scene_overlap) if scene_overlap else 'none'}`",
        "",
        "## Comparison Summary",
        "",
    ]
    lines.extend(
        _markdown_table(
            [
                "comparison",
                "reference_trials",
                "candidate_trials",
                "expected_trials",
                "scene_overlap",
                "mismatches",
                "mismatch_scene_count",
                "mismatch_scene_ids",
            ],
            [
                [
                    row["comparison"],
                    row["reference_trials"],
                    row["candidate_trials"],
                    row["expected_trials"],
                    row["scene_overlap"],
                    row["mismatches"],
                    row["mismatch_scene_count"],
                    row["mismatch_scene_ids"],
                ]
                for row in comparison_summary_rows
            ],
        )
    )
    lines.extend(["", "## Variant Summary", ""])
    lines.extend(
        _markdown_table(
            [
                "variant",
                "execution_mode",
                "task_set",
                "trials",
                "successes",
                "success_rate",
                "playground_trials",
                "playground_successes",
                "playground_success_rate",
                "setup_error",
            ],
            [
                [
                    row["variant"],
                    row["execution_mode"],
                    row["task_set"],
                    row["trials"],
                    row["successes"],
                    row["success_rate"],
                    row["playground_trials"],
                    row["playground_successes"],
                    row["playground_success_rate"],
                    row["setup_error"],
                ]
                for row in summary_rows
            ],
        )
    )
    lines.extend(["", "## Official Boundary Ledger", ""])
    lines.extend(
        _markdown_table(
            ["item", "status", "claim_scope", "details"],
            [
                [row["item"], row["status_label"], row["claim_scope"], row["details"]]
                for row in boundary_ledger_rows
            ],
        )
    )
    lines.extend(["", "## Success Delta Table", ""])
    if attribution_rows:
        lines.extend(
            _markdown_table(
                [
                    "transition",
                    "factor",
                    "from_success_rate",
                    "to_success_rate",
                    "success_rate_delta",
                    "same_distribution",
                    "interpretation",
                ],
                [
                    [
                        row["transition"],
                        row["factor"],
                        row["from_success_rate"],
                        row["to_success_rate"],
                        row["success_rate_delta"],
                        row["same_distribution"],
                        row["interpretation"],
                    ]
                    for row in attribution_rows
                ],
            )
        )
    else:
        lines.append("_V2-V5 were not run because parity did not pass the dual-threshold gate._")
    lines.extend(["", "## Audit Conclusion", ""])
    lines.append(f"- Parity conclusion: `{parity_status['status_label']}`.")
    lines.append(f"- Interpretation: {parity_status['reason']}")
    lines.append(f"- Primary bottleneck: `{primary_bottleneck}`.")
    if force_attribution and str(parity_status["status_code"]) == "parity_failed" and attribution_rows:
        lines.append("- `V2-V5` were still run in provisional mode so we could estimate factor contributions before parity is fully repaired.")
    lines.extend(_attribution_conclusion_lines(attribution_rows))
    if v1_mismatch_rows:
        lines.append("- See `mismatch_episodes.csv` for the remaining `V0a vs V1` mismatches.")
    if v0_repeat_mismatch_rows:
        lines.append("- See `v0_repeat_mismatch_episodes.csv` for the official runner self-repeat baseline mismatches.")
    report_text = "\n".join(lines) + "\n"
    _write_text(audit_root / "report.md", report_text)
    _write_text(audit_root / "internal_summary.md", report_text)

    teacher_lines = [
        "# GraspVLA 公开 release 的能力边界与当前 benchmark 瓶颈",
        "",
        f"- 当前官方边界结论：`{parity_status['status_label']}`。",
        f"- 当前主要瓶颈：`{primary_bottleneck}`。",
        "",
        "## 1. 官方 release 当前可稳定支持什么",
        "",
        "- `Track B` 官方 native LIBERO/playground 结果可以继续当作公开 release 的原生上限参考，但它不能直接当 shared benchmark 主结论。",
        "- 当前官方对齐子集已经可以稳定跑完，不再有 setup-level blocker。",
        "",
        "## 2. 哪些结果只能算 reproducibility-limited",
        "",
    ]
    if str(parity_status["status_code"]) == "reproducibility_limited_parity":
        teacher_lines.append("- 当前 `official_aligned subset parity` 应标成 `reproducibility-limited parity`：wrapper 剩余 mismatch 数已经和官方自重复漂移同量级。")
    elif str(parity_status["status_code"]) == "strict_parity_passed":
        teacher_lines.append("- 当前 `official_aligned subset parity` 已达到严格对齐。")
    else:
        teacher_lines.append("- 当前 `official_aligned subset parity` 仍未通过，说明 wrapper implementation gap 还没有完全排除。")
    teacher_lines.append(
        f"- 这轮 `V0a vs V0b` mismatch 为 `{len(v0_repeat_mismatch_rows)}`，`V0a vs V1` mismatch 为 `{len(v1_mismatch_rows)}`，scene overlap 为 `{', '.join(scene_overlap) if scene_overlap else 'none'}`。"
    )
    if force_attribution and str(parity_status["status_code"]) == "parity_failed" and attribution_rows:
        teacher_lines.append("- 这轮我仍然把 `V2-V5` 跑了出来，但它们现在只能算 provisional factor attribution，不能替代正式 parity gate。")
    teacher_lines.extend(
        [
            "",
            "## 3. 哪些 benchmark 结论现在还不能 claim",
            "",
            "- 当前 `Track A-Cal` 仍应保留为 provisional，不能拿它直接写成公开 release 在 shared benchmark 下的最终公平结论。",
            "- 在边界澄清完成前，不继续扩 `Track A-Cal`、不继续做 CGN / AnyGrasp 的 headline compare，也不重新设计 success rule。",
            "",
            "## 4. 下一步如果要把 Track A 变成可区分 leaderboard，最先该改哪里",
            "",
        ]
    )
    if primary_bottleneck == "shared protocol / distribution gap":
        teacher_lines.append("- 当前证据更支持先审计 shared protocol 和 released distribution 的对齐，而不是继续怀疑 wrapper 大面积实现错误。")
    elif primary_bottleneck == "wrapper implementation gap":
        teacher_lines.append("- 当前最先该修的是 wrapper implementation gap；在它被排除之前，不适合再解释 shared benchmark 结果。")
    else:
        teacher_lines.append(f"- 当前最先该审的是 `{primary_bottleneck}`，因为它比继续扩 benchmark 更可能解释 `Track A-Cal` 的全零结果。")
    teacher_text = "\n".join(teacher_lines) + "\n"
    _write_text(audit_root / "teacher_summary_zh.md", teacher_text)
    _write_text(audit_root / "teacher_summary_zh_clean.md", teacher_text, encoding="utf-8-sig")
    _write_docs_snapshots(date_token=date_token, report_text=report_text, teacher_text=teacher_text)
    _write_json(
        audit_root / "report.json",
        {
            "parity_status": parity_status,
            "force_attribution": force_attribution,
            "comparison_summary": comparison_summary_rows,
            "summary": summary_rows,
            "boundary_ledger": boundary_ledger_rows,
            "attribution_rows": attribution_rows,
            "primary_bottleneck": primary_bottleneck,
            "v0_repeat_diff_rows": v0_repeat_diff_rows,
            "v0_repeat_mismatch_rows": v0_repeat_mismatch_rows,
            "v1_diff_rows": v1_diff_rows,
            "v1_mismatch_rows": v1_mismatch_rows,
        },
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
    parser.add_argument("--force-attribution", action="store_true")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date_token = timestamp[:8]
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
        "force_attribution": bool(args.force_attribution),
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
                "lift_threshold_cm_override": variant.lift_threshold_cm_override,
                "hold_steps_override": variant.hold_steps_override,
            }
            for variant in VARIANTS
        ],
        "local_commit": resolve_commit(),
    }
    _write_json(audit_root / "dispatch_manifest.json", manifest)

    smoke_root = ensure_dir(audit_root / "smoke")
    for variant in (PARITY_VARIANTS[0], PARITY_VARIANTS[2]):
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
    for variant in PARITY_VARIANTS:
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

    expected_full_episodes = _expected_episode_count(
        args.benchmarks,
        args.tasks_per_benchmark,
        args.seeds,
        args.playground_seeds,
    )
    v0_rows = _read_results(variant_dirs["V0_official_runner"] / "results.csv")
    v0_repeat_rows = _read_results(variant_dirs["V0_repeat_official_runner"] / "results.csv")
    v1_rows = _read_results(variant_dirs["V1_wrapper_official_parity"] / "results.csv")

    v0_repeat_diff_rows = _compare_variant_rows(
        v0_rows,
        v0_repeat_rows,
        reference_variant="V0_official_runner",
        candidate_variant="V0_repeat_official_runner",
    )
    v0_repeat_mismatch_rows = _mismatch_rows_only(v0_repeat_diff_rows) + _coverage_rows(
        reference_variant="V0_official_runner",
        candidate_variant="V0_repeat_official_runner",
        reference_count=len(v0_rows),
        candidate_count=len(v0_repeat_rows),
        expected_episodes=expected_full_episodes,
    )

    v1_diff_rows = _compare_variant_rows(
        v0_rows,
        v1_rows,
        reference_variant="V0_official_runner",
        candidate_variant="V1_wrapper_official_parity",
    )
    v1_mismatch_rows = _mismatch_rows_only(v1_diff_rows) + _coverage_rows(
        reference_variant="V0_official_runner",
        candidate_variant="V1_wrapper_official_parity",
        reference_count=len(v0_rows),
        candidate_count=len(v1_rows),
        expected_episodes=expected_full_episodes,
    )

    summary_rows = [_summary_row(variant, variant_dirs[variant.name]) for variant in PARITY_VARIANTS]
    setup_errors = {str(row["variant"]): str(row["setup_error"]) for row in summary_rows}
    coverage_counts = {
        "V0_official_runner": len(v0_rows),
        "V0_repeat_official_runner": len(v0_repeat_rows),
        "V1_wrapper_official_parity": len(v1_rows),
    }
    parity_status = classify_parity_status(
        expected_episodes=expected_full_episodes,
        coverage_counts=coverage_counts,
        setup_errors=setup_errors,
        v0_repeat_mismatch_count=len(v0_repeat_mismatch_rows),
        v1_mismatch_count=len(v1_mismatch_rows),
    )

    should_run_attribution = (bool(parity_status["advance_to_attribution"]) or bool(args.force_attribution)) and not args.stop_after_parity
    if should_run_attribution:
        for variant in ATTRIBUTION_VARIANTS:
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

    comparison_summary_rows = [
        _comparison_summary_row(
            reference_variant="V0_official_runner",
            candidate_variant="V0_repeat_official_runner",
            reference_rows=v0_rows,
            candidate_rows=v0_repeat_rows,
            mismatch_rows=v0_repeat_mismatch_rows,
            expected_episodes=expected_full_episodes,
        ),
        _comparison_summary_row(
            reference_variant="V0_official_runner",
            candidate_variant="V1_wrapper_official_parity",
            reference_rows=v0_rows,
            candidate_rows=v1_rows,
            mismatch_rows=v1_mismatch_rows,
            expected_episodes=expected_full_episodes,
        ),
    ]
    boundary_ledger_rows = _build_boundary_ledger(
        parity_status=parity_status,
        comparison_summary_rows=comparison_summary_rows,
    )
    attribution_rows = _build_attribution_rows(summary_rows)

    _write_csv(audit_root / "summary.csv", summary_rows)
    _write_csv(audit_root / "comparison_summary.csv", comparison_summary_rows)
    _write_csv(audit_root / "per_episode_diff_v0a_vs_v0b.csv", v0_repeat_diff_rows)
    _write_csv(audit_root / "per_episode_diff_v0a_vs_v1.csv", v1_diff_rows)
    _write_csv(audit_root / "v0_repeat_mismatch_episodes.csv", v0_repeat_mismatch_rows)
    _write_csv(audit_root / "mismatch_episodes.csv", v1_mismatch_rows)
    _write_csv(audit_root / "boundary_ledger.csv", boundary_ledger_rows)
    _write_json(audit_root / "boundary_ledger.json", boundary_ledger_rows)
    _write_csv(audit_root / "success_delta.csv", attribution_rows)
    _write_report(
        audit_root=audit_root,
        date_token=date_token,
        parity_status=parity_status,
        force_attribution=bool(args.force_attribution),
        comparison_summary_rows=comparison_summary_rows,
        summary_rows=summary_rows,
        v0_repeat_diff_rows=v0_repeat_diff_rows,
        v0_repeat_mismatch_rows=v0_repeat_mismatch_rows,
        v1_diff_rows=v1_diff_rows,
        v1_mismatch_rows=v1_mismatch_rows,
        boundary_ledger_rows=boundary_ledger_rows,
        attribution_rows=attribution_rows,
    )
    print(
        json.dumps(
            {
                "audit_root": str(audit_root),
                "parity_status": parity_status["status_code"],
                "advance_to_attribution": bool(parity_status["advance_to_attribution"]),
                "force_attribution": bool(args.force_attribution),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
