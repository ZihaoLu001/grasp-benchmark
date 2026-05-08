# Current Benchmark Report

Last updated: 2026-05-08.

This is the single detailed report intended to live in the GitHub repository. Generated logs, plots, videos, Slurm manifests, and intermediate materials stay under `artifacts/`.

## Executive Summary

The benchmark compares released grasping systems under a shared simulator protocol: same Franka robot, same gripper, same cameras, same workspace, same blocking controller, up to three attempts per trial, and the same `15 cm / 2 s` lift-and-hold success rule.

The current shared-protocol result favors GraspVLA across the completed simulator suites. Contact-GraspNet is evaluated as one modular pipeline: GroundingDINO target localization, depth masking, Contact-GraspNet grasp proposals, and shared planner/controller execution.

AnyGrasp is excluded from current comparative claims until fresh SDK access and runtime validation are available.

## Current Headline Results

| Suite | GraspVLA | Contact-GraspNet modular pipeline | Interpretation |
| --- | ---: | ---: | --- |
| Main Shared Grasping Benchmark (`track_a_cal_v3`) | `88 / 90` | `25 / 90` (`27.78%`) | headline fair table |
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
- two-camera observation contract;
- simulator scenes and object sets;
- blocking controller semantics;
- up to three attempts per trial;
- success defined as lifting the target object at least 15 cm and holding it for 2 s;
- standardized logs with success, attempts, lift height, hold duration, inference latency, cycle time, and stage labels.

The headline comparison uses the shared protocol only. Implementation-check suites verify runtime contracts and are not separate compared systems.

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

> We evaluate GraspVLA and a Contact-GraspNet-based modular pipeline under one shared simulator protocol: same Franka robot, cameras, gripper, controller, attempt budget, and `15 cm / 2 s` lift-and-hold success rule. Under this protocol, GraspVLA achieves `88/90` on the Main Shared Grasping Benchmark and `160/168` on the Hard Shared Grasping Stress Test; the Contact-GraspNet modular pipeline achieves `25/90` and `20/168`. On a 12-trial Lakeshore H100 speed validation subset, GraspVLA records median `136.6 ms` model-server round-trip latency and median `4.83 s` full-cycle trial time; the Contact-GraspNet modular pipeline records median `25.4 ms` adapter-step latency, median `11.45 s` cycle time on successful rows, and median `52.24 s` all-trial cycle time after including failed retries.
