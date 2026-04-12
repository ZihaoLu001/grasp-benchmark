from __future__ import annotations

import unittest

from grasp_benchmark.config import load_named_config
from grasp_benchmark.task_specs import expand_task_set


class TaskSpecTest(unittest.TestCase):
    def test_expand_track_a_cal_v1_creates_15_trials(self) -> None:
        task_config = load_named_config("tasks", "track_a_cal_v1")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 15)
        self.assertEqual(task_config["scene_catalog"], "graspvla_track_a_playground_cal_v1")
        self.assertEqual(trials[0].track, "track_a_cal")
        self.assertEqual(trials[0].task, "language_conditioned_single_target_pick")
        self.assertEqual(trials[0].condition, "basic")
        self.assertEqual(trials[4].object_id, "watermelon")
        self.assertEqual(trials[-1].task, "arbitrary_grasping_common_opaque")
        self.assertEqual(trials[-1].condition, "opaque_basic")

    def test_expand_task_set_uses_catalog_and_conditions(self) -> None:
        task_config = load_named_config("tasks", "track_a_v1")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 29)
        self.assertEqual(trials[0].track, "track_a")
        self.assertEqual(trials[0].task, "language_conditioned_single_target_pick")
        self.assertEqual(trials[0].condition, "basic")
        self.assertIn("pick up", trials[0].instruction)
        self.assertEqual(trials[-1].task, "arbitrary_grasping_transparent")
        self.assertEqual(trials[-1].condition, "transparent")

    def test_expand_task_set_respects_max_trials(self) -> None:
        task_config = load_named_config("tasks", "track_a_v1")
        trials = expand_task_set(task_config, max_trials=3)
        self.assertEqual(len(trials), 3)

    def test_expand_track_a_v2_adds_common_opaque_group(self) -> None:
        task_config = load_named_config("tasks", "track_a_v2")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 34)
        self.assertEqual(task_config["scene_catalog"], "graspvla_track_a_playground_v2")
        self.assertEqual(trials[-1].task, "arbitrary_grasping_common_opaque")
        self.assertEqual(trials[-1].condition, "opaque")
        self.assertEqual(sum(1 for trial in trials if trial.task == "arbitrary_grasping_common_opaque"), 5)

    def test_track_a_v2_adds_common_opaque_trials_without_mutating_v1(self) -> None:
        v1_trials = expand_task_set(load_named_config("tasks", "track_a_v1"))
        v2_trials = expand_task_set(load_named_config("tasks", "track_a_v2"))
        self.assertEqual(len(v1_trials), 29)
        self.assertEqual(len(v2_trials), 34)
        opaque_trials = [trial for trial in v2_trials if trial.task == "arbitrary_grasping_common_opaque"]
        self.assertEqual(len(opaque_trials), 5)
        self.assertTrue(all(trial.condition == "opaque" for trial in opaque_trials))

    def test_track_a_cal_v1_is_independent_from_stress_track(self) -> None:
        cal_trials = expand_task_set(load_named_config("tasks", "track_a_cal_v1"))
        stress_trials = expand_task_set(load_named_config("tasks", "track_a_v2"))
        self.assertEqual(len(cal_trials), 15)
        self.assertEqual(len(stress_trials), 34)
        self.assertTrue(all(trial.object_group == "native_opaque_cal" for trial in cal_trials))
        self.assertTrue(any(trial.object_group == "transparent" for trial in stress_trials))

    def test_expand_track_a_cal_v2_creates_60_trials_with_paired_identifiers(self) -> None:
        task_config = load_named_config("tasks", "track_a_cal_v2")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 60)
        self.assertEqual(trials[0].scene_id, "language_conditioned_single_target_pick__basic__001__r01")
        self.assertEqual(trials[0].scene_recipe_id, "language_conditioned_single_target_pick__basic__001")
        self.assertEqual(trials[0].replicate_index, 1)
        self.assertGreater(trials[0].seed, 0)
        self.assertEqual(trials[-1].task, "arbitrary_grasping_common_opaque")
        self.assertEqual(trials[-1].condition, "opaque_basic")
        self.assertEqual(trials[-1].replicate_index, 4)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "basic"), 20)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "distractors_light"), 20)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "opaque_basic"), 20)

    def test_expand_track_a_stress_v2_creates_64_trials(self) -> None:
        task_config = load_named_config("tasks", "track_a_stress_v2")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 64)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "distractors_heavy"), 20)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "opaque_clutter"), 20)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "transparent_pose_bank"), 24)
        transparent_trials = [trial for trial in trials if trial.task == "arbitrary_grasping_transparent"]
        self.assertEqual(len(transparent_trials), 24)
        self.assertEqual(transparent_trials[0].condition, "transparent_pose_bank")
        self.assertEqual(transparent_trials[-1].replicate_index, 6)

    def test_expand_track_a_cal_v3_creates_90_trials(self) -> None:
        task_config = load_named_config("tasks", "track_a_cal_v3")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 90)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "basic"), 30)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "distractors_light"), 30)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "opaque_basic"), 30)
        self.assertEqual(trials[0].replicate_index, 1)
        self.assertEqual(trials[-1].replicate_index, 6)

    def test_expand_track_a_stress_v3_creates_112_trials(self) -> None:
        task_config = load_named_config("tasks", "track_a_stress_v3")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 112)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "distractors_heavy"), 30)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "occlusion_bank"), 20)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "opaque_clutter"), 30)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "transparent_pose_bank"), 32)
        transparent_trials = [trial for trial in trials if trial.task == "arbitrary_grasping_transparent"]
        self.assertEqual(len(transparent_trials), 32)
        self.assertEqual(transparent_trials[-1].replicate_index, 8)

    def test_protocol_probe_v2_creates_24_trials(self) -> None:
        task_config = load_named_config("tasks", "protocol_probe_v2")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 24)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "basic"), 8)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "distractors_light"), 8)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "transparent_pose_bank"), 8)

    def test_protocol_and_transfer_suite_v1_creates_24_trials(self) -> None:
        task_config = load_named_config("tasks", "protocol_and_transfer_suite_v1")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 24)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "basic"), 8)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "distractors_light"), 8)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "transparent_pose_bank"), 8)

    def test_cgn_bottleneck_v1_creates_24_trials(self) -> None:
        task_config = load_named_config("tasks", "cgn_bottleneck_v1")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 24)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "basic"), 8)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "distractors_light"), 8)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "transparent_pose_bank"), 8)

    def test_track_b_cgn_native_v1_creates_84_trials(self) -> None:
        task_config = load_named_config("tasks", "track_b_cgn_native_v1")
        trials = expand_task_set(task_config)

        self.assertEqual(len(trials), 84)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "basic"), 20)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "distractors_light"), 20)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "opaque_basic"), 20)
        self.assertEqual(sum(1 for trial in trials if trial.condition == "transparent_pose_bank"), 24)
        self.assertEqual(trials[0].track, "track_b_native")


if __name__ == "__main__":
    unittest.main()
