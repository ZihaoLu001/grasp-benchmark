# grasp-benchmark

`grasp-benchmark` is a release-centric simulation benchmark for comparing end-to-end and modular robot grasping systems under a shared, frozen protocol.

The repository is organized around one practical question:

> If two released grasping systems are placed in the same simulated scenes, with the same cameras, robot, gripper, controller, attempt budget, and lift-and-hold success rule, what happens?

## Start Here

For collaborators, read these first:

1. [Current Benchmark Report](docs/current_benchmark_report.md): the single consolidated project report.
2. This README: how to interpret the repository, experiment names, and run commands.
3. `artifacts/`: generated results and run logs. This directory is intentionally not the source of truth for GitHub documentation.

The older `grasp_benchmark.pdf` draft from May 5, 2026 is pre-H100-rerun for CGN and should not be shared without revising the CGN tables and wording.

## Current Status

As of May 7, 2026:

- GraspVLA shared-protocol results are stable for the current simulator suites.
- CGN means the benchmark-owned `CGN shared lane`, not an official Contact-GraspNet native system.
- The old CGN all-zero result should be treated as pre-rerun shared-lane evidence, not as a claim that Contact-GraspNet itself has zero capability.
- CGN has been migrated on Lakeshore to `gb-cgn-tf212` with TensorFlow 2.12.0 / CUDA 11.8 / cuDNN 8.6 and H100-compatible custom ops.
- The raw Contact-GraspNet proposal generation works on H100: the saved probe returned 47 grasp proposals, so proposal generation itself is not the reason for the earlier all-zero shared-lane table.
- A shared planner timing bug was found and patched: CGN plans now hold the object after lift instead of ending the attempt immediately.
- The full patched CGN rerun on Lakeshore jobs `364545-364563` completed successfully with `ExitCode=0:0` for every job.

Current patched CGN H100 results:

| Suite | GraspVLA | CGN shared lane after post-lift-hold patch | Use |
| --- | ---: | ---: | --- |
| Main Shared Grasping Benchmark | `88 / 90` | `25 / 90` | headline fair-comparison suite |
| Hard Shared Grasping Stress Test | `160 / 168` | `20 / 168` | difficult-scene stress suite |
| Instruction Robustness Check | `38 / 40` | `8 / 40` | wording/paraphrase diagnostic |
| Task-Oriented Grasping Pilot | `23 / 24` | `0 / 24` | small task-oriented extension |

Tracked machine-readable evidence: [configs/results/cgn_h100_posthold_20260507.json](configs/results/cgn_h100_posthold_20260507.json). The canonical patched CGN suites recorded zero wrong-object successes; the separate `cgn_bottleneck_v2` diagnostic with one wrong-object flag is not part of the headline table.

The pre-patch CGN H100 table (`1 / 90`, `2 / 168`, `0 / 40`, `0 / 24`) is now only a diagnostic reference. The patched diagnostic `oracle_gt + real CGN` run on `cgn_bottleneck_v2` improved from `0 / 12` to `3 / 12`, confirming that the old CGN shared-lane score included a benchmark integration problem.

CGN Native-Reference Appendix status:

- Lakeshore jobs `364696-364699` and finalizer `364723` completed with `ExitCode=0:0`.
- Result: `39 / 138` (`28.26%`) on `track_b_cgn_native_v2`.
- This appendix used raw fused point clouds with `segment_ids`, Contact-GraspNet `pc_segments`, `local_regions=True`, and `filter_grasps=True`.
- All `939 / 939` saved debug traces confirm that official-filtering path and TensorFlow GPU visibility.
- Tracked evidence: [configs/results/cgn_native_reference_h100_20260507.json](configs/results/cgn_native_reference_h100_20260507.json).
- This remains native-reference engineering context only, not a fair-comparison headline result and not official Contact-GraspNet native-system performance.

## Experiment Name Guide

Internal `task_set` IDs are kept stable for scripts and reproducibility. Collaborator-facing names are what should appear in email, slides, and discussion.

| Collaborator-facing name | Internal ID | Status | Plain-English meaning |
| --- | --- | --- | --- |
| Main Shared Grasping Benchmark | `track_a_cal_v3` | current headline | 90 paired trials under the frozen shared protocol |
| Main Shared Grasping Benchmark, 60-trial draft | `track_a_cal_v2` | historical | earlier calibration subset, not the current headline table |
| Hard Shared Grasping Stress Test | `track_a_stress_v4` | current diagnostic | 168 difficult paired trials with clutter, occlusion, and transparent objects |
| Hard Shared Stress Test, early drafts | `track_a_stress_v2`, `track_a_stress_v3` | historical | older stress-suite drafts, retained for reproducibility |
| Instruction Robustness Check | `instruction_robustness_v2` | current diagnostic | same scenes with different instruction phrasings |
| Task-Oriented Grasping Pilot | `phase2_pilot_v1` | current diagnostic | small suite for handle/part-oriented grasping |
| Sim-to-Real Robustness Proxy | `sim2real_proxy_v2` | supporting diagnostic | simulated perturbations used as transfer stressors |
| CGN Pipeline Diagnostic | `cgn_bottleneck_v2` | debugging suite | isolates GroundingDINO, Contact-GraspNet, planner, and success-rule bottlenecks |
| CGN Native-Reference Appendix | `track_b_cgn_native_v2` | reference only | native-like engineering context, not a fair-comparison claim |

