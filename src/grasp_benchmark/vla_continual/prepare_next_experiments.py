from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from grasp_benchmark.paths import ARTIFACTS_DIR, CONFIGS_DIR, PROJECT_ROOT, ensure_dir


DEFAULT_CONFIG = CONFIGS_DIR / "sca_vla" / "next_experiments.yaml"


def _write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


@dataclass(frozen=True)
class JobSpec:
    name: str
    suite: str
    kind: str
    sbatch_path: Path
    command: str


@dataclass(frozen=True)
class ScriptSpec:
    name: str
    kind: str
    path: Path
    command: str


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def _third_party_status(config: dict[str, Any]) -> dict[str, str]:
    tp = config["third_party"]["continual_vla_rl"]
    path = PROJECT_ROOT / tp["local_path"]
    status = {
        "repo": str(tp["repo"]),
        "path": str(path),
        "pinned_commit": str(tp.get("pinned_commit", "")),
        "present": str(path.exists()).lower(),
        "current_commit": "",
        "remote_url": "",
    }
    if path.exists():
        try:
            status["current_commit"] = _run_git(["rev-parse", "HEAD"], path)
            status["remote_url"] = _run_git(["remote", "get-url", "origin"], path)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return status


def _slurm_header(config: dict[str, Any], name: str) -> str:
    cluster = config["cluster"]
    return "\n".join(
        [
            "#!/bin/bash",
            f"#SBATCH --job-name={name}",
            f"#SBATCH --account={cluster['account']}",
            f"#SBATCH --partition={cluster['partition']}",
            f"#SBATCH --gres={cluster['gres']}",
            f"#SBATCH --cpus-per-task={cluster['cpus_per_task']}",
            f"#SBATCH --mem={cluster['mem']}",
            f"#SBATCH --time={cluster['time']}",
            "#SBATCH --output=%x-%j.out",
            "#SBATCH --error=%x-%j.err",
            "",
            "set -euo pipefail",
            "source /etc/profile.d/modules.sh >/dev/null 2>&1 || true",
            f"module load {cluster['slurm_module']} >/dev/null 2>&1 || true",
            "",
        ]
    )


def _seq_rl_command(config: dict[str, Any], suite: str) -> str:
    seq = config["reference_seq_rl"]
    suite_cfg = seq["suites"][suite]
    root = config["cluster"]["continual_vla_rl_root"]
    max_epoch = str(seq.get("max_epoch", ""))
    seed = str(seq["seed"])
    model_dir = f"{root}/{suite_cfg['local_model_dir']}"
    return "\n".join(
        [
            f'cd "{root}"',
            f'export REPO_PATH="{root}"',
            f'export EMBODIED_PATH="{root}/examples/embodiment"',
            "echo \"Seq-RL reference suite: " + suite + "\"",
            "echo \"Base checkpoint: " + str(suite_cfg["base_checkpoint"]) + "\"",
            f'if [ ! -d "{model_dir}" ]; then',
            f'  echo "Missing local Seq-RL model directory: {model_dir}" >&2',
            '  echo "Run commands/prepare_seq_rl_checkpoints.sh before submitting this job." >&2',
            "  exit 42",
            "fi",
            (
                "bash examples/crl_experiment/run_embodiment_sequential.sh "
                f'"{suite_cfg["task_range"]}" "" "{max_epoch}" "{suite_cfg["train_config"]}" "{seed}"'
            ),
        ]
    )


def _offline_collect_command(config: dict[str, Any], suite: str) -> str:
    offline = config["offline"]
    root = config["cluster"]["sca_vla_root"]
    python = config["cluster"]["sca_vla_python"]
    aliases = offline.get("baseline_method_aliases", {})
    methods = ",".join(aliases.get(method, method) for method in offline.get("baseline_methods", offline["methods"]))
    run_root = offline["fixed_pilot_run_root"]
    output = f"{run_root}/summary_{suite}.json"
    collector = f"{root}/{offline['collector']}"
    return "\n".join(
        [
            f'cd "{root}"',
            f'"{python}" "{collector}" '
            f'--run-root "{run_root}" '
            f'--suites "{suite}" '
            f'--methods "{methods}" '
            f'--output "{output}"',
        ]
    )


