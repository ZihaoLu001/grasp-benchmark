from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.config import load_cluster_config, load_named_config, resolve_cluster_config_name
from grasp_benchmark.paths import ARTIFACTS_DIR, PROJECT_ROOT, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.shell import run_command


@dataclass(frozen=True, slots=True)
class BottleneckVariant:
    name: str
    execution_mode: str
    segmentation_mode: str = ""
    oracle_grasp_mode: str = ""


VARIANTS = (
    BottleneckVariant(
        name="D0_shared_cgn",
        execution_mode="track_a_diag_cgn_bottleneck_d0",
    ),
    BottleneckVariant(
        name="D1_oracle_grounding",
        execution_mode="track_a_diag_cgn_bottleneck_d1",
        segmentation_mode="oracle_gt",
    ),
    BottleneckVariant(
        name="D2_oracle_grasp",
        execution_mode="track_a_diag_cgn_bottleneck_d2",
        segmentation_mode="oracle_gt",
        oracle_grasp_mode="topdown_centroid",
    ),
)


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


def _build_remote_command(
    *,
    cluster_config: dict,
    method_config: dict,
    sensor_config_name: str,
    variant: BottleneckVariant,
    task_set: str,
    parent_run_id: str,
    remote_output_dir: str,
    scene_ids: str,
    cluster_config_name: str = "default",
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["env_name"]}'
    remote_root = cluster_config["remote_root"]
    scene_ids_flag = f' --scene-ids "{scene_ids}"' if scene_ids.strip() else ""
    segmentation_flag = f' --segmentation-mode "{variant.segmentation_mode}"' if variant.segmentation_mode else ""
    oracle_grasp_flag = f' --oracle-grasp-mode "{variant.oracle_grasp_mode}"' if variant.oracle_grasp_mode else ""
    return (
        f'mkdir -p "{remote_output_dir}" && '
        f'source "{miniforge_root}/etc/profile.d/conda.sh" && '
        f'conda activate "{env_prefix}" && '
        f'cd "{remote_root}" && '
        f'export GRASP_BENCHMARK_CLUSTER_CONFIG="{cluster_config_name}" && '
        f'export PYTHONPATH="{remote_root}/src${{PYTHONPATH:+:${{PYTHONPATH}}}}" && '
        f'python -m grasp_benchmark.run.worker '
        f'--cluster-config "{cluster_config_name}" '
        f'--method "cgn" '
        f'--task-set "{task_set}" '
        f'--sensor-config "{sensor_config_name}" '
        f'--output-dir "{remote_output_dir}" '
        f'--execution-mode "{variant.execution_mode}" '
        f'--parent-run-id "{parent_run_id}" '
        f'--trace-steps'
        f'{segmentation_flag}'
        f'{oracle_grasp_flag}'
        f'{scene_ids_flag}'
    ).strip()


def _fetch_remote_results(node: str, remote_run_dir: str, local_run_dir: Path) -> None:
    ensure_dir(local_run_dir)
    result = run_command(["scp", "-r", f"{node}:{remote_run_dir}/.", str(local_run_dir)], timeout=14400)
    (local_run_dir / "fetch_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (local_run_dir / "fetch_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "Failed to fetch remote CGN bottleneck outputs.")


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


def _variant_summary(variant: BottleneckVariant, rows: list[dict[str, str]]) -> dict[str, object]:
    successes = sum(int(row["success"]) for row in rows)
    trials = len(rows)
    return {
        "variant": variant.name,
        "execution_mode": variant.execution_mode,
        "segmentation_mode": variant.segmentation_mode or "shared_detector_segmentation",
        "oracle_grasp_mode": variant.oracle_grasp_mode or "none",
        "trials": trials,
        "successes": successes,
        "success_rate": round(successes / trials, 4) if trials else 0.0,
        "mean_attempts": round(sum(float(row["attempts"]) for row in rows) / trials, 4) if trials else 0.0,
        "mean_inference_ms": round(sum(float(row["inference_ms"]) for row in rows) / trials, 4) if trials else 0.0,
        "mean_cycle_time_s": round(sum(float(row["cycle_time_s"]) for row in rows) / trials, 4) if trials else 0.0,
    }


