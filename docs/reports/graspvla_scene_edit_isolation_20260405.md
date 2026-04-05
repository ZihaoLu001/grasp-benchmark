# GraspVLA Scene-Edit Isolation Audit

## Headline

- Basket-linked official tasks are not just harder without scene edits; in the current public release they become incompatible with raw init states.
- A clean scene-edit performance delta can still be measured on the scene-edit-compatible overlap subset.
- On that compatible subset, `V3 -> V4` changes success rate from `0.9500` to `0.9500` (`+0.0000`).
- The latest formal Track A-Cal reference remains `15/15`.

## Compatible Overlap Subset

| benchmark | task_id | task_name | instruction |
| --- | --- | --- | --- |
| libero_goal | 1 | put_the_bowl_on_the_stove | pick up bowl |
| libero_goal | 2 | put_the_wine_bottle_on_top_of_the_cabinet | pick up wine bottle |

These are the official tasks that remain runnable without method-specific scene edits.

## Scene-Edit Compatibility Gate

| benchmark | task_id | task_name | incompatible_seeds |
| --- | --- | --- | --- |
| libero_10 | 0 | LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 |
| libero_10 | 1 | LIVING_ROOM_SCENE2_put_both_the_cream_cheese_box_and_the_butter_in_the_basket | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 |
| libero_object | 0 | pick_up_the_alphabet_soup_and_place_it_in_the_basket | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 |
| libero_object | 1 | pick_up_the_cream_cheese_and_place_it_in_the_basket | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 |

These tasks require the official `process_initial_state` transformation in the current public release, so they cannot be used for a clean no-scene-edit like-for-like ablation.

## Quantified Scene-Edit Effect

- Child audit root: [20260405_042741_graspvla_official_alignment](D:/codex/grasp-benchmark/artifacts/audits/20260405_042741_graspvla_official_alignment)
- Transition: `V3_shared_success -> V4_no_method_specific_scene_edits`
- Success-rate delta: `+0.0000`
- Interpretation: `nearly_no_effect`

## Practical Conclusion

- The public release boundary should be stated in two layers:
  - basket-linked official tasks: scene edits are a compatibility requirement
  - scene-edit-compatible official tasks: scene edits have nearly no measurable performance effect in the current clean `libero_goal` overlap audit
- This means the earlier large result gap should not be explained as a pure scene-edit effect.
- The current best explanation remains:
  - gripper change is small
  - shared success rule matters a lot
  - basket-linked scene edits are a release-boundary constraint
  - latest Track A-Cal is runnable and should no longer be described as all-zero

_Generated from probe and child audit under `20260405_042741_graspvla_scene_edit_isolation`._
