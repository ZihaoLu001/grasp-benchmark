# Current Benchmark Report

Last updated: 2026-05-08.

This is the single detailed report intended to live in the GitHub repository. Generated logs, plots, videos, Slurm manifests, and intermediate materials stay under `artifacts/`.

## Executive Summary

The benchmark compares released grasping systems under a shared simulator protocol: same Franka robot, same gripper, same cameras, same workspace, same blocking controller, up to three attempts per trial, and the same `15 cm / 2 s` lift-and-hold success rule.

The current shared-protocol result favors GraspVLA across the completed simulator suites. Contact-GraspNet is evaluated in two ways:

- as a benchmark-owned shared modular pipeline for head-to-head task execution;
- as a depth+`K`+segmentation-map proposal-path appendix aligned with the public NVLabs Contact-GraspNet inference contract.

AnyGrasp is excluded from current comparative claims until fresh SDK access and runtime validation are available.

## Current Headline Results

| Suite | GraspVLA | Contact-GraspNet shared pipeline | Interpretation |
| --- | ---: | ---: | --- |
| Main Shared Grasping Benchmark (`track_a_cal_v3`) | `88 / 90` | `25 / 90` (`27.78%`) | headline fair table |
| Hard Shared Grasping Stress Test (`track_a_stress_v4`) | `160 / 168` | `20 / 168` (`11.90%`) | difficult-scene stress suite |
| Instruction Robustness Check (`instruction_robustness_v2`) | `38 / 40` | `8 / 40` (`20.00%`) | instruction and paraphrase diagnostic |
| Task-Oriented Grasping Pilot (`phase2_pilot_v1`) | `23 / 24` | `0 / 24` (`0.00%`) | small task-oriented extension |

Tracked evidence for the shared Contact-GraspNet pipeline:

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
| Contact-GraspNet official depth+segmap appendix, H100 | median `5.57 s` across all 138 trials; median `82.5 ms` on successful proposal/execution rows | median `32.87 s` across all 138 trials | full cycle includes proposal, planning, simulation, controller execution, and retry budget |

Current Contact-GraspNet appendix latency is bimodal: successful proposal/execution rows are fast, while rows without an executable proposal spend about 5.6 s in the proposal-search path. For this reason, model-serving latency and full episode cycle time are both reported.

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

The headline comparison uses the shared protocol only. Reference appendices are reported separately because they answer engineering questions about each method's preferred proposal path or runtime setup.

## Method Definitions

| Method | Repository definition | Reported result type |
| --- | --- | --- |
| GraspVLA | Public release through the aligned simulator wrapper | shared-protocol task execution |
| Contact-GraspNet shared pipeline | GroundingDINO localization, depth masking, Contact-GraspNet proposals, and shared planner/controller execution | benchmark-owned modular task execution |
| CGN official depth+segmap appendix | Contact-GraspNet proposal path from depth, camera matrix `K`, segmentation map, and RGB, followed by benchmark-owned Franka execution | proposal-path reference appendix |
| CGN native-reference appendix | fused point-cloud reference path with object segment IDs and official filtering enabled | engineering reference |
| AnyGrasp | pending fresh SDK access and runtime validation | excluded from current comparative claims |

## Contact-GraspNet Proposal-Path Appendix

The strict Contact-GraspNet appendix aligns the runner with the public Contact-GraspNet input contract used by NVLabs examples: depth map in meters, camera matrix `K`, segmentation map, RGB, local-region cropping, and contact filtering.

Result:

| Task group | Successes / trials |
| --- | ---: |
| language-conditioned single-target pick | `14 / 60` |
| arbitrary opaque grasping | `26 / 30` |
| transparent-object grasping | `0 / 48` |
| total | `40 / 138` (`28.99%`) |

Evidence:

```text
configs/results/cgn_official_depth_segmap_h100_20260508.json
```

The run completed four Lakeshore H100 shards plus finalization. The evidence file records:

- `488 / 488` runner traces with `input_contract=official_depth_k_segmap`;
- `use_raw_points=False`;
- `local_regions=True`;
- `filter_grasps=True`;
- TensorFlow GPU visibility;
- duplicate trial keys equal to `0`;
- target-selection violations equal to `0`.

The full episode score includes benchmark-owned Franka execution and the benchmark lift-and-hold rule. It is therefore reported as a Contact-GraspNet proposal-path appendix rather than a native robot-system score.

## Native-Reference Appendix

The fused point-cloud native-reference appendix is retained as secondary engineering context.

Result:

| Task group | Successes / trials |
| --- | ---: |
| language-conditioned single-target pick | `20 / 60` |
| arbitrary opaque grasping | `19 / 30` |
| transparent-object grasping | `0 / 48` |
| total | `39 / 138` (`28.26%`) |

Evidence:

```text
configs/results/cgn_native_reference_h100_20260507.json
```

The evidence file records all four GPU shards, finalization status, `939` checked debug payloads, official filtering confirmation, and TensorFlow GPU visibility.

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

The official depth+segmap appendix ran on Lakeshore jobs `365136-365139`, with CPU finalizer `365140`; all recorded `ExitCode=0:0`.

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

Run the strict Contact-GraspNet proposal-path appendix:

```powershell
python -m grasp_benchmark.run.sim --cluster-config lakeshore --method cgn --task-set track_b_cgn_official_depth_segmap_v1 --node lakeshore --available-nodes artifacts/preflight/lakeshore_available_nodes.json --execution-mode shared_track_a_sim --matrix --max-shards 4 --trace-steps
```

Build a paper bundle from existing artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_corl2026_bundle_v3.ps1
```

## Conclusion

> We evaluate GraspVLA and a Contact-GraspNet-based modular pipeline under one shared simulator protocol: same Franka robot, cameras, gripper, controller, attempt budget, and `15 cm / 2 s` lift-and-hold success rule. Under this protocol, GraspVLA achieves `88/90` on the Main Shared Grasping Benchmark and `160/168` on the Hard Shared Grasping Stress Test; the Contact-GraspNet shared pipeline achieves `25/90` and `20/168`. We also include a Contact-GraspNet proposal-path appendix using the public depth+`K`+segmentation-map inference contract, which obtains `40/138`. We report speed alongside success because the GraspVLA paper treats speed as a method-level metric; the official GraspVLA release reports about 200 ms serving latency on L40s, while our Contact-GraspNet appendix records median 5.57 s inference across all trials and median 82.5 ms on successful proposal/execution rows.