def _seq_rl_checkpoint_prepare_command(config: dict[str, Any]) -> str:
    root = config["cluster"]["continual_vla_rl_root"]
    suites = config["comparison_matrix"]["primary_suites"]
    model_specs = []
    for suite in suites:
        suite_cfg = config["reference_seq_rl"]["suites"][suite]
        model_specs.append(
            {
                "suite": suite,
                "repo_id": suite_cfg["base_checkpoint"],
                "local_dir": f"{root}/{suite_cfg['local_model_dir']}",
            }
        )
    return "\n".join(
        [
            "set -euo pipefail",
            f'cd "{root}"',
            "python - <<'PY'",
            "from huggingface_hub import snapshot_download",
            f"model_specs = {model_specs!r}",
            "for spec in model_specs:",
            "    print(f\"Preparing {spec['suite']}: {spec['repo_id']} -> {spec['local_dir']}\")",
            "    snapshot_download(",
            "        repo_id=spec['repo_id'],",
            "        local_dir=spec['local_dir'],",
            "        local_dir_use_symlinks=False,",
            "        resume_download=True,",
            "    )",
            "PY",
        ]
    )


def _policy_anchor_launch_command(config: dict[str, Any], *, smoke: bool, submit: bool) -> str:
    cluster = config["cluster"]
    offline = config["offline"]
    pa = offline["policy_anchor"]
    run_root = offline["policy_anchor_smoke_root"] if smoke else offline["policy_anchor_run_root"]
    task_order = pa["smoke_task_order"] if smoke else pa["full_task_order"]
    suites = pa["smoke_suite"] if smoke else pa["full_suites"]
    stages_arg = " --max-stages 3" if smoke else ""
    submit_arg = " --submit" if submit else ""
    job_root = offline["policy_anchor_job_root"]
    method = pa["submitted_method"]
    lambda_value = pa["anchor_lambda_balanced"]
    suite_base_checkpoints = ",".join(
        f"{suite}={checkpoint}" for suite, checkpoint in sorted(pa.get("base_checkpoints", {}).items())
    )
    suite_base_arg = (
        [f"  --suite-base-checkpoints {suite_base_checkpoints} \\"]
        if suite_base_checkpoints
        else []
    )
    lines = [
        "set -euo pipefail",
        f'cd "{cluster["sca_vla_root"]}"',
        f'"{cluster["sca_vla_python"]}" scripts/launch_lakeshore_oft_continual.py \\',
        f"  --suites {suites} \\",
        f"  --methods {method} \\",
        f"  --task-order {task_order} \\",
        f"  --run-root {run_root} \\",
        f"  --job-dir {job_root}/{'smoke' if smoke else 'full'} \\",
        f"  --slurm-log-dir {offline['policy_anchor_slurm_log_dir']} \\",
        *suite_base_arg,
        f"  --steps-per-task {pa['steps_per_task']} \\",
        f"  --num-trials-per-task {pa['num_trials_per_task']} \\",
        f"  --teacher-distill-lambda {lambda_value} \\",
        f"  --teacher-distill-current-weight {pa['current_loss_weight']} \\",
        f"  --teacher-distill-old-weight {pa['old_loss_weight']} \\",
        "  --teacher-distill-balance-groups \\",
        "  --job-prefix policy-anchor \\",
        f"  --global-dependency-chain{stages_arg}{submit_arg}",
    ]
    return "\n".join(
        lines
    )


