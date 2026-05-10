# grasp-benchmark

`grasp-benchmark` is a release-centric simulator benchmark for comparing end-to-end and modular robot grasping systems under one shared execution protocol.

The repository is organized around one practical question:

> If released grasping systems are placed in the same simulated scenes, with the same rendered camera rig, robot, gripper, controller, attempt budget, and lift-and-hold success rule, what happens when each system uses its declared input interface?

## Start Here

Recommended reading order:

1. [Current Benchmark Report](docs/current_benchmark_report.md): the single consolidated project report.
2. This README: experiment names, current results, and run commands.
3. `configs/results/`: small tracked evidence summaries for the tables below.

Generated logs, videos, plots, and Slurm manifests live under `artifacts/`.

## Current Results

As of May 8, 2026, the shared-protocol benchmark uses a fixed Franka simulation setup, fixed rendered camera rig, blocking control, up to three attempts per trial, and a success rule of lifting the target object by at least 15 cm and holding it for 2 s.

Each suite is made from paired simulator trials: both methods run on the same scene definitions, object layouts, instructions, robot, controller, and success rule. The main public comparison below is view-matched: one row compares both systems with the front camera only, and one row compares both systems with the front and side cameras.

## Shared Experimental Setup

The tables below use the same simulator setup for both methods.

| Component | Setting |
| --- | --- |
| Simulator | GraspVLA playground / LIBERO floor-manipulation environment with offscreen rendering |
| Robot and control | Franka-style arm, shared gripper, `IK_POSE` controller, blocking execution, `5 Hz` control frequency |
| Workspace | fixed tabletop workspace of `40 cm x 50 cm x 20 cm`, with target and clutter regions defined by the scene catalog |
| Cameras | two fixed RGB-D cameras: `front_view` and `side_view`, both `256 x 256`, `fovy=43` |
| Camera poses | `front_view`: position `(0.7555, 0.0000, 0.5388)`, quaternion `(0.5964, 0.3799, 0.3799, 0.5964)`; `side_view`: position `(-0.1000, 0.6928, 0.5000)`, quaternion `(0.0000, 0.0000, -0.5000, -0.8660)` |
| Method observations | GraspVLA receives RGB image streams according to the view setting; Contact-GraspNet receives RGB-D geometry, camera intrinsics `K`, and segmentation. The single-camera setting uses `front_view`; the two-camera setting fuses `front_view` and `side_view` before grasp proposal |
| Trial execution | `10` stabilization steps, up to `300` simulator control steps per attempt, and up to `3` attempts per trial |
| Success rule | lift the specified object by at least `15 cm` and hold it for `2 s` (`10` hold steps at `5 Hz`) |

The environment always renders the same two cameras for every trial. For fairness, the Main Shared Grasping Benchmark is reported with view-count parity:

- Single-camera setting: both methods use the `front_view` camera only. GraspVLA receives the front RGB image in both expected image slots; Contact-GraspNet uses front RGB-D, front intrinsics `K`, and segmentation.
- Two-camera setting: both methods use `front_view` and `side_view`. GraspVLA receives the two RGB streams; Contact-GraspNet uses a fused two-view RGB-D point cloud with segmentation before Contact-GraspNet proposal generation.

This is a view-matched system comparison. It does not force identical tensors, because GraspVLA and Contact-GraspNet have different released input contracts: GraspVLA is an RGB vision-language-action policy, while Contact-GraspNet is an RGB-D grasp-proposal method followed here by the benchmark planner/controller.

| Suite | Trials | What it tests |
| --- | ---: | --- |
| Main Shared Grasping Benchmark | 90 | primary shared-environment comparison suite: 60 language-conditioned single-target trials over five common opaque objects, plus 30 arbitrary opaque-object grasping trials |
| Hard Shared Grasping Stress Test | 168 | hard-case suite: 80 language-target trials with heavy distractors or occlusion, 40 cluttered arbitrary opaque trials, and 48 transparent-object trials |
| Instruction Robustness Check | 40 | prompt sensitivity: canonical, lexical, compositional, and distractor-aware instruction variants on matched scenes |
| Task-Oriented Grasping Pilot | 24 | small extension for part/constraint-aware grasping, including cup-handle and power-drill-handle instructions |

