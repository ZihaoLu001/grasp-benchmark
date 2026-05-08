# grasp-benchmark

`grasp-benchmark` is a release-centric simulator benchmark for comparing end-to-end and modular robot grasping systems under one shared execution protocol.

The repository is organized around one practical question:

> If released grasping systems are placed in the same simulated scenes, with the same cameras, robot, gripper, controller, attempt budget, and lift-and-hold success rule, what happens?

## Start Here

Recommended reading order:

1. [Current Benchmark Report](docs/current_benchmark_report.md): the single consolidated project report.
2. This README: experiment names, current results, and run commands.
3. `configs/results/`: small tracked evidence summaries for the tables below.

Generated logs, videos, plots, and Slurm manifests live under `artifacts/`.

## Current Results

As of May 8, 2026, the shared-protocol benchmark uses a fixed Franka simulation setup, fixed camera geometry, blocking control, up to three attempts per trial, and a success rule of lifting the target object by at least 15 cm and holding it for 2 s.

| Suite | GraspVLA | Contact-GraspNet shared pipeline | Use |
| --- | ---: | ---: | --- |
| Main Shared Grasping Benchmark | `88 / 90` | `25 / 90` | headline fair-comparison suite |
| Hard Shared Grasping Stress Test | `160 / 168` | `20 / 168` | difficult-scene stress suite |
| Instruction Robustness Check | `38 / 40` | `8 / 40` | instruction and paraphrase diagnostic |
| Task-Oriented Grasping Pilot | `23 / 24` | `0 / 24` | small task-oriented extension |

Tracked machine-readable evidence: [configs/results/cgn_shared_protocol_h100_20260508.json](configs/results/cgn_shared_protocol_h100_20260508.json).

## Speed and Latency

Speed is part of the comparison. The GraspVLA paper reports speed in the real-world comparison table, and the official GraspVLA repository lists an approximate single-GPU inference latency of 200 ms on an NVIDIA L40s.

| Evidence source | Inference latency | End-to-end cycle time | Interpretation |
| --- | ---: | ---: | --- |
| GraspVLA official release notes | about `200 ms` on one L40s | not remeasured in this repository | This is the release-reported model-serving latency. |
| GraspVLA paper comparison | `5 Hz` for GraspVLA, `37 Hz` for AnyGrasp | paper-level comparison | The paper treats speed as a method-level metric alongside success rate. |
| Contact-GraspNet official depth+segmap appendix, H100 | median `5.57 s` across all 138 trials; median `82.5 ms` on successful proposal/execution rows | median `32.87 s` across all 138 trials | The full cycle includes proposal, planning, simulation, controller execution, and retry budget. |

Primary speed references:

- [GraspVLA official repository](https://github.com/PKU-EPIC/GraspVLA)
- [GraspVLA paper HTML](https://arxiv.org/html/2505.03233v2)

## Contact-GraspNet Reference Appendix

The strict Contact-GraspNet proposal-path appendix uses the public NVLabs-style `depth + K + segmap + RGB` input contract with `local_regions=True` and `filter_grasps=True`, then executes the resulting proposal through the benchmark-owned Franka controller and lift-and-hold success rule.

| Appendix | Result | Evidence |
| --- | ---: | --- |
| CGN Official Depth+Segmap Proposal Appendix | `40 / 138` (`28.99%`) | [configs/results/cgn_official_depth_segmap_h100_20260508.json](configs/results/cgn_official_depth_segmap_h100_20260508.json) |
| CGN Native-Reference Appendix | `39 / 138` (`28.26%`) | [configs/results/cgn_native_reference_h100_20260507.json](configs/results/cgn_native_reference_h100_20260507.json) |

The official depth+segmap appendix completed all four Lakeshore H100 shards and the CPU finalizer. Trace evidence confirms `488 / 488` Contact-GraspNet runner calls used `input_contract=official_depth_k_segmap`, `use_raw_points=False`, `local_regions=True`, `filter_grasps=True`, and TensorFlow GPU visibility.

## Experiment Name Guide

Internal `task_set` IDs are stable for scripts and reproducibility. Use the readable suite names in reports and discussions.

| Suite name | Internal ID | Status | Plain-English meaning |
| --- | --- | --- | --- |
| Main Shared Grasping Benchmark | `track_a_cal_v3` | current headline | 90 paired trials under the frozen shared protocol |
| Hard Shared Grasping Stress Test | `track_a_stress_v4` | current diagnostic | 168 difficult paired trials with clutter, occlusion, and transparent objects |
| Instruction Robustness Check | `instruction_robustness_v2` | current diagnostic | same scenes with different instruction phrasings |
| Task-Oriented Grasping Pilot | `phase2_pilot_v1` | current diagnostic | small suite for handle/part-oriented grasping |
| Sim-to-Real Robustness Proxy | `sim2real_proxy_v2` | supporting diagnostic | simulated perturbations used as transfer stressors |
| CGN Pipeline Diagnostic | `cgn_bottleneck_v2` | supporting diagnostic | isolates grounding, proposal, planning, and execution stages |
| CGN Official Depth+Segmap Proposal Appendix | `track_b_cgn_official_depth_segmap_v1` | current reference | closest repository-supported path to the public Contact-GraspNet inference contract |
| CGN Native-Reference Appendix | `track_b_cgn_native_v2` | reference | fused-point-cloud engineering context |

Use the readable suite names first. Put internal IDs in parentheses only when readers need to reproduce the exact command.

## Which Task Set Should I Use?

| Goal | Use |
| --- | --- |
| Main comparison | Main Shared Grasping Benchmark (`track_a_cal_v3`) |
| Hard-case analysis | Hard Shared Grasping Stress Test (`track_a_stress_v4`) |
| Instruction paraphrase analysis | Instruction Robustness Check (`instruction_robustness_v2`) |
| Task-oriented grasp examples | Task-Oriented Grasping Pilot (`phase2_pilot_v1`) |
| Contact-GraspNet proposal-path context | CGN Official Depth+Segmap Proposal Appendix (`track_b_cgn_official_depth_segmap_v1`) |
| Fused-point-cloud CGN engineering context | CGN Native-Reference Appendix (`track_b_cgn_native_v2`) |

## Method Definitions

| Method label | What it means in this repo | Reported claim |
| --- | --- | --- |
| GraspVLA | Public GraspVLA release through the aligned shared simulator wrapper | shared-protocol task-execution result |
| Contact-GraspNet shared pipeline | GroundingDINO target localization, depth masking, Contact-GraspNet proposals, and the shared planner/controller | benchmark-owned modular execution result |
| CGN official depth+segmap appendix | NVLabs Contact-GraspNet proposal path from depth, `K`, `segmap`, and RGB, followed by benchmark-owned Franka execution | proposal-path reference appendix |
| AnyGrasp | Excluded from current comparative claims | requires fresh SDK access and runtime revalidation |

## Architecture

```text
configs/
  cluster/      Lakeshore and other execution environments
  methods/      method definitions, runtime overrides, checkpoints
  results/      small tracked evidence summaries for public tables
  scenes/       simulator scene catalogs
  sensors/      shared camera/gripper/success-rule contracts
  tasks/        stable task-set IDs and readable suite names

src/grasp_benchmark/
  adapters/     method adapters and modular perception/planning components
  runners/      simulator and Contact-GraspNet runtime runners
  run/          local/cluster dispatch entrypoints
  report/       result aggregation and paper-bundle generation
  audit/        diagnostic experiments

docs/
  current_benchmark_report.md

artifacts/
  generated runs, logs, reports, videos, and Slurm manifests
```

Contact-GraspNet language-target tasks use:

```text
GroundingDINO -> depth mask -> Contact-GraspNet -> shared planner/controller -> 15 cm / 2 s success check
```

The shared protocol evaluates complete task execution, not only whether a grasp proposal exists.

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

Run the strict Contact-GraspNet proposal-path appendix:

```powershell
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method cgn --task-set track_b_cgn_official_depth_segmap_v1 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json --execution-mode shared_track_a_sim --matrix --max-shards 4 --trace-steps
```

Build a paper bundle from existing artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_corl2026_bundle_v3.ps1
```

## Lakeshore Notes

Lakeshore is a Slurm cluster. The login node is for editing, file management, and job submission; GPU work runs through `srun`, `sbatch`, or `salloc`.

Project-owned files should stay under:

```text
/projects/cs_yifan16_chi/zlu31
```

The verified Contact-GraspNet runtime is:

```text
/projects/cs_yifan16_chi/zlu31/conda_envs/gb-cgn-tf212
```

Typical Slurm GPU allocation:

```bash
source /etc/profile.d/modules.sh
module load slurm/lakeshore/23.02.4
srun -A cs_yifan16_chi -p batch_gpu2 --gres=gpu:1 nvidia-smi -L
```

## Documentation Policy

Keep GitHub documentation small and current:

- Keep one detailed tracked report: [docs/current_benchmark_report.md](docs/current_benchmark_report.md).
- Keep generated artifacts under `artifacts/`.
- Keep small machine-readable evidence summaries under `configs/results/`.
- Keep public names readable; use internal IDs only for reproduction.