def _behavior_field_anchor_launch_command(config: dict[str, Any], *, smoke: bool, submit: bool) -> str:
    cluster = config["cluster"]
    offline = config["offline"]
    bfa = offline["behavior_field_anchor"]
    run_root = offline["behavior_field_smoke_root"] if smoke else offline["behavior_field_run_root"]
    task_order = bfa["smoke_task_order"] if smoke else bfa["full_task_order"]
    suites = bfa["smoke_suite"] if smoke else bfa["full_suites"]
    stages_arg = " --max-stages 3" if smoke else ""
    submit_arg = " --submit" if submit else ""
    suite_base_checkpoints = ",".join(
        f"{suite}={checkpoint}" for suite, checkpoint in sorted(bfa.get("base_checkpoints", {}).items())
    )
    suite_base_arg = (
        [f"  --suite-base-checkpoints {suite_base_checkpoints} \\"]
        if suite_base_checkpoints
        else []
    )
    lines = [
        "set -euo pipefail",
        f'cd "{cluster["sca_vla_root"]}"',
        f'"{cluster["sca_vla_python"]}" scripts/launch_lakeshore_oft_continual.py \\',
        f"  --suites {suites} \\",
        f"  --methods {bfa['submitted_method']} \\",
        f"  --task-order {task_order} \\",
        f"  --run-root {run_root} \\",
        f"  --job-dir {offline['behavior_field_job_root']}/{'smoke' if smoke else 'full'} \\",
        f"  --slurm-log-dir {offline['policy_anchor_slurm_log_dir']} \\",
        *suite_base_arg,
        f"  --steps-per-task {bfa['steps_per_task']} \\",
        f"  --num-trials-per-task {bfa['num_trials_per_task']} \\",
        f"  --teacher-distill-lambda {bfa['anchor_lambda']} \\",
        f"  --teacher-distill-current-weight {bfa['current_loss_weight']} \\",
        f"  --teacher-distill-old-weight {bfa['old_loss_weight']} \\",
        "  --teacher-distill-balance-groups \\",
        f"  --bfa-lambda-field {bfa['field_lambda']} \\",
        f"  --bfa-image-noise-std {bfa['image_noise_std']} \\",
        f"  --bfa-proprio-noise-std {bfa['proprio_noise_std']} \\",
        "  --job-prefix bfa-anchor \\",
        f"  --global-dependency-chain{stages_arg}{submit_arg}",
    ]
    return "\n".join(lines)


def _write_job(
    *,
    config: dict[str, Any],
    jobs_dir: Path,
    suite: str,
    kind: str,
    command: str,
) -> JobSpec:
    name = f"sca-vla-{kind}-{suite.replace('_', '-')}"
    path = jobs_dir / f"{name}.sbatch"
    body = _slurm_header(config, name) + command + "\n"
    _write_text_lf(path, body)
    return JobSpec(name=name, suite=suite, kind=kind, sbatch_path=path, command=command)


def _write_shell_script(*, scripts_dir: Path, name: str, kind: str, command: str) -> ScriptSpec:
    path = scripts_dir / name
    body = "#!/usr/bin/env bash\n" + command.rstrip() + "\n"
    _write_text_lf(path, body)
    return ScriptSpec(name=name, kind=kind, path=path, command=command)


