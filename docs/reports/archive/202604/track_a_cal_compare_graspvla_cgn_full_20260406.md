# Track A-Cal Full-Modular Compare Report (2026-04-06)

## Scope

- Formal shared-setting simulation compare for the benchmark v1.1 headline leaderboard.
- Methods included in the current headline table:
  - `GraspVLA`
  - `Contact-GraspNet + Segmentation + Grounding DINO + shared motion planner`
- Task set: `track_a_cal_v1`
- `Track A-Stress` remains appendix-only.
- `Track B` remains the frozen native-reference appendix only.
- `AnyGrasp` is not in this table yet because the public SDK is ready but the license bundle is still missing.

## Parent Runs

- `GraspVLA`: `20260405_053120_graspvla_track_a_cal_v1_shared_sim`
- `CGN full modular`: `20260406_115112_cgn_track_a_cal_v1_shared_sim`
- `CGN` ran as an `em14`-only matrix batch across GPUs `0-7`.

## Headline

- `GraspVLA`: `14/15`
- `CGN full modular`: `0/15`

This is the first `Track A-Cal` headline table where the modular side is no longer the raw interim baseline. The comparison now uses the full public `CGN + GroundingDINO + segmentation + shared planner` stack under the frozen shared protocol.

## Task Breakdown

- `GraspVLA / language_conditioned_single_target_pick`: `10/10`
- `GraspVLA / arbitrary_grasping_common_opaque`: `4/5`
- `CGN full modular / language_conditioned_single_target_pick`: `0/10`
- `CGN full modular / arbitrary_grasping_common_opaque`: `0/5`

## Failure Breakdown

- `GraspVLA`: `1` `task_failure`
- `CGN full modular`: `11` `task_failure`
- `CGN full modular`: `4` `grounding_error`

Current language-conditioned failures are dominated by `GroundingDINO` target localization misses on `carrot` and `power drill`. The remaining failures are fixed-plan execution failures after a proposal was obtained.

## Interpretation

- The current `Track A-Cal` headline table now supports a stronger fairness claim than the previous raw-CGN engineering compare.
- Under the shared benchmark protocol:
  - same robot embodiment
  - same shared cameras
  - same workspace
  - same attempt budget
  - same success rule
  - no method-specific scene edits
  `GraspVLA` is clearly ahead of the current public full-modular `CGN` stack.
- This still is **not** the final end-to-end vs modular conclusion, because the intended modular headline table also requires:
  - `AnyGrasp + Grounding DINO + shared motion planner`
- The benchmark protocol is now frozen enough that the next fair comparison step is simply to insert `AnyGrasp` after the license bundle arrives, without changing tasks or metrics.

## AnyGrasp Readiness

- Public SDK checkout is present under `third_party/upstreams/anygrasp_sdk`.
- Import probe on `em14` now succeeds.
- Current blocker is only the missing license config / bundle.
- Readiness artifact:
  `artifacts/anygrasp/20260406_105544_em14.json`

## Key Artifacts

- Aggregate report:
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_full_latest/report.md`
- Teacher summary:
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_full_latest/teacher_summary_zh_clean.md`
- Failure taxonomy:
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_full_latest/failure_taxonomy.csv`
- Track A-Stress appendix:
  `artifacts/reports/track_a_compare_graspvla_cgn_v2_latest/report.md`
- Track B native reference:
  `artifacts/official_sim/20260402_231726_em14_full/summary.json`
- AnyGrasp readiness:
  `artifacts/anygrasp/20260406_105544_em14.json`
