# GraspVLA Protocol Probe v2

## Headline

- Latest formal `Track A-Cal` reference remains `14/15`.
- On the fixed `protocol_probe_v2` suite, the shared baseline reaches `24/24`.
- The weakest single-factor variant is `P1_front_only_duplicate` at `14/24`.
- The largest measured drop versus baseline is `P1_front_only_duplicate / arbitrary_grasping_transparent / transparent_pose_bank` = `-1.0`.

## Variant Summary

| variant | view_mode | attempt_budget | lift_threshold_cm | hold_steps | camera_jitter_mode | trials | successes | success_rate | mean_attempts | mean_inference_ms | mean_cycle_time_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0_shared_baseline | dual | 3 | 15.0 | 10 | none | 24 | 24 | 1.0 | 1.1667 | 224.1416 | 17.3062 |
| P1_front_only_duplicate | front_only_duplicate | 3 | 15.0 | 10 | none | 24 | 14 | 0.5833 | 2.0417 | 226.6475 | 53.6984 |
| P2_attempt_budget_1 | dual | 1 | 15.0 | 10 | none | 24 | 20 | 0.8333 | 1.0 | 229.8696 | 15.9466 |
| P3_relaxed_success | dual | 3 | 10.0 | 1 | none | 24 | 24 | 1.0 | 1.0 | 222.2205 | 10.3183 |
| P4_camera_jitter_low | dual | 3 | 15.0 | 10 | low | 24 | 24 | 1.0 | 1.125 | 227.9041 | 16.1334 |

## By Task

| variant | task | trials | successes | success_rate | mean_attempts |
| --- | --- | --- | --- | --- | --- |
| P0_shared_baseline | arbitrary_grasping_transparent | 8 | 8 | 1.0 | 1.25 |
| P0_shared_baseline | language_conditioned_single_target_pick | 16 | 16 | 1.0 | 1.125 |
| P1_front_only_duplicate | arbitrary_grasping_transparent | 8 | 0 | 0.0 | 3.0 |
| P1_front_only_duplicate | language_conditioned_single_target_pick | 16 | 14 | 0.875 | 1.5625 |
| P2_attempt_budget_1 | arbitrary_grasping_transparent | 8 | 6 | 0.75 | 1.0 |
| P2_attempt_budget_1 | language_conditioned_single_target_pick | 16 | 14 | 0.875 | 1.0 |
| P3_relaxed_success | arbitrary_grasping_transparent | 8 | 8 | 1.0 | 1.0 |
| P3_relaxed_success | language_conditioned_single_target_pick | 16 | 16 | 1.0 | 1.0 |
| P4_camera_jitter_low | arbitrary_grasping_transparent | 8 | 8 | 1.0 | 1.125 |
| P4_camera_jitter_low | language_conditioned_single_target_pick | 16 | 16 | 1.0 | 1.125 |

## By Condition

| variant | task | condition | trials | successes | success_rate |
| --- | --- | --- | --- | --- | --- |
| P0_shared_baseline | arbitrary_grasping_transparent | transparent_pose_bank | 8 | 8 | 1.0 |
| P0_shared_baseline | language_conditioned_single_target_pick | basic | 8 | 8 | 1.0 |
| P0_shared_baseline | language_conditioned_single_target_pick | distractors_light | 8 | 8 | 1.0 |
| P1_front_only_duplicate | arbitrary_grasping_transparent | transparent_pose_bank | 8 | 0 | 0.0 |
| P1_front_only_duplicate | language_conditioned_single_target_pick | basic | 8 | 8 | 1.0 |
| P1_front_only_duplicate | language_conditioned_single_target_pick | distractors_light | 8 | 6 | 0.75 |
| P2_attempt_budget_1 | arbitrary_grasping_transparent | transparent_pose_bank | 8 | 6 | 0.75 |
| P2_attempt_budget_1 | language_conditioned_single_target_pick | basic | 8 | 8 | 1.0 |
| P2_attempt_budget_1 | language_conditioned_single_target_pick | distractors_light | 8 | 6 | 0.75 |
| P3_relaxed_success | arbitrary_grasping_transparent | transparent_pose_bank | 8 | 8 | 1.0 |
| P3_relaxed_success | language_conditioned_single_target_pick | basic | 8 | 8 | 1.0 |
| P3_relaxed_success | language_conditioned_single_target_pick | distractors_light | 8 | 8 | 1.0 |
| P4_camera_jitter_low | arbitrary_grasping_transparent | transparent_pose_bank | 8 | 8 | 1.0 |
| P4_camera_jitter_low | language_conditioned_single_target_pick | basic | 8 | 8 | 1.0 |
| P4_camera_jitter_low | language_conditioned_single_target_pick | distractors_light | 8 | 8 | 1.0 |

## Delta vs Shared Baseline

| variant | task | condition | baseline_success_rate | variant_success_rate | success_rate_delta | baseline_mean_attempts | variant_mean_attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1_front_only_duplicate | arbitrary_grasping_transparent | transparent_pose_bank | 1.0 | 0.0 | -1.0 | 1.25 | 3.0 |
| P1_front_only_duplicate | language_conditioned_single_target_pick | basic | 1.0 | 1.0 | 0.0 | 1.0 | 1.5 |
| P1_front_only_duplicate | language_conditioned_single_target_pick | distractors_light | 1.0 | 0.75 | -0.25 | 1.25 | 1.625 |
| P2_attempt_budget_1 | arbitrary_grasping_transparent | transparent_pose_bank | 1.0 | 0.75 | -0.25 | 1.25 | 1.0 |
| P2_attempt_budget_1 | language_conditioned_single_target_pick | basic | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| P2_attempt_budget_1 | language_conditioned_single_target_pick | distractors_light | 1.0 | 0.75 | -0.25 | 1.25 | 1.0 |
| P3_relaxed_success | arbitrary_grasping_transparent | transparent_pose_bank | 1.0 | 1.0 | 0.0 | 1.25 | 1.0 |
| P3_relaxed_success | language_conditioned_single_target_pick | basic | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| P3_relaxed_success | language_conditioned_single_target_pick | distractors_light | 1.0 | 1.0 | 0.0 | 1.25 | 1.0 |
| P4_camera_jitter_low | arbitrary_grasping_transparent | transparent_pose_bank | 1.0 | 1.0 | 0.0 | 1.25 | 1.125 |
| P4_camera_jitter_low | language_conditioned_single_target_pick | basic | 1.0 | 1.0 | 0.0 | 1.0 | 1.125 |
| P4_camera_jitter_low | language_conditioned_single_target_pick | distractors_light | 1.0 | 1.0 | 0.0 | 1.25 | 1.125 |

## Factor Deltas

| factor | variant | baseline_success_rate | variant_success_rate | success_rate_delta |
| --- | --- | --- | --- | --- |
| view_mode_effect | P1_front_only_duplicate | 1.0 | 0.5833 | -0.4167 |
| attempt_budget_effect | P2_attempt_budget_1 | 1.0 | 0.8333 | -0.1667 |
| success_rule_effect | P3_relaxed_success | 1.0 | 1.0 | 0.0 |
| camera_jitter_effect | P4_camera_jitter_low | 1.0 | 1.0 | 0.0 |

_Generated under `20260412_080241_graspvla_protocol_probe_v2`._
