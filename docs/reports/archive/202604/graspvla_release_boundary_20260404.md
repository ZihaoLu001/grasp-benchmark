# GraspVLA Official Boundary And Bottleneck Audit

- parity_status: `reproducibility-limited parity`
- primary_bottleneck: `shared protocol / distribution gap`
- attribution_ran: `True`
- attribution_mode: `gated`
- scene_level_overlap_between_V0_repeat_and_V1_mismatches: `libero_10__task001__seed005, libero_object__task000__seed003`

## Comparison Summary

| comparison | reference_trials | candidate_trials | expected_trials | scene_overlap | mismatches | mismatch_scene_count | mismatch_scene_ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V0_official_runner vs V0_repeat_official_runner | 65 | 65 | 65 | 65 | 3 | 3 | libero_10__task001__seed005, libero_object__task000__seed003, libero_object__task000__seed006 |
| V0_official_runner vs V1_wrapper_official_parity | 65 | 65 | 65 | 65 | 3 | 3 | libero_10__task001__seed005, libero_goal__task001__seed004, libero_object__task000__seed003 |

## Variant Summary

| variant | execution_mode | task_set | trials | successes | success_rate | playground_trials | playground_successes | playground_success_rate | setup_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V0_official_runner | official_aligned_sim | official_alignment_subset | 60 | 58 | 0.9667 | 5 | 0 | 0.0 |  |
| V0_repeat_official_runner | official_aligned_sim | official_alignment_subset | 60 | 59 | 0.9833 | 5 | 0 | 0.0 |  |
| V1_wrapper_official_parity | official_aligned_sim | official_alignment_subset | 60 | 59 | 0.9833 | 5 | 0 | 0.0 |  |
| V2_shared_gripper | official_aligned_sim | official_alignment_subset | 60 | 58 | 0.9667 | 0 | 0 | 0.0 |  |
| V3_shared_success | official_aligned_sim | official_alignment_subset | 60 | 39 | 0.65 | 0 | 0 | 0.0 |  |
| V4_no_method_specific_scene_edits | official_aligned_sim | official_alignment_subset | 0 | 0 | 0.0 | 0 | 0 | 0.0 | RuntimeError: State length mismatch for libero_object task 0 seed 0: env=97 init=110 |
| V5_track_a_cal_distribution | shared_track_a_sim | track_a_cal_v1 | 15 | 14 | 0.9333 | 0 | 0 | 0.0 |  |

## Official Boundary Ledger

| item | status | claim_scope | details |
| --- | --- | --- | --- |
| Track B official LIBERO/playground native run | Supported and stable | Use only as the native-deployment upper bound for the public release, not as the shared benchmark headline result. | Official native full run completed successfully; benchmarks=libero_object, libero_10, libero_goal; LIBERO summary=libero_10: 325/350 = 0.929; libero_goal: 336/350 = 0.960; libero_object: 482/500 = 0.964 |
| official_aligned subset parity | Supported but reproducibility-limited | Use to judge whether our wrapper is implementation-aligned with the public release on an official subset. | Parity status=reproducibility-limited parity; V0a vs V0b mismatches=3; V0a vs V1 mismatches=3; mismatch scene overlap=2. |
| Track A-Cal shared benchmark | Unsupported / not claimable from public release | Keep provisional only; do not use as the final fair benchmark claim until the current shared-protocol bottleneck is explained. | Latest Track A-Cal report still shows GraspVLA at 0/15 under the shared benchmark protocol. |

## Success Delta Table

| transition | factor | from_success_rate | to_success_rate | success_rate_delta | same_distribution | interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| V1_wrapper_official_parity -> V2_shared_gripper | gripper_effect | 0.9833 | 0.9667 | -0.0166 | 1 | nearly_no_effect |
| V2_shared_gripper -> V3_shared_success | success_rule_effect | 0.9667 | 0.65 | -0.3167 | 1 | major_effect |
| V3_shared_success -> V4_no_method_specific_scene_edits | scene_edit_effect | 0.65 | 0.0 | -0.65 | 0 | distribution_shift_candidate |
| V4_no_method_specific_scene_edits -> V5_track_a_cal_distribution | task_distribution_effect | 0.0 | 0.9333 | 0.9333 | 0 | distribution_shift_candidate |

## Audit Conclusion

- Parity conclusion: `reproducibility-limited parity`.
- Interpretation: The wrapper mismatch count is no worse than the official runner's self-repeat drift.
- Primary bottleneck: `shared protocol / distribution gap`.
- Gripper effect: `V1_wrapper_official_parity -> V2_shared_gripper` changes success rate by `-0.0166` and shows nearly no measurable impact.
- Success-rule effect: `V2_shared_gripper -> V3_shared_success` changes success rate by `-0.3167` and shows a major measurable impact.
- Method-specific scene-edit effect: `V3_shared_success -> V4_no_method_specific_scene_edits` changes success rate by `-0.6500` and shows the strongest candidate bottleneck because the distribution changes.
- Task/distribution effect: `V4_no_method_specific_scene_edits -> V5_track_a_cal_distribution` changes success rate by `+0.9333` and shows the strongest candidate bottleneck because the distribution changes.
- See `mismatch_episodes.csv` for the remaining `V0a vs V1` mismatches.
- See `v0_repeat_mismatch_episodes.csv` for the official runner self-repeat baseline mismatches.
