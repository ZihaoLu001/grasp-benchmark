# Track A Compare: GraspVLA vs Contact-GraspNet

## Scope

- Track A shared benchmark
- Parent runs:
  - `20260403_051928_graspvla_track_a_v1_shared_sim`
  - `20260403_094334_cgn_track_a_v1_shared_sim`
- Track B reference:
  - `D:\codex\grasp-benchmark\artifacts\official_sim\20260402_231726_em14_full\summary.json`

## Headline

| Method | Task | Trials | Success Rate | Mean Attempts | Mean Inference (ms) | Mean Cycle Time (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `graspvla` | `language_conditioned_single_target_pick` | 25 | 0.0 | 3.0 | 453.4220 | 146.7363 |
| `graspvla` | `arbitrary_grasping_transparent` | 4 | 0.0 | 3.0 | 445.7128 | 188.9989 |
| `cgn` | `language_conditioned_single_target_pick` | 25 | 0.0 | 3.0 | 0.0 | 67.2280 |
| `cgn` | `arbitrary_grasping_transparent` | 4 | 0.0 | 3.0 | 0.0 | 85.2574 |

## Interpretation

- `Track A` under the frozen shared setting is now complete for both `GraspVLA` and `Contact-GraspNet`.
- Both methods scored `0/29` under this version of `track_a_v1`.
- `GraspVLA` fails at the task level:
  - `Shared success criterion was not met within the Track A step budget.`
- `Contact-GraspNet` now runs end-to-end in the real shared-sim backend and no longer fails in legacy runtime:
  - all `29/29` failures are `grasp_proposal`
  - reason: `Contact-GraspNet returned zero grasp proposals.`
- The latest complete `CGN` batch was executed from the shared runner and fetched back under:
  - `D:\codex\grasp-benchmark\artifacts\runs\20260403_094334_cgn_track_a_v1_shared_sim`
- `Track B` remains only a native reference for `GraspVLA`, not a fair benchmark number:
  - `playground = 0.800`
  - `libero_10 = 0.929`
  - `libero_goal = 0.960`
  - `libero_object = 0.964`

## Notes

- The `GraspVLA` Track A run predates the sharded schema, so I normalized its CSV into the current compare input before aggregation.
- The official compare report is in:
  - `D:\codex\grasp-benchmark\artifacts\reports\track_a_compare_latest\report.md`
  - `D:\codex\grasp-benchmark\artifacts\reports\track_a_compare_graspvla_cgn_latest\report.md`
