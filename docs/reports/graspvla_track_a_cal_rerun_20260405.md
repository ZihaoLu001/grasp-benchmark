# GraspVLA Track A-Cal Rerun (2026-04-05)

## Headline

- Latest formal `Track A-Cal` rerun: `14/15`.
- The only failed trial is `arbitrary_grasping_common_opaque__opaque_basic__003` with `object_id=power_drill`.
- This confirms that the current shared calibration benchmark is runnable and no longer resembles the old all-zero state.

## Evidence

- Run artifact:
  - [results.csv](D:/codex/grasp-benchmark/artifacts/runs/20260405_053120_graspvla_track_a_cal_v1_shared_sim/results.csv)
- Aggregate report:
  - [report.md](D:/codex/grasp-benchmark/artifacts/reports/track_a_cal_graspvla_refresh_20260405_v2/report.md)

## Breakdown

| task | trials | success_rate |
| --- | --- | --- |
| `language_conditioned_single_target_pick` | `10` | `1.0` |
| `arbitrary_grasping_common_opaque` | `5` | `0.8` |

## Failed Trial

- `scene_id`: `arbitrary_grasping_common_opaque__opaque_basic__003`
- `object_id`: `power_drill`
- `attempts`: `3`
- `best reported lift_cm`: `4.053`
- `failure_reason`: `Shared success criterion was not met within the Track A step budget.`

## Practical Conclusion

- Current GraspVLA performance on the shared calibration leaderboard is strong but no longer perfect.
- The remaining miss is in `arbitrary_grasping_common_opaque`, which is consistent with the broader picture that geometric common-object grasping is not automatically the strongest case for this RGB closed-loop stack under a shared protocol.
