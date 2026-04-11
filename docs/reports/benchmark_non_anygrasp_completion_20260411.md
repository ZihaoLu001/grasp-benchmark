# Benchmark Non-AnyGrasp Completion Note (2026-04-11)

## Scope

- This note summarizes what is now fully evaluated in the benchmark without waiting for a refreshed AnyGrasp license.
- It does not change the frozen benchmark protocol.
- It simply closes the non-AnyGrasp simulation scope that was still open before.

## What Is Now Complete

### 1. `Track A-Cal` main fairness table

Frozen headline table:

- `GraspVLA`: `14/15`
- `CGN full modular`: `0/15`
- `AnyGrasp full modular`: historical artifact exists, but the current AnyGrasp lane is now blocked by license mismatch on current `em14`

Primary artifact:

- [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_cal_compare_graspvla_cgn_anygrasp_latest/report.md)

### 2. Shared transparent subset

Completed methods:

- `GraspVLA`: `4/4`
- `CGN full modular`: `0/4`

Primary artifact:

- [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_transparent_compare_graspvla_cgn_latest/report.md)

### 3. `Track A-Stress` full shared stress run, non-AnyGrasp subset

This is the most important newly closed item.

Fresh full `track_a_v2` results:

- `GraspVLA / language_conditioned_single_target_pick`: `23/25`
- `GraspVLA / arbitrary_grasping_transparent`: `4/4`
- `GraspVLA / arbitrary_grasping_common_opaque`: `5/5`
- `GraspVLA total`: `32/34`

- `CGN full modular / language_conditioned_single_target_pick`: `0/25`
- `CGN full modular / arbitrary_grasping_transparent`: `0/4`
- `CGN full modular / arbitrary_grasping_common_opaque`: `0/5`
- `CGN full modular total`: `0/34`

Primary artifact:

- [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_stress_compare_graspvla_cgn_latest/report.md)

## Main Interpretation

- The earlier historical reading of `Track A-Stress = 0/34` for `GraspVLA` is no longer the current state of the repo.
- With the repaired shared simulation lane, `GraspVLA` is now strong on the full frozen `track_a_v2` stress suite.
- The most visible remaining weakness for `GraspVLA` is the `distractors` condition:
  - `3/5`
- `CGN full modular` remains at `0/34` on the same shared stress protocol.
- `CGN` fails in two main ways:
  - `GroundingDINO` misses on some language-conditioned scenes, especially `power drill`
  - most remaining scenes reach `task_failure` after the modular pipeline already has a proposal/execution attempt

## Important Operational Note

- We also tested `CGN` cross-node on `rll_6000_1/2`.
- Those hosts exposed a CUDA-extension incompatibility:
  - `CUDA error: no kernel image is available for execution on the device`
- To finish the non-AnyGrasp benchmark cleanly, the formal `CGN track_a_v2` run was completed on `em14` via multi-GPU sharding instead.

## What Still Remains After This

Only these benchmark items are still incomplete:

1. `AnyGrasp` transparent subset and final stress insertion
2. real-world pilot benchmark numbers
3. Phase 2 constraint / affordance grasping
4. modular `Track B` native best-case reference tracks

So the simulation mainline is now largely closed except the blocked AnyGrasp lane.