def _load_attempt_payloads(episodes_dir: Path) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for path in sorted(episodes_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        scene_id = str(payload.get("scene_id", "")).strip()
        if not scene_id:
            continue
        grouped[scene_id].append(payload)
    for scene_id in grouped:
        grouped[scene_id].sort(key=lambda item: int(item.get("attempt", 0)))
    return grouped


def _rescore_relaxed_success(
    d0_rows: list[dict[str, str]],
    attempt_payloads: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    rescored: list[dict[str, object]] = []
    for row in d0_rows:
        scene_id = str(row["scene_id"])
        attempts = attempt_payloads.get(scene_id, [])
        success_attempt = next(
            (
                attempt
                for attempt in attempts
                if float(attempt.get("lift_cm", 0.0)) >= 10.0
            ),
            None,
        )
        max_lift_cm = max((float(attempt.get("lift_cm", 0.0)) for attempt in attempts), default=float(row.get("lift_cm", 0.0) or 0.0))
        rescored.append(
            {
                "variant": "D3_relaxed_success_rescore",
                "task": row["task"],
                "scene_id": row["scene_id"],
                "scene_recipe_id": row.get("scene_recipe_id", row["scene_id"]),
                "condition": row["condition"],
                "object_group": row["object_group"],
                "success": 1 if success_attempt is not None else 0,
                "attempts": int(success_attempt.get("attempt", row["attempts"])) if success_attempt is not None else int(row["attempts"]),
                "lift_cm": round(max_lift_cm, 4),
                "hold_s": 0.0,
                "spl": round(1.0 / int(success_attempt.get("attempt", row["attempts"])), 4) if success_attempt is not None else 0.0,
                "inference_ms": float(row.get("inference_ms", 0.0) or 0.0),
                "cycle_time_s": float(row.get("cycle_time_s", 0.0) or 0.0),
                "failure_stage": "" if success_attempt is not None else "task_failure",
                "failure_reason": "" if success_attempt is not None else "relaxed_lift_10cm_not_met",
            }
        )
    return rescored


def _failure_taxonomy_by_variant(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counter = Counter()
    for row in rows:
        if int(row.get("success", 0)):
            continue
        counter[
            (
                str(row.get("variant", "")),
                str(row.get("failure_stage", "")),
                str(row.get("failure_reason", "")),
            )
        ] += 1
    output: list[dict[str, object]] = []
    for (variant, failure_stage, failure_reason), count in sorted(counter.items()):
        output.append(
            {
                "variant": variant,
                "failure_stage": failure_stage,
                "failure_reason": failure_reason,
                "count": count,
            }
        )
    return output


def _delta_table(summary_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    lookup = {str(row["variant"]): row for row in summary_rows}
    transitions = (
        ("D0_shared_cgn", "D1_oracle_grounding", "grounding_segmentation_effect"),
        ("D1_oracle_grounding", "D2_oracle_grasp", "grasp_proposal_effect"),
        ("D0_shared_cgn", "D3_relaxed_success_rescore", "strict_success_semantics_effect"),
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
    summary_rows: list[dict[str, object]],
    by_task_rows: list[dict[str, object]],
    taxonomy_rows: list[dict[str, object]],
    delta_rows: list[dict[str, object]],
) -> tuple[str, str]:
    lookup = {str(row["variant"]): row for row in summary_rows}
    d0 = lookup["D0_shared_cgn"]
    d1 = lookup["D1_oracle_grounding"]
    d2 = lookup["D2_oracle_grasp"]
    d3 = lookup["D3_relaxed_success_rescore"]
    d1_delta = next(row for row in delta_rows if row["factor"] == "grounding_segmentation_effect")
    d2_delta = next(row for row in delta_rows if row["factor"] == "grasp_proposal_effect")
    d3_delta = next(row for row in delta_rows if row["factor"] == "strict_success_semantics_effect")

    report_lines = [
        "# CGN Bottleneck v1",
        "",
        "## Headline",
        "",
        f"- `D0 shared CGN` reaches `{d0['successes']}/{d0['trials']}` on the fixed 24-episode bottleneck suite.",
        f"- Replacing detector + mask filtering with simulator GT masks changes success rate by `{d1_delta['success_rate_delta']:+.4f}`.",
        f"- Replacing the CGN grasp proposal with an oracle top-down centroid grasp changes success rate by `{d2_delta['success_rate_delta']:+.4f}` beyond `D1`.",
        f"- Relaxing the success rule on the original `D0` logs changes success rate by `{d3_delta['success_rate_delta']:+.4f}`.",
        f"- After removing both perception and proposal errors, `D2` still reaches only `{d2['successes']}/{d2['trials']}`, which quantifies the residual planner/execution gap under the shared controller.",
        "",
        "## Variant Summary",
        "",
        "| variant | segmentation_mode | oracle_grasp_mode | trials | successes | success_rate | mean_attempts | mean_inference_ms | mean_cycle_time_s |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary_rows:
        report_lines.append(
            f"| {row['variant']} | {row['segmentation_mode']} | {row['oracle_grasp_mode']} | {row['trials']} | {row['successes']} | {row['success_rate']} | {row['mean_attempts']} | {row['mean_inference_ms']} | {row['mean_cycle_time_s']} |"
        )
    report_lines.extend(
        [
            "",
            "## Delta Table",
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
            "## By Task",
            "",
            "| variant | task | trials | successes | success_rate | mean_attempts |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in by_task_rows:
        report_lines.append(
            f"| {row['variant']} | {row['task']} | {row['trials']} | {row['successes']} | {row['success_rate']} | {row['mean_attempts']} |"
        )
    report_lines.extend(["", "## Failure Taxonomy", ""])
    if taxonomy_rows:
        report_lines.extend(
            [
                "| variant | failure_stage | failure_reason | count |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in taxonomy_rows:
            report_lines.append(
                f"| {row['variant']} | {row['failure_stage']} | {row['failure_reason']} | {row['count']} |"
            )
    else:
        report_lines.append("_No failures recorded._")
    report_lines.extend(["", f"_Generated under `{root_dir.name}`._"])

    teacher_lines = [
        "# CGN Bottleneck v1 Summary",
        "",
        f"- The shared CGN baseline `D0` scored `{d0['successes']}/{d0['trials']}`.",
        f"- `D0 -> D1` quantifies detector / segmentation error; the success-rate delta is `{d1_delta['success_rate_delta']:+.4f}`.",
        f"- `D1 -> D2` quantifies grasp proposal error; the success-rate delta is `{d2_delta['success_rate_delta']:+.4f}`.",
        f"- `D0 -> D3` quantifies strict success semantics; the success-rate delta is `{d3_delta['success_rate_delta']:+.4f}`.",
        f"- Even with oracle perception and grasp proposal, `D2` reaches only `{d2['successes']}/{d2['trials']}`, leaving planner / execution / shared-control mismatch as the remaining bottleneck.",
        "",
        "## Paper Claim",
        "",
        "- This audit is not intended to tune CGN upward; it decomposes the shared-lane low score into interpretable stage bottlenecks.",
        "- In the paper, it belongs in the modular bottleneck section and supports the claim that the CGN shared-lane gap reflects both method differences and measurable pipeline bottlenecks.",
    ]
    return "\n".join(report_lines) + "\n", "\n".join(teacher_lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CGN bottleneck audit on a fixed diagnostic suite.")
    parser.add_argument("--node", default="em14")
    parser.add_argument("--sensor-config", default="track_a_dual_realsense")
    parser.add_argument("--scene-ids", default="", help="Optional comma-separated scene ids for smoke runs.")
    parser.add_argument("--task-set", default="cgn_bottleneck_v1")
    parser.add_argument("--dry-run", action="store_true", help="Write remote commands without executing them.")
    parser.add_argument(
        "--cluster-config",
        default="",
        help="Cluster config name under configs/cluster. Defaults to GRASP_BENCHMARK_CLUSTER_CONFIG or default.",
    )
    args = parser.parse_args()

    cluster_config_name = resolve_cluster_config_name(args.cluster_config)
    cluster_config = load_cluster_config(cluster_config_name)
    method_config = load_named_config("methods", "cgn")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date_token = timestamp[:8]
    parent_run_id = f"{timestamp}_{args.task_set}"
    local_root = ensure_dir(ARTIFACTS_DIR / "audits" / parent_run_id)
    remote_root = f'{cluster_config["remote_root"]}/artifacts/audits/{parent_run_id}'

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node": args.node,
        "sensor_config": args.sensor_config,
        "task_set": args.task_set,
        "cluster_config": cluster_config_name,
        "parent_run_id": parent_run_id,
        "scene_ids_filter": args.scene_ids,
        "dry_run": args.dry_run,
        "variants": [
            {
                "name": variant.name,
                "execution_mode": variant.execution_mode,
                "segmentation_mode": variant.segmentation_mode,
                "oracle_grasp_mode": variant.oracle_grasp_mode,
            }
            for variant in VARIANTS
        ],
        "local_commit": resolve_commit(),
    }
    (local_root / "dispatch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    variant_rows: dict[str, list[dict[str, str]]] = {}
    summary_rows: list[dict[str, object]] = []
    by_task_rows: list[dict[str, object]] = []
    variant_commands: list[dict[str, str]] = []

    for variant in VARIANTS:
        local_variant_dir = ensure_dir(local_root / variant.name)
        remote_variant_dir = f"{remote_root}/{variant.name}"
        remote_command = _build_remote_command(
            cluster_config=cluster_config,
            method_config=method_config,
            sensor_config_name=args.sensor_config,
            variant=variant,
            task_set=args.task_set,
            parent_run_id=parent_run_id,
            remote_output_dir=remote_variant_dir,
            scene_ids=args.scene_ids,
            cluster_config_name=cluster_config_name,
        )
        variant_commands.append(
            {
                "variant": variant.name,
                "remote_output_dir": remote_variant_dir,
                "remote_command": remote_command,
            }
        )
        (local_variant_dir / "remote_command.txt").write_text(remote_command + "\n", encoding="utf-8")
        if args.dry_run:
            continue
        result = run_command(["ssh", "-o", "BatchMode=yes", args.node, f"bash -lc '{remote_command}'"], timeout=28800)
        (local_variant_dir / "dispatch_stdout.txt").write_text(result.stdout, encoding="utf-8")
        (local_variant_dir / "dispatch_stderr.txt").write_text(result.stderr, encoding="utf-8")
        if not result.ok:
            raise SystemExit(result.stderr or result.stdout)
        _fetch_remote_results(args.node, remote_variant_dir, local_variant_dir)

        rows = _read_results(local_variant_dir / "results.csv")
        variant_rows[variant.name] = rows
        summary_rows.append(_variant_summary(variant, rows))
        for row in _aggregate(rows, ["task"]):
            row["variant"] = variant.name
            by_task_rows.append(row)

    if args.dry_run:
        manifest["variant_commands"] = variant_commands
        (local_root / "dispatch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"dry_run": True, "manifest": str(local_root / "dispatch_manifest.json")}, indent=2))
        return

    d0_attempt_payloads = _load_attempt_payloads(local_root / "D0_shared_cgn" / "episodes")
    d3_rows = _rescore_relaxed_success(variant_rows["D0_shared_cgn"], d0_attempt_payloads)
    d3_summary = _aggregate(
        [
            {
                "variant": "D3_relaxed_success_rescore",
                "task": row["task"],
                "attempts": str(row["attempts"]),
                "success": str(row["success"]),
                "inference_ms": str(row["inference_ms"]),
                "cycle_time_s": str(row["cycle_time_s"]),
            }
            for row in d3_rows
        ],
        ["variant"],
    )[0]
    d3_summary.update(
        {
            "execution_mode": "offline_rescore",
            "segmentation_mode": "shared_detector_segmentation",
            "oracle_grasp_mode": "none",
        }
    )
    summary_rows.append(d3_summary)
    for row in _aggregate(
        [
            {
                "variant": "D3_relaxed_success_rescore",
                "task": item["task"],
                "attempts": str(item["attempts"]),
                "success": str(item["success"]),
                "inference_ms": str(item["inference_ms"]),
                "cycle_time_s": str(item["cycle_time_s"]),
            }
            for item in d3_rows
        ],
        ["variant", "task"],
    ):
        by_task_rows.append(row)

    delta_rows = _delta_table(summary_rows)
    taxonomy_rows = _failure_taxonomy_by_variant(
        [
            *[
                {
                    "variant": variant_name,
                    "success": int(row["success"]),
                    "failure_stage": row.get("failure_stage", ""),
                    "failure_reason": row.get("failure_reason", ""),
                }
                for variant_name, rows in variant_rows.items()
                for row in rows
            ],
            *d3_rows,
        ]
    )
    report_text, teacher_text = _render_report(
        root_dir=local_root,
        summary_rows=summary_rows,
        by_task_rows=by_task_rows,
        taxonomy_rows=taxonomy_rows,
        delta_rows=delta_rows,
    )
    _write_csv(local_root / "summary.csv", summary_rows)
    _write_csv(local_root / "task_summary.csv", by_task_rows)
    _write_csv(local_root / "failure_taxonomy.csv", taxonomy_rows)
    _write_csv(local_root / "success_delta.csv", delta_rows)
    _write_csv(local_root / "d3_relaxed_success_rows.csv", d3_rows)
    _write_text(local_root / "report.md", report_text)
    _write_text(local_root / "collaborator_summary.md", teacher_text)
    _write_json(
        local_root / "summary.json",
        {
            "summary": summary_rows,
            "task_summary": by_task_rows,
            "failure_taxonomy": taxonomy_rows,
            "success_delta": delta_rows,
            "scene_ids_filter": args.scene_ids,
        },
    )
    docs_dir = _docs_reports_dir()
    _write_text(docs_dir / f"{args.task_set}_{date_token}.md", report_text)
    _write_text(docs_dir / f"{args.task_set}_{date_token}_collaborator.md", teacher_text)
    print(json.dumps({"audit_root": str(local_root), "parent_run_id": parent_run_id}, indent=2))


if __name__ == "__main__":
    main()