## View-Matched Main Benchmark

The fairest current headline is the Main Shared Grasping Benchmark under matched camera-view counts.

| View setting | GraspVLA input and result | Contact-GraspNet modular input and result |
| --- | ---: | ---: |
| Single front camera | front RGB duplicated to the two expected image slots: `68 / 90` (`75.56%`) | front RGB-D + `K` + segmentation: `25 / 90` (`27.78%`) |
| Two cameras | front + side RGB: `88 / 90` (`97.78%`) | fused front + side RGB-D + segmentation: `43 / 90` (`47.78%`) |

Interpretation: matching the number of camera views does not remove the performance gap on the current Main Shared Grasping Benchmark. Adding the side camera helps Contact-GraspNet substantially (`25 / 90` to `43 / 90`), but GraspVLA remains higher in both the single-front-camera and two-camera comparisons.

## Additional Suite Coverage

The broader suites below are useful stress diagnostics. They use the frozen released-interface setup: GraspVLA uses its two RGB views, while the current Contact-GraspNet modular pipeline uses the front RGB-D proposal path.

| Suite | GraspVLA | Contact-GraspNet modular pipeline | Use |
| --- | ---: | ---: | --- |
| Main Shared Grasping Benchmark | `88 / 90` | `25 / 90` | released-interface reference row |
| Hard Shared Grasping Stress Test | `160 / 168` | `20 / 168` | difficult-scene stress suite |
| Instruction Robustness Check | `38 / 40` | `8 / 40` | instruction and paraphrase diagnostic |
| Task-Oriented Grasping Pilot | `23 / 24` | `0 / 24` | small task-oriented extension |

Tracked machine-readable evidence:

- [configs/results/cgn_shared_protocol_h100_20260508.json](configs/results/cgn_shared_protocol_h100_20260508.json)
- [configs/results/fair_sensor_view_ablation_h100_20260508.json](configs/results/fair_sensor_view_ablation_h100_20260508.json)
- [configs/results/speed_validation_lakeshore_h100_20260508.json](configs/results/speed_validation_lakeshore_h100_20260508.json)

## Speed and Latency

Speed is part of the comparison. The GraspVLA paper reports speed in the real-world comparison table (`5 Hz` for GraspVLA, `37 Hz` for AnyGrasp), and the official GraspVLA repository lists an approximate single-GPU inference latency of about `200 ms` on an NVIDIA L40s.

The repository now also includes a direct Lakeshore H100 speed validation on the same 12-trial subset of the Main Shared Grasping Benchmark (`track_a_cal_v3`). The GraspVLA model server was launched inside the same Slurm GPU allocation and validated before trials began; server startup is excluded from per-trial timing.

| Method | Speed-validation subset | Logged latency signal | Full trial cycle time, including retries | Result |
| --- | --- | ---: | ---: | ---: |
| GraspVLA | 12 Main Shared trials on Lakeshore H100 | median `136.6 ms` model-server round trip | median `4.83 s` | `12 / 12` |
| Contact-GraspNet modular pipeline | same 12 trials on Lakeshore H100 | median `25.4 ms` adapter-step average | median `52.24 s` | `5 / 12` |

The full trial cycle is the operational speed metric: it includes simulator stepping, retry budget, controller execution, logging, and success checking. The Contact-GraspNet all-trial median is dominated by failed rows: `7 / 12` trials used all three attempts, with a failed-trial median of `52.39 s`; the successful Contact-GraspNet rows have median full-cycle time `11.45 s`. The logged latency column is a diagnostic signal, not a direct neural-network speed comparison: for GraspVLA it is the model-server request round trip, while for Contact-GraspNet it is averaged over adapter control steps and includes many cached-action steps after a grasp plan has already been produced.

Primary speed references:

- [GraspVLA official repository](https://github.com/PKU-EPIC/GraspVLA)
- [GraspVLA paper HTML](https://arxiv.org/html/2505.03233v2)

## Contact-GraspNet Implementation Check

There is one Contact-GraspNet method in this repository: the modular pipeline reported in the shared-protocol tables. Its grasp-proposal stage is also checked against the public NVLabs-style `depth + K + segmap + RGB` input contract with `local_regions=True` and `filter_grasps=True`.

Evidence: [configs/results/cgn_official_depth_segmap_h100_20260508.json](configs/results/cgn_official_depth_segmap_h100_20260508.json).

Trace evidence confirms `488 / 488` Contact-GraspNet runner calls used `input_contract=official_depth_k_segmap`, `use_raw_points=False`, `local_regions=True`, `filter_grasps=True`, and TensorFlow GPU visibility. This is an implementation check, not a second compared Contact-GraspNet system.

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

Use the readable suite names first. Put internal IDs in parentheses only when readers need to reproduce the exact command.

## Which Task Set Should I Use?

| Goal | Use |
| --- | --- |
| Main comparison | Main Shared Grasping Benchmark (`track_a_cal_v3`) |
| Hard-case analysis | Hard Shared Grasping Stress Test (`track_a_stress_v4`) |
| Instruction paraphrase analysis | Instruction Robustness Check (`instruction_robustness_v2`) |
| Task-oriented grasp examples | Task-Oriented Grasping Pilot (`phase2_pilot_v1`) |
| Contact-GraspNet implementation check | Contact-GraspNet Official-Input Validation Suite (`track_b_cgn_official_depth_segmap_v1`) |

## Method Definitions

| Method label | What it means in this repo | Reported claim |
| --- | --- | --- |
| GraspVLA | Public GraspVLA release through the aligned shared simulator wrapper | shared-protocol task-execution result |
| Contact-GraspNet modular pipeline | GroundingDINO target localization, depth masking, Contact-GraspNet proposals, and the shared planner/controller | benchmark-owned modular execution result |
| AnyGrasp | Excluded from current comparative claims | requires fresh SDK access and runtime revalidation |

## Contact-GraspNet Modular Pipeline

The Contact-GraspNet row is a complete modular grasping system assembled for this benchmark. Contact-GraspNet itself provides 6-DoF grasp proposals from RGB-D geometry; the language grounding, two-view fusion, and robot execution wrapper are benchmark components around that proposal model.

| Stage | Implementation in this benchmark |
| --- | --- |
| Target localization | GroundingDINO localizes language-conditioned targets using `GroundingDINO_SwinT_OGC.py`, `groundingdino_swint_ogc.pth`, `box_threshold=0.25`, and `text_threshold=0.20`. |
| Segmentation mask | The detection box is converted into a depth-band object mask. Arbitrary-object trials first use catalog labels and then a foreground-depth fallback if no class box is found. |
| View handling | Single-camera results use `front_view`; two-camera results fuse `front_view` and `side_view` RGB-D points after transforming side-view points into the front-camera frame. |
| Grasp proposal | Contact-GraspNet predicts ranked 6-DoF grasp candidates. The checked official-input path uses depth in meters, camera matrix `K`, RGB, segmentation map, `local_regions=True`, and `filter_grasps=True`. |
| Execution | The benchmark planner converts the selected grasp pose into pre-grasp, grasp, close, lift, and hold actions for the shared `IK_POSE` controller, rejecting impossible gripper openings before execution. |
| Success check | The shared evaluator applies the same `15 cm / 2 s` lift-and-hold rule used for GraspVLA. |

Single-camera CGN uses only `front_view`: GroundingDINO or foreground filtering builds a front mask, masked front depth is back-projected with intrinsics `K`, and Contact-GraspNet receives the checked `depth + K + segmap + RGB` proposal payload.

Two-camera fused RGB-D CGN uses `front_view` and `side_view`: both views produce masked point clouds, side-view points are transformed through the camera extrinsics into the front-camera frame, the two point clouds are concatenated, and the fused segmented geometry is passed to the Contact-GraspNet proposal runner before shared planner/controller execution.

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
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method graspvla --task-set track_a_cal_v3 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method cgn --task-set track_a_cal_v3 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json --matrix --max-shards 4
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method graspvla --task-set track_a_stress_v4 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method cgn --task-set track_a_stress_v4 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json --matrix --max-shards 4
```

Run the Contact-GraspNet official-input validation suite:

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