Use the friendly names first. Put internal IDs in parentheses only when readers need to reproduce the exact command.

## Which Task Set Should I Use?

| Goal | Use | Avoid |
| --- | --- | --- |
| Main collaborator comparison | Main Shared Grasping Benchmark (`track_a_cal_v3`) | older `track_a_cal_v1` / `track_a_cal_v2` drafts |
| Hard-case analysis | Hard Shared Grasping Stress Test (`track_a_stress_v4`) | older `track_a_stress_v2` / `track_a_stress_v3` drafts |
| CGN debugging | CGN Pipeline Diagnostic (`cgn_bottleneck_v2`) | treating bottleneck probes as headline benchmark results |
| Wording sensitivity | Instruction Robustness Check (`instruction_robustness_v2`) | mixing instruction robustness rows into the headline table |
| Task-oriented grasp examples | Task-Oriented Grasping Pilot (`phase2_pilot_v1`) | presenting this small pilot as the full benchmark |
| Native-like CGN context | CGN Native-Reference Appendix (`track_b_cgn_native_v2`) | using native-reference rows as fair-comparison claims |

## Method Lanes

| Method label | What it means in this repo | Claim boundary |
| --- | --- | --- |
| GraspVLA | Public GraspVLA release through the aligned shared simulator wrapper | headline Track A method |
| CGN shared lane | GroundingDINO target localization, depth masking, Contact-GraspNet proposals, and the shared planner/controller | benchmark-owned modular lane, not official native Contact-GraspNet |
| AnyGrasp | Excluded from current comparative claims | needs a fresh node-matched SDK license before revalidation |

## Architecture

```text
configs/
  cluster/      Lakeshore and other execution environments
  methods/      method definitions, runtime overrides, checkpoints
  results/      small tracked evidence summaries for collaborator-facing tables
  scenes/       simulator scene catalogs
  sensors/      shared camera/gripper/success-rule contracts
  tasks/        stable task-set IDs and collaborator-facing names

src/grasp_benchmark/
  adapters/     method adapters and modular perception/planning components
  runners/      simulator and legacy Contact-GraspNet runtime runners
  run/          local/cluster dispatch entrypoints
  report/       result aggregation and paper-bundle generation
  audit/        diagnostic experiments

docs/
  current_benchmark_report.md

artifacts/
  generated runs, logs, reports, videos, and Slurm manifests
```

CGN language-target tasks use:

```text
GroundingDINO -> depth mask -> Contact-GraspNet -> shared planner/controller -> 15 cm / 2 s success check
```

The shared protocol intentionally evaluates complete task execution, not only whether a grasp proposal exists.

## Quick Start

Install locally:

```powershell
python -m pip install -e .
```

Run tests:

```powershell
$env:PYTHONPATH = (Resolve-Path "src").Path
python -m pytest tests -q
```

Run Lakeshore preflight:

```powershell
python -m grasp_benchmark.preflight --cluster-config lakeshore --pool lakeshore --output artifacts/preflight/lakeshore_available_nodes.json
```

Prepare or revalidate the H100-compatible Contact-GraspNet runtime:

```powershell
python -m grasp_benchmark.prepare_cgn --node lakeshore --cluster-config lakeshore --bootstrap-legacy-env --compile-tf-ops
```

Dry-run a Lakeshore CGN dispatch:

```powershell
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method cgn --task-set cgn_bottleneck_v2 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json --dry-run
```

Launch current canonical simulator suites:

```powershell
python -m grasp_benchmark.run.sim --method graspvla --task-set track_a_cal_v3 --node em14
python -m grasp_benchmark.run.sim --method cgn --task-set track_a_cal_v3 --matrix
python -m grasp_benchmark.run.sim --method graspvla --task-set track_a_stress_v4 --node em14
python -m grasp_benchmark.run.sim --method cgn --task-set track_a_stress_v4 --matrix
```

Build a paper bundle from existing artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_corl2026_bundle_v3.ps1
```

## Lakeshore Notes

Lakeshore is a Slurm cluster. The login node is for editing, file management, and job submission; GPU work must run through `srun`, `sbatch`, or `salloc`.

Project-owned files should stay under:

```text
/projects/cs_yifan16_chi/zlu31
```

The verified CGN runtime is:

```text
/projects/cs_yifan16_chi/zlu31/conda_envs/gb-cgn-tf212
```

Typical Slurm GPU allocation:

```bash
source /etc/profile.d/modules.sh
module load slurm/lakeshore/23.02.4
srun -A cs_yifan16_chi -p batch_gpu2 --gres=gpu:1 nvidia-smi -L
```

Login-node `nvidia-smi` failures are expected and do not mean Lakeshore lacks GPUs.

## Documentation Policy

Keep GitHub documentation small and current:

- Keep one detailed tracked report: [docs/current_benchmark_report.md](docs/current_benchmark_report.md).
- Keep generated artifacts under `artifacts/`.
- Do not add scattered historical reports back under `docs/`.
- Do not promote CGN numbers from a partial or pre-patch run into the headline table.
