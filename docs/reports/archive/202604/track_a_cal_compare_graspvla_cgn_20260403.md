# Track A-Cal Compare Report (2026-04-03)

## Scope

- Formal shared-setting simulation compare for the new `Track A-Cal` leaderboard.
- Methods: `GraspVLA` and `Contact-GraspNet`.
- Task set: `track_a_cal_v1`.
- `Track A-Stress` is preserved separately as the historical `track_a_v2` reference.
- `Track B` remains the frozen native-reference appendix only.

## Parent Runs

- `GraspVLA`: `20260403_232144_graspvla_track_a_cal_v1_shared_sim`
- `CGN`: `20260403_232144_cgn_track_a_cal_v1_shared_sim`
- `CGN` matrix shards:
  - `pabrtxl1 / shard_000 / gpu0`
  - `pabrtxl2 / shard_001 / gpu0`

## Headline

- `GraspVLA`: `0/15`
- `CGN`: `0/15`
- `Track A-Cal` is easier and more native-asset-focused than the previous stress track, but it is still all-zero across both methods.

## Failure Breakdown

- `GraspVLA`: `15` `task_failure`
- `CGN`: `14` `task_failure`
- `CGN`: `1` `grasp_proposal`

## Interpretation

- The v1.1 redesign successfully separated the benchmark into three layers:
  - `Track A-Cal`: main shared leaderboard
  - `Track A-Stress`: shared stress appendix
  - `Track B`: native reference
- However, `Track A-Cal` still collapses to all-zero results.
- This triggers the agreed health check:
  - stop expanding the benchmark
  - do not add AnyGrasp to the headline table yet
  - audit shared-runner / released-distribution alignment first
- Current evidence narrows the problem:
  - `Track A-Stress` was indeed too strong, but reducing it to native opaque assets was still not enough
  - the gap is not explained mainly by gripper geometry or success threshold alone
  - the next likely issue is remaining mismatch between the shared runner scenes and the released deployment distribution

## Key Artifacts

- Aggregate report:
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_latest/report.md`
- Teacher summary:
  `artifacts/reports/track_a_cal_compare_graspvla_cgn_latest/teacher_summary_zh_clean.md`
- Stress reference:
  `artifacts/reports/track_a_compare_graspvla_cgn_v2_latest/report.md`
- Diagnostic report:
  `artifacts/diagnostics/20260403_175506_graspvla_track_a_diagnostics/report.md`
- Track B native reference:
  `artifacts/official_sim/20260402_231726_em14_full/summary.json`
