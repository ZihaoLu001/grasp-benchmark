# Track A-Cal Compare: GraspVLA vs CGN Full Modular vs AnyGrasp Full Modular (2026-04-07)

## Scope

- This is the frozen `Track A-Cal` fairness table for Phase 1.
- Shared protocol is unchanged:
  - `track_a_cal_v1`
  - shared gripper / shared cameras / shared workspace
  - blocking control
  - `lift >= 15 cm` and `hold >= 2 s`
  - max `3` attempts per trial
- `Track A-Stress` and `Track B` remain appendix layers only.

## Headline Result

- `GraspVLA`: `14/15`
- `CGN full modular`: `0/15`
- `AnyGrasp full modular`: `0/15`

Formal aggregate bundle:
- `D:\codex\grasp-benchmark\artifacts\reports\track_a_cal_compare_graspvla_cgn_anygrasp_latest\report.md`
- `D:\codex\grasp-benchmark\artifacts\reports\track_a_cal_compare_graspvla_cgn_anygrasp_latest\summary.csv`
- `D:\codex\grasp-benchmark\artifacts\reports\track_a_cal_compare_graspvla_cgn_anygrasp_latest\teacher_summary_zh_clean.md`

Parent runs:
- `GraspVLA`: `20260405_053120_graspvla_track_a_cal_v1_shared_sim`
- `CGN full modular`: `20260406_115112_cgn_track_a_cal_v1_shared_sim`
- `AnyGrasp full modular`: `20260407_062119_anygrasp_track_a_cal_v1_shared_sim`

## By Task

- `GraspVLA / language_conditioned_single_target_pick`: `10/10`
- `GraspVLA / arbitrary_grasping_common_opaque`: `4/5`
- `CGN full modular / language_conditioned_single_target_pick`: `0/10`
- `CGN full modular / arbitrary_grasping_common_opaque`: `0/5`
- `AnyGrasp full modular / language_conditioned_single_target_pick`: `0/10`
- `AnyGrasp full modular / arbitrary_grasping_common_opaque`: `0/5`

## Failure Taxonomy

- `GraspVLA`
  - `1` x `task_failure`
- `CGN full modular`
  - `11` x `task_failure`
  - `2` x `grounding_error: carrot`
  - `2` x `grounding_error: power drill`
- `AnyGrasp full modular`
  - `11` x `grasp_proposal: AnyGrasp returned no grasp group for the current masked observation`
  - `2` x `grounding_error: carrot`
  - `2` x `grounding_error: power drill`

## Interpretation

- `GraspVLA` remains clearly strongest on the frozen shared leaderboard.
- `CGN full modular` and `AnyGrasp full modular` are now both fully assembled under the same protocol, so the headline table is no longer relying on raw / interim modular numbers.
- The two modular baselines fail for different dominant reasons:
  - `CGN` usually reaches planning/execution but does not satisfy the success criterion.
  - `AnyGrasp` more often fails upstream at grasp proposal generation after object masking.
- `Track B` is still much higher for `GraspVLA`, but that native-reference result is not mixed into the fairness claim.

## AnyGrasp Insertion Notes

- License is installed operationally on `em14`.
- Readiness passed with:
  - matching feature id
  - `import_status = 0`
  - `license_ready = true`
  - `checkpoint_present = true`
- Final AnyGrasp insertion required:
  - installing official detection/tracking checkpoints from the provided Google Drive links
  - building `MinkowskiEngine` and `pointnet2` in `gb-anygrasp`
  - fixing null-proposal handling so `None` grasp groups are recorded as `grasp_proposal` instead of `scene_execution`
  - fixing latency accounting so failed AnyGrasp attempts still record non-zero inference time

Key artifacts:
- readiness: `D:\codex\grasp-benchmark\artifacts\anygrasp\20260407_053602_em14.json`
- final run: `D:\codex\grasp-benchmark\artifacts\runs\20260407_062119_anygrasp_track_a_cal_v1_shared_sim\results.csv`

