# Current Benchmark Report

Last updated: 2026-05-08.

This is the single detailed report intended to live in the GitHub repository. Generated logs, plots, videos, Slurm manifests, and intermediate materials stay under `artifacts/`.

## Executive Summary

The benchmark compares released grasping systems under a shared simulator protocol: same Franka robot, same gripper, same rendered camera rig, same workspace, same blocking controller, up to three attempts per trial, and the same `15 cm / 2 s` lift-and-hold success rule. Each system uses its declared input interface.

The current shared-protocol result favors GraspVLA across the completed simulator suites. Contact-GraspNet is evaluated as one modular pipeline: GroundingDINO target localization, depth masking, Contact-GraspNet grasp proposals, and shared planner/controller execution.

AnyGrasp is excluded from current comparative claims until fresh SDK access and runtime validation are available.

## Shared Experimental Setup

The benchmark uses one frozen simulator setup for the reported comparisons.

| Component | Setting |
| --- | --- |
| Simulator | GraspVLA playground / LIBERO floor-manipulation environment with offscreen rendering |
| Robot and control | Franka-style arm, shared gripper, `IK_POSE` controller, blocking execution, `5 Hz` control frequency |
| Workspace | fixed tabletop workspace of `40 cm x 50 cm x 20 cm`, with target, clutter-left, clutter-right, clutter-back, and stress-test clutter-front regions defined by the scene catalog |
| Cameras | two fixed RGB-D cameras: `front_view` and `side_view`, both `256 x 256`, `fovy=43` |
| Camera poses | `front_view`: position `(0.7555, 0.0000, 0.5388)`, quaternion `(0.5964, 0.3799, 0.3799, 0.5964)`; `side_view`: position `(-0.1000, 0.6928, 0.5000)`, quaternion `(0.0000, 0.0000, -0.5000, -0.8660)` |
| Observation contract | both cameras are rendered and logged for every trial; GraspVLA receives `front_view_image` and `side_view_image`; Contact-GraspNet uses front RGB-D, front camera intrinsics `K`, and a segmentation map for the `depth + K + segmap + RGB` grasp-proposal path |
| Trial execution | `10` stabilization steps, up to `300` simulator control steps per attempt, and up to `3` attempts per trial |
| Success rule | lift the specified object by at least `15 cm` and hold it for `2 s` (`10` hold steps at `5 Hz`) |

The camera setup is therefore a two-camera environment, not a single-camera environment. The Contact-GraspNet shared pipeline uses the front RGB-D stream because the checked Contact-GraspNet proposal path is defined by the front depth map, camera intrinsics `K`, RGB image, and segmentation map. The side camera remains part of the shared rendered scene observation and is used by GraspVLA's two-view policy input.

This is a shared-environment system comparison, not a strict same-tensor sensor ablation. That distinction matters: GraspVLA and Contact-GraspNet are released with different observation contracts, so forcing identical tensors would be a separate diagnostic rather than the main method-level comparison.

## Current Headline Results

Each suite is a set of paired simulator trials. A trial specifies the scene, object layout, instruction, and success target. Both methods use the same robot, gripper, rendered camera rig, object poses, blocking controller, attempt budget, and lift-and-hold success rule. For language-conditioned trials, success requires lifting the named object; for arbitrary-grasping trials, success requires lifting a valid object from the scene; for task-oriented trials, success additionally checks the requested part or constraint.

| Suite | Trials | What it tests |
| --- | ---: | --- |
| Main Shared Grasping Benchmark (`track_a_cal_v3`) | 90 | primary shared-environment comparison suite: 60 language-conditioned single-target trials over five common opaque objects, plus 30 arbitrary opaque-object grasping trials |
| Hard Shared Grasping Stress Test (`track_a_stress_v4`) | 168 | hard-case suite: 80 language-target trials with heavy distractors or occlusion, 40 cluttered arbitrary opaque trials, and 48 transparent-object trials |
| Instruction Robustness Check (`instruction_robustness_v2`) | 40 | prompt sensitivity suite: the same basic and light-distractor scenes with canonical, lexical, compositional, and distractor-aware instruction variants |
| Task-Oriented Grasping Pilot (`phase2_pilot_v1`) | 24 | small extension for grasp constraints, including cup-handle grasping, avoiding the inside of the cup, and power-drill handle grasping |

