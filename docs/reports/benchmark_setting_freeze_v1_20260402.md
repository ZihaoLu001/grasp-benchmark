# Benchmark Setting Freeze v1

## Purpose

This note freezes the difference between:

- the current **official GraspVLA simulation setting** that we already ran end-to-end
- the future **shared benchmark setting** that will be used for fair comparison across methods

The key point is simple:

- the current official GraspVLA run is a **method-native reproduction**
- the benchmark setting will be a **shared-protocol comparison**

They are related, but they are not the same experiment.

## Side-by-Side Comparison

| Item | Official GraspVLA Sim Setting | Unified Benchmark Setting |
|---|---|---|
| Goal | Reproduce the released GraspVLA simulation stack | Fairly compare end-to-end and modular methods |
| Primary code path | `third_party/upstreams/GraspVLA-playground/` | `src/grasp_benchmark/` wrapper plus per-method adapters |
| Task suites | Official `playground`, `libero_object`, `libero_10`, `libero_goal` | Track A task groups from `configs/tasks/track_a_v1.yaml` |
| Instruction style | Simplified grasp-only instructions such as `pick up {object}` | Fixed benchmark templates, starting from `pick up {object}` and `pick up any object` |
| Cameras | Two fixed RGB views: `front_view`, `side_view` | One shared dual fixed camera rig for all methods |
| Camera resolution | `256 x 256` | `256 x 256` in v1 |
| Depth availability | GraspVLA official sim consumes RGB only | Shared sensor stack records RGB and depth for all methods; methods may consume the allowed subset |
| Control frequency | `5 Hz` | `5 Hz` in simulation unless a shared benchmark revision changes it for everyone |
| Gripper / embodiment | Official GraspVLA playground uses `franka_with_extended_finger` | One shared robot and gripper definition for every baseline in Track A |
| Scene edits | Official code removes the basket in some tasks because it occludes the side view | No method-specific scene edits once the shared benchmark is frozen |
| Success rule | Official task success from the LIBERO / BDDL goal, including grasp lift logic in the released environment | Shared success rule from `configs/sensors/track_a_dual_realsense.yaml`: `lift >= 15 cm` and `hold >= 2 s` |
| Attempts per trial | Single official rollout per seed in sim | Up to `3` attempts per trial in benchmark evaluation |
| Metrics | Official success rate from generated videos / statistics | `task_success`, `spl`, `attempts_to_success`, `inference_latency`, `cycle_time`, plus failure taxonomy |
| Purpose of result | Understand GraspVLA performance under its released deployment stack | Produce a publishable fairness claim across methods |

## What Is Already Frozen For The Benchmark

These settings are already written in the benchmark configs:

- Sensor stack:
  `configs/sensors/track_a_dual_realsense.yaml`
- Task set:
  `configs/tasks/track_a_v1.yaml`
- GraspVLA method config:
  `configs/methods/graspvla.yaml`

Track A v1 currently freezes:

- dual fixed front and side cameras
- RGB plus depth recorded from both cameras
- blocking control
- workspace `40 x 50 x 20 cm`
- success rule `lift >= 15 cm` and `hold >= 2 s`
- attempt budget `3`
- task groups:
  - `language_conditioned_single_target_pick`
  - `arbitrary_grasping_transparent`

## Why The Two Settings Must Stay Separate

If we mix these two settings together, we lose the ability to answer two different questions:

1. Can we run the released GraspVLA stack faithfully?
2. Under one shared protocol, how does GraspVLA compare with modular baselines?

The official simulation run answers the first question.
The benchmark setting is designed to answer the second.

## Practical Interpretation

For meetings, the safest wording is:

> We have already reproduced the released GraspVLA simulation stack under the official method-native setting.  
> We have not yet finished the final shared benchmark setting comparison, because that requires every baseline to run under the same sensor, embodiment, success, and logging protocol.

## Current Recommendation

Use the current official GraspVLA simulation artifact as:

- the architecture understanding milestone
- the method-native reference line
- the sanity check before integrating modular baselines

Do **not** use it yet as the final benchmark claim.
