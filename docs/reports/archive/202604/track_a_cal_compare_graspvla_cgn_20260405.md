# Track A-Cal Compare Report (2026-04-05)

## Scope

- Formal shared-setting simulation compare for the benchmark v1.1 headline leaderboard.
- Methods: `GraspVLA` and `Contact-GraspNet`.
- Task set: `track_a_cal_v1`.
- `Track A-Stress` remains the historical `track_a_v2` appendix.
- `Track B` remains the frozen native-reference appendix only.

## Parent Runs

- `GraspVLA`: `20260405_053120_graspvla_track_a_cal_v1_shared_sim`
- `CGN`: `20260405_090826_cgn_track_a_cal_v1_shared_sim`
- `CGN` matrix shards:
  - `pabrtxl1 / rll_6000_1 / gpu0`
  - `pabrtxl2 / rll_6000_2 / gpu0`

## Headline

- `GraspVLA`: `14/15`
- `CGN`: `0/15`
- This is the first formal `Track A-Cal` compare that yields clear separation under the shared benchmark protocol.

## Task Breakdown

- `GraspVLA / language_conditioned_single_target_pick`: `10/10`
- `GraspVLA / arbitrary_grasping_common_opaque`: `4/5`
- `CGN / language_conditioned_single_target_pick`: `0/10`
- `CGN / arbitrary_grasping_common_opaque`: `0/5`

## Failure Breakdown

- `GraspVLA`: `1` `task_failure`
- `CGN`: `14` `task_failure`
- `CGN`: `1` `grasp_proposal`

## Interpretation

- The current headline table now has usable benchmark resolution:
  - `GraspVLA` is strong on the shared calibration leaderboard.
  - `CGN` is still not competitive in the current raw shared-input form.
- The `CGN` result should not yet be read as the final ceiling for modular pipelines.
  - This run uses the first shared baseline:
    - front-depth point cloud
    - raw `Contact-GraspNet` proposal
    - shared action conversion
    - no segmentation
    - no detector filtering
- The main remaining benchmark task before adding `AnyGrasp` is therefore:
  - improve the modular baseline stack without breaking the shared protocol
  - keep `Track A-Cal` fixed
  - preserve `Track A-Stress` and `Track B` as secondary context layers

## Key Artifacts

- Aggregate report:
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_latest/report.md`
- Teacher summary:
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_latest/teacher_summary_zh_clean.md`
- Failure taxonomy:
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_latest/failure_taxonomy.csv`
- Stress reference:
  `artifacts/reports/track_a_compare_graspvla_cgn_v2_latest/report.md`
- Track B native reference:
  `artifacts/official_sim/20260402_231726_em14_full/summary.json`
