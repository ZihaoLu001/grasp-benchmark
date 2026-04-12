# CGN Bottleneck v1

## Headline

- `D0 shared CGN` reaches `0/24` on the fixed 24-episode bottleneck suite.
- Replacing detector + mask filtering with simulator GT masks changes success rate by `+0.0000`.
- Replacing the CGN grasp proposal with an oracle top-down centroid grasp changes success rate by `+0.0000` beyond `D1`.
- Relaxing the success rule on the original `D0` logs changes success rate by `+0.0417`.
- After removing both perception and proposal errors, `D2` still reaches only `0/24`, which quantifies the residual planner/execution gap under the shared controller.

## Variant Summary

| variant | segmentation_mode | oracle_grasp_mode | trials | successes | success_rate | mean_attempts | mean_inference_ms | mean_cycle_time_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D0_shared_cgn | shared_detector_segmentation | none | 24 | 0 | 0.0 | 3.0 | 1855.2302 | 257.5682 |
| D1_oracle_grounding | oracle_gt | none | 24 | 0 | 0.0 | 3.0 | 1623.265 | 358.6235 |
| D2_oracle_grasp | oracle_gt | topdown_centroid | 24 | 0 | 0.0 | 3.0 | 0.0597 | 42.3021 |
| D3_relaxed_success_rescore | shared_detector_segmentation | none | 24 | 1 | 0.0417 | 3.0 | 1855.2302 | 257.5682 |

## Delta Table

| transition | factor | from_success_rate | to_success_rate | success_rate_delta |
| --- | --- | --- | --- | --- |
| D0_shared_cgn -> D1_oracle_grounding | grounding_segmentation_effect | 0.0 | 0.0 | 0.0 |
| D1_oracle_grounding -> D2_oracle_grasp | grasp_proposal_effect | 0.0 | 0.0 | 0.0 |
| D0_shared_cgn -> D3_relaxed_success_rescore | strict_success_semantics_effect | 0.0 | 0.0417 | 0.0417 |

## By Task

| variant | task | trials | successes | success_rate | mean_attempts |
| --- | --- | --- | --- | --- | --- |
| D0_shared_cgn | arbitrary_grasping_transparent | 8 | 0 | 0.0 | 3.0 |
| D0_shared_cgn | language_conditioned_single_target_pick | 16 | 0 | 0.0 | 3.0 |
| D1_oracle_grounding | arbitrary_grasping_transparent | 8 | 0 | 0.0 | 3.0 |
| D1_oracle_grounding | language_conditioned_single_target_pick | 16 | 0 | 0.0 | 3.0 |
| D2_oracle_grasp | arbitrary_grasping_transparent | 8 | 0 | 0.0 | 3.0 |
| D2_oracle_grasp | language_conditioned_single_target_pick | 16 | 0 | 0.0 | 3.0 |
| D3_relaxed_success_rescore | arbitrary_grasping_transparent | 8 | 0 | 0.0 | 3.0 |
| D3_relaxed_success_rescore | language_conditioned_single_target_pick | 16 | 1 | 0.0625 | 3.0 |

## Failure Taxonomy

| variant | failure_stage | failure_reason | count |
| --- | --- | --- | --- |
| D0_shared_cgn | grounding_error | AdapterExecutionError: GroundingDINO failed to localize the requested target: carrot | 4 |
| D0_shared_cgn | grounding_error | AdapterExecutionError: GroundingDINO failed to localize the requested target: power drill | 4 |
| D0_shared_cgn | task_failure | Shared modular baseline exhausted its fixed execution plan without meeting the success criterion. | 16 |
| D1_oracle_grounding | task_failure | Shared modular baseline exhausted its fixed execution plan without meeting the success criterion. | 24 |
| D2_oracle_grasp | task_failure | Shared modular baseline exhausted its fixed execution plan without meeting the success criterion. | 24 |
| D3_relaxed_success_rescore | task_failure | relaxed_lift_10cm_not_met | 23 |

_Generated under `20260412_101317_cgn_bottleneck_v1`._