def generate_jobs(
    config_path: Path = DEFAULT_CONFIG,
    output_dir: Path | None = None,
    suites: list[str] | None = None,
    include_seq_rl: bool = True,
    include_offline_collect: bool = True,
    include_policy_anchor: bool = True,
    include_checkpoint_prep: bool = True,
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_dir or (ARTIFACTS_DIR / "sca_vla_next" / timestamp)
    jobs_dir = ensure_dir(output_dir / "jobs")
    scripts_dir = ensure_dir(output_dir / "commands")

    selected_suites = suites or list(config["comparison_matrix"]["primary_suites"])
    jobs: list[JobSpec] = []
    scripts: list[ScriptSpec] = []

    if include_checkpoint_prep:
        scripts.append(
            _write_shell_script(
                scripts_dir=scripts_dir,
                name="prepare_seq_rl_checkpoints.sh",
                kind="seq-rl-checkpoint-prep",
                command=_seq_rl_checkpoint_prepare_command(config),
            )
        )
    if include_policy_anchor:
        scripts.append(
            _write_shell_script(
                scripts_dir=scripts_dir,
                name="dry_run_policy_anchor_smoke.sh",
                kind="policy-anchor-smoke-dry-run",
                command=_policy_anchor_launch_command(config, smoke=True, submit=False),
            )
        )
        scripts.append(
            _write_shell_script(
                scripts_dir=scripts_dir,
                name="submit_policy_anchor_smoke.sh",
                kind="policy-anchor-smoke-submit",
                command=_policy_anchor_launch_command(config, smoke=True, submit=True),
            )
        )
        scripts.append(
            _write_shell_script(
                scripts_dir=scripts_dir,
                name="submit_policy_anchor_full.sh",
                kind="policy-anchor-full-submit",
                command=_policy_anchor_launch_command(config, smoke=False, submit=True),
            )
        )
        scripts.append(
            _write_shell_script(
                scripts_dir=scripts_dir,
                name="dry_run_behavior_field_anchor_smoke.sh",
                kind="behavior-field-anchor-smoke-dry-run",
                command=_behavior_field_anchor_launch_command(config, smoke=True, submit=False),
            )
        )
        scripts.append(
            _write_shell_script(
                scripts_dir=scripts_dir,
                name="submit_behavior_field_anchor_smoke.sh",
                kind="behavior-field-anchor-smoke-submit",
                command=_behavior_field_anchor_launch_command(config, smoke=True, submit=True),
            )
        )
        scripts.append(
            _write_shell_script(
                scripts_dir=scripts_dir,
                name="submit_behavior_field_anchor_full.sh",
                kind="behavior-field-anchor-full-submit",
                command=_behavior_field_anchor_launch_command(config, smoke=False, submit=True),
            )
        )

    for suite in selected_suites:
        if include_seq_rl:
            if suite not in config["reference_seq_rl"]["suites"]:
                raise ValueError(f"No Seq-RL reference config for suite: {suite}")
            jobs.append(
                _write_job(
                    config=config,
                    jobs_dir=jobs_dir,
                    suite=suite,
                    kind="seq-rl-ref",
                    command=_seq_rl_command(config, suite),
                )
            )
        if include_offline_collect:
            jobs.append(
                _write_job(
                    config=config,
                    jobs_dir=jobs_dir,
                    suite=suite,
                    kind="offline-collect",
                    command=_offline_collect_command(config, suite),
                )
            )

    manifest = {
        "created_utc": timestamp,
        "config_path": str(config_path),
        "output_dir": str(output_dir),
        "third_party": {"continual_vla_rl": _third_party_status(config)},
        "selected_suites": selected_suites,
        "scripts": [
            {
                "name": script.name,
                "kind": script.kind,
                "path": str(script.path),
                "command": script.command,
            }
            for script in scripts
        ],
        "jobs": [
            {
                "name": job.name,
                "suite": job.suite,
                "kind": job.kind,
                "sbatch_path": str(job.sbatch_path),
                "command": job.command,
            }
            for job in jobs
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SCA-VLA continual-learning comparison jobs.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--suites", default="", help="Comma-separated suite list. Defaults to primary_suites.")
    parser.add_argument("--no-seq-rl", action="store_true", help="Do not generate official Seq-RL reference jobs.")
    parser.add_argument("--no-offline-collect", action="store_true", help="Do not generate offline collector jobs.")
    parser.add_argument("--no-policy-anchor", action="store_true", help="Do not generate policy-anchor launcher commands.")
    parser.add_argument("--no-checkpoint-prep", action="store_true", help="Do not generate Seq-RL checkpoint prep command.")
    args = parser.parse_args()

    manifest = generate_jobs(
        config_path=args.config,
        output_dir=args.output_dir,
        suites=_parse_csv(args.suites) if args.suites else None,
        include_seq_rl=not args.no_seq_rl,
        include_offline_collect=not args.no_offline_collect,
        include_policy_anchor=not args.no_policy_anchor,
        include_checkpoint_prep=not args.no_checkpoint_prep,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
