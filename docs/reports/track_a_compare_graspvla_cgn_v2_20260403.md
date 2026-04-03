# Track A v2 Compare Report (2026-04-03)

## Scope

- Formal shared-setting simulation compare only.
- Methods: `GraspVLA` and `Contact-GraspNet`.
- Task set: `track_a_v2`.
- Track B remains a frozen native-reference appendix only.

## Parent Runs

- `GraspVLA`: `20260403_163649_graspvla_track_a_v2_shared_sim`
- `CGN`: `20260403_163700_cgn_track_a_v2_shared_sim`
- `GraspVLA diagnostics`: `20260403_175506_graspvla_track_a_diagnostics`

## Headline

- `GraspVLA`: `0/34`
- `CGN`: `0/34`
- The two methods fail for different reasons under the same Track A shared protocol.

## Failure Breakdown

- `GraspVLA`: `34` `task_failure`
- `CGN`: `30` `task_failure`
- `CGN`: `4` `grasp_proposal`

## Interpretation

- `GraspVLA` stays very strong in the frozen Track B native reference, but drops to `0/34` in Track A shared simulation.
- The diagnostic ablations show that switching back to the extended finger changes mean best lift only marginally.
- Relaxing from the shared Track A success rule to the official rule still does not recover success on the diagnostic set.
- The current gap is therefore not explained mainly by gripper geometry or the success threshold alone.
- `CGN` now produces valid proposals often enough to finish most trials as real `task_failure` episodes, so the shared-sim depth / intrinsics path is no longer the dominant blocker.

## Key Artifacts

- Aggregate report:
  `artifacts/reports/track_a_compare_graspvla_cgn_v2_latest/report.md`
- Teacher summary:
  `artifacts/reports/track_a_compare_graspvla_cgn_v2_latest/teacher_summary_zh.md`
- Diagnostic report:
  `artifacts/diagnostics/20260403_175506_graspvla_track_a_diagnostics/report.md`
- Track B native reference:
  `artifacts/official_sim/20260402_231726_em14_full/summary.json`
