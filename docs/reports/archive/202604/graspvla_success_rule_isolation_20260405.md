# GraspVLA Success-Rule Isolation Audit

## Headline

- This audit isolates the shared success rule on the official scene-edit-compatible subset under the same shared-like embodiment and no method-specific scene edits.
- `env_done -> lift10_hold1` changes success rate by `-0.0500`.
- `lift10_hold1 -> lift15_hold1` changes success rate by `+0.0000`.
- `lift15_hold1 -> lift15_hold10` changes success rate by `+0.0500`.
- On this compatible subset, the success-rule subcomponents are all small and close to the run-to-run noise floor, so no single subcomponent should be over-interpreted from one run.

## Compatible Official Subset

| benchmark | task_id | task_name | instruction |
| --- | --- | --- | --- |
| libero_goal | 1 | put_the_bowl_on_the_stove | pick up bowl |
| libero_goal | 2 | put_the_wine_bottle_on_top_of_the_cabinet | pick up wine bottle |

## Variant Summary

| variant | success_mode | lift_threshold_cm | hold_steps | trials | successes | success_rate |
| --- | --- | --- | --- | --- | --- | --- |
| S0_env_done | env_done |  |  | 20 | 20 | 1.0 |
| S1_lift10_hold1 | shared_lift_hold | 10.0 | 1 | 20 | 19 | 0.95 |
| S2_lift15_hold1 | shared_lift_hold | 15.0 | 1 | 20 | 19 | 0.95 |
| S3_lift15_hold10 | shared_lift_hold | 15.0 | 10 | 20 | 20 | 1.0 |

## Success-Rule Delta Table

| transition | factor | from_success_rate | to_success_rate | success_rate_delta |
| --- | --- | --- | --- | --- |
| S0_env_done -> S1_lift10_hold1 | goal_vs_minimal_lift_rule | 1.0 | 0.95 | -0.05 |
| S1_lift10_hold1 -> S2_lift15_hold1 | lift_threshold_effect | 0.95 | 0.95 | 0.0 |
| S2_lift15_hold1 -> S3_lift15_hold10 | hold_time_effect | 0.95 | 1.0 | 0.05 |

## Practical Conclusion

- The shared success rule can now be discussed in pieces instead of as one opaque change.
- `env_done` and a minimal lift-based rule are close but not identical.
- Within this one run, the observed deltas are small enough that the safest conclusion is: the **shared success rule as a whole matters**, but the compatible-subset audit does not cleanly prove that either the lift threshold or the hold time is the single dominant subcomponent.
- This means the benchmark gap should now be explained primarily through success-rule strictness plus the already-established public-release scene-edit boundary on basket tasks.

_Generated under `20260405_051053_graspvla_success_rule_isolation`._
