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
```

The tracked evidence records all expected shards for the four suites, duplicate scene IDs equal to `0`, and target-selection violations equal to `0`.

## Speed and Latency

Speed is reported next to success rate. The GraspVLA paper includes speed in its real-world method comparison, and the official GraspVLA repository reports approximate model-serving latency.

| Evidence source | Inference latency | End-to-end cycle time | Notes |
| --- | ---: | ---: | --- |
| GraspVLA official release notes | about `200 ms` on one NVIDIA L40s | not remeasured in this repository | release-reported serving latency |
| GraspVLA paper comparison | `5 Hz` for GraspVLA, `37 Hz` for AnyGrasp | paper-level metric | speed is treated as a method-level comparison dimension |
| Contact-GraspNet modular pipeline, H100 | median `5.57 s` across official-input validation trials; median `82.5 ms` on successful proposal/execution rows | median `32.87 s` across all validation trials | full cycle includes proposal, planning, simulation, controller execution, and retry budget |

Current Contact-GraspNet latency is bimodal: successful proposal/execution rows are fast, while rows without an executable proposal spend about 5.6 s in the proposal-search path. For this reason, model-serving latency and full episode cycle time are both reported.

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

Run the Contact-GraspNet official-input validation suite:

```powershell
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method cgn --task-set track_b_cgn_official_depth_segmap_v1 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json --execution-mode shared_track_a_sim --matrix --max-shards 4 --trace-steps
```

Build a paper bundle from existing artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_corl2026_bundle_v3.ps1
```

## Conclusion

> We evaluate GraspVLA and a Contact-GraspNet-based modular pipeline under one shared simulator protocol: same Franka robot, cameras, gripper, controller, attempt budget, and `15 cm / 2 s` lift-and-hold success rule. Under this protocol, GraspVLA achieves `88/90` on the Main Shared Grasping Benchmark and `160/168` on the Hard Shared Grasping Stress Test; the Contact-GraspNet modular pipeline achieves `25/90` and `20/168`. We report speed alongside success because the GraspVLA paper treats speed as a method-level metric; the official GraspVLA release reports about 200 ms serving latency on L40s, while the Contact-GraspNet implementation check records median 5.57 s inference across validation trials and median 82.5 ms on successful proposal/execution rows.
