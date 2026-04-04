# GraspVLA Official Boundary And Bottleneck Audit

- parity_status: `parity failed`
- primary_bottleneck: `wrapper implementation gap`
- attribution_ran: `False`
- scene_level_overlap_between_V0_repeat_and_V1_mismatches: `libero_goal__task001__seed002`

## Comparison Summary

| comparison | reference_trials | candidate_trials | expected_trials | scene_overlap | mismatches | mismatch_scene_count | mismatch_scene_ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V0_official_runner vs V0_repeat_official_runner | 65 | 65 | 65 | 65 | 2 | 2 | libero_10__task001__seed004, libero_goal__task001__seed002 |
| V0_official_runner vs V1_wrapper_official_parity | 65 | 65 | 65 | 65 | 3 | 3 | libero_goal__task001__seed002, libero_goal__task001__seed005, libero_object__task000__seed007 |

## Variant Summary

| variant | execution_mode | task_set | trials | successes | success_rate | playground_trials | playground_successes | playground_success_rate | setup_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V0_official_runner | official_aligned_sim | official_alignment_subset | 60 | 59 | 0.9833 | 5 | 0 | 0.0 |  |
| V0_repeat_official_runner | official_aligned_sim | official_alignment_subset | 60 | 59 | 0.9833 | 5 | 0 | 0.0 |  |
| V1_wrapper_official_parity | official_aligned_sim | official_alignment_subset | 60 | 58 | 0.9667 | 5 | 0 | 0.0 |  |

## Official Boundary Ledger

| item | status | claim_scope | details |
| --- | --- | --- | --- |
| Track B official LIBERO/playground native run | Supported and stable | Use only as the native-deployment upper bound for the public release, not as the shared benchmark headline result. | Official native full run completed successfully; benchmarks=libero_object, libero_10, libero_goal; LIBERO summary=libero_10: 325/350 = 0.929; libero_goal: 336/350 = 0.960; libero_object: 482/500 = 0.964 |
| official_aligned subset parity | Unsupported / not claimable from public release | Use to judge whether our wrapper is implementation-aligned with the public release on an official subset. | Parity status=parity failed; V0a vs V0b mismatches=2; V0a vs V1 mismatches=3; mismatch scene overlap=1. |
| Track A-Cal shared benchmark | Unsupported / not claimable from public release | Keep provisional only; do not use as the final fair benchmark claim until the current shared-protocol bottleneck is explained. | Latest Track A-Cal report still shows GraspVLA at 0/15 under the shared benchmark protocol. |

## Success Delta Table

_V2-V5 were not run because parity did not pass the dual-threshold gate._

## Audit Conclusion

- Parity conclusion: `parity failed`.
- Interpretation: The wrapper still drifts more than the official runner's self-repeat baseline.
- Primary bottleneck: `wrapper implementation gap`.
- The audit did not run V2-V5, so there is no variable-contribution table yet.
- See `mismatch_episodes.csv` for the remaining `V0a vs V1` mismatches.
- See `v0_repeat_mismatch_episodes.csv` for the official runner self-repeat baseline mismatches.