| Suite | GraspVLA | Contact-GraspNet modular pipeline | Interpretation |
| --- | ---: | ---: | --- |
| Main Shared Grasping Benchmark (`track_a_cal_v3`) | `88 / 90` | `25 / 90` (`27.78%`) | headline shared-environment table |
| Hard Shared Grasping Stress Test (`track_a_stress_v4`) | `160 / 168` | `20 / 168` (`11.90%`) | difficult-scene stress suite |
| Instruction Robustness Check (`instruction_robustness_v2`) | `38 / 40` | `8 / 40` (`20.00%`) | instruction and paraphrase diagnostic |
| Task-Oriented Grasping Pilot (`phase2_pilot_v1`) | `23 / 24` | `0 / 24` (`0.00%`) | small task-oriented extension |

Tracked evidence for the Contact-GraspNet modular pipeline:

```text
configs/results/cgn_shared_protocol_h100_20260508.json
configs/results/speed_validation_lakeshore_h100_20260508.json
```

The tracked evidence records all expected shards for the four suites, duplicate scene IDs equal to `0`, and target-selection violations equal to `0`.

## Speed and Latency

Speed is reported next to success rate. The GraspVLA paper includes speed in its real-world method comparison, and the official GraspVLA repository reports approximate model-serving latency.

A direct Lakeshore H100 speed validation was run on the same 12-trial subset of the Main Shared Grasping Benchmark (`track_a_cal_v3`). The GraspVLA server was launched inside the same Slurm GPU allocation and validated before trials began; server startup is excluded from per-trial timing.

| Method | Validation subset | Logged latency signal | Full trial cycle time, including retries | Result |
| --- | --- | ---: | ---: | ---: |
| GraspVLA | 12 Main Shared trials on Lakeshore H100 | median `136.6 ms` model-server round trip | median `4.83 s` | `12 / 12` |
| Contact-GraspNet modular pipeline | same 12 trials on Lakeshore H100 | median `25.4 ms` adapter-step average | median `52.24 s` | `5 / 12` |

The full trial cycle is the operational speed metric: it includes simulator stepping, retry budget, controller execution, logging, and success checking. The Contact-GraspNet all-trial median is dominated by failed rows: `7 / 12` trials used all three attempts, with a failed-trial median of `52.39 s`; the successful Contact-GraspNet rows have median full-cycle time `11.45 s`. The logged latency column is a diagnostic signal, not a direct neural-network speed comparison: for GraspVLA it is the model-server request round trip, while for Contact-GraspNet it is averaged over adapter control steps and includes many cached-action steps after a grasp plan has already been produced.

Primary references:

- GraspVLA official repository: <https://github.com/PKU-EPIC/GraspVLA>
- GraspVLA paper HTML: <https://arxiv.org/html/2505.03233v2>

## Evaluation Protocol

The shared-protocol suites freeze the following factors:

- Franka robot and gripper;
- two fixed RGB-D cameras (`front_view` and `side_view`, `256 x 256`, `fovy=43`);
- simulator scenes and object sets;
- blocking controller semantics;
- up to three attempts per trial;
- 300 simulator control steps per attempt;
- success defined as lifting the target object at least 15 cm and holding it for 2 s;
- standardized logs with success, attempts, lift height, hold duration, logged latency signal, cycle time, and stage labels.

The headline comparison uses the shared protocol only. Implementation-check suites verify runtime contracts and are not separate compared systems. Sensor/view ablations should be reported separately from the headline table.

## Method Definitions

| Method | Repository definition | Reported result type |
| --- | --- | --- |
| GraspVLA | Public release through the aligned simulator wrapper | shared-protocol task execution |
| Contact-GraspNet modular pipeline | GroundingDINO localization, depth masking, Contact-GraspNet proposals, and shared planner/controller execution | benchmark-owned modular task execution |
| AnyGrasp | pending fresh SDK access and runtime validation | excluded from current comparative claims |

## Contact-GraspNet Implementation Check

There is only one Contact-GraspNet method in the benchmark: the modular pipeline in the shared-protocol results table. Its grasp-proposal stage is checked against the public Contact-GraspNet input contract used by NVLabs examples: depth map in meters, camera matrix `K`, segmentation map, RGB, local-region cropping, and contact filtering.

Evidence:

```text
configs/results/cgn_official_depth_segmap_h100_20260508.json
```

The evidence file records:

- `488 / 488` runner traces with `input_contract=official_depth_k_segmap`;
- `use_raw_points=False`;
- `local_regions=True`;
- `filter_grasps=True`;
- TensorFlow GPU visibility;
- duplicate trial keys equal to `0`;
- target-selection violations equal to `0`.

This is an implementation check, not a second compared Contact-GraspNet system.

## Lakeshore Runtime

Lakeshore execution uses the project-owned directory:

```text
/projects/cs_yifan16_chi/zlu31
```

The current H100-compatible Contact-GraspNet environment is:

```text
env:        /projects/cs_yifan16_chi/zlu31/conda_envs/gb-cgn-tf212
python:     3.10
tensorflow: 2.12.0
cuda:       11.8
cudnn:      8.6
custom ops: sm_80/sm_86/sm_89/sm_90 + compute_90 PTX
```

The official-input validation suite ran on Lakeshore jobs `365136-365139`, with CPU finalizer `365140`; all recorded `ExitCode=0:0`.

## Reproduction Pointers

Local tests:

```powershell
$env:PYTHONPATH = (Resolve-Path "src").Path
python -m pytest tests -q
```

Lakeshore preflight:

```powershell
python -m grasp_benchmark.preflight --cluster-config lakeshore --pool lakeshore --output artifacts/preflight/lakeshore_available_nodes.json
```

Prepare or revalidate H100-compatible Contact-GraspNet:

```powershell
python -m grasp_benchmark.prepare_cgn --node lakeshore --cluster-config lakeshore --bootstrap-legacy-env --compile-tf-ops
```

Run the current shared-protocol suites on Lakeshore:

```powershell
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method graspvla --task-set track_a_cal_v3 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method cgn --task-set track_a_cal_v3 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json --matrix --max-shards 4
```

Run the Contact-GraspNet official-input validation suite:

```powershell
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method cgn --task-set track_b_cgn_official_depth_segmap_v1 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json --execution-mode shared_track_a_sim --matrix --max-shards 4 --trace-steps
```

Build a paper bundle from existing artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_corl2026_bundle_v3.ps1
```

## Conclusion

> We evaluate GraspVLA and a Contact-GraspNet-based modular pipeline under one shared simulator protocol: same Franka robot, rendered camera rig, gripper, controller, attempt budget, and `15 cm / 2 s` lift-and-hold success rule, with each system using its declared input interface. Under this protocol, GraspVLA achieves `88/90` on the Main Shared Grasping Benchmark and `160/168` on the Hard Shared Grasping Stress Test; the Contact-GraspNet modular pipeline achieves `25/90` and `20/168`. On a 12-trial Lakeshore H100 speed validation subset, GraspVLA records median `136.6 ms` model-server round-trip latency and median `4.83 s` full-cycle trial time; the Contact-GraspNet modular pipeline records median `25.4 ms` adapter-step latency, median `11.45 s` cycle time on successful rows, and median `52.24 s` all-trial cycle time after including failed retries.
