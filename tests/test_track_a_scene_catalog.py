from __future__ import annotations

import unittest

from grasp_benchmark.config import load_named_config
from grasp_benchmark.runners.graspvla_track_a_sim import build_scene_catalog
from grasp_benchmark.task_specs import expand_task_set


class TrackASceneCatalogTest(unittest.TestCase):
    def test_scene_catalog_covers_all_track_a_cal_trials(self) -> None:
        task_config = load_named_config("tasks", "track_a_cal_v1")
        scene_config = load_named_config("scenes", task_config["scene_catalog"])
        trials = expand_task_set(task_config)

        catalog = build_scene_catalog(trials, scene_config)

        self.assertEqual(len(trials), 15)
        self.assertEqual(set(catalog), {trial.scene_id for trial in trials})
        self.assertEqual(catalog["language_conditioned_single_target_pick__basic__001"].condition, "basic")
        self.assertEqual(catalog["language_conditioned_single_target_pick__distractors_light__003"].condition, "distractors_light")
        self.assertEqual(catalog["arbitrary_grasping_common_opaque__opaque_basic__005"].condition, "opaque_basic")

    def test_track_a_cal_uses_native_assets_without_material_overrides(self) -> None:
        task_config = load_named_config("tasks", "track_a_cal_v1")
        scene_config = load_named_config("scenes", task_config["scene_catalog"])
        trials = expand_task_set(task_config)

        catalog = build_scene_catalog(trials, scene_config)

        for recipe in catalog.values():
            for scene_object in recipe.objects:
                self.assertFalse(scene_object.material_override)
        opaque_recipe = catalog["arbitrary_grasping_common_opaque__opaque_basic__001"]
        self.assertEqual(len(opaque_recipe.success_instance_names), 4)
        self.assertEqual(opaque_recipe.objects[0].object_id, "banana")

    def test_scene_catalog_covers_all_track_a_trials(self) -> None:
        method_config = load_named_config("methods", "graspvla")
        task_config = load_named_config("tasks", "track_a_v1")
        scene_config = load_named_config("scenes", method_config["sim"]["scene_catalog"])
        trials = expand_task_set(task_config)

        catalog = build_scene_catalog(trials, scene_config)

        self.assertEqual(len(trials), 29)
        self.assertEqual(set(catalog), {trial.scene_id for trial in trials})
        self.assertEqual(catalog["language_conditioned_single_target_pick__basic__001"].condition, "basic")
        self.assertEqual(catalog["arbitrary_grasping_transparent__transparent__004"].condition, "transparent")

    def test_scene_catalog_covers_all_track_a_v2_trials(self) -> None:
        method_config = load_named_config("methods", "graspvla")
        task_config = load_named_config("tasks", "track_a_v2")
        scene_config = load_named_config("scenes", task_config["scene_catalog"])
        trials = expand_task_set(task_config)

        catalog = build_scene_catalog(trials, scene_config)

        self.assertEqual(len(trials), 34)
        self.assertEqual(set(catalog), {trial.scene_id for trial in trials})
        self.assertEqual(catalog["arbitrary_grasping_common_opaque__opaque__005"].condition, "opaque")
        self.assertEqual(len(catalog["arbitrary_grasping_common_opaque__opaque__001"].success_instance_names), 4)

    def test_track_a_v2_scene_catalog_covers_common_opaque_group(self) -> None:
        method_config = load_named_config("methods", "graspvla")
        task_config = load_named_config("tasks", "track_a_v2")
        scene_config = load_named_config("scenes", task_config["scene_catalog"])
        trials = expand_task_set(task_config)

        catalog = build_scene_catalog(trials, scene_config)

        self.assertEqual(len(trials), 34)
        self.assertEqual(set(catalog), {trial.scene_id for trial in trials})
        self.assertEqual(catalog["arbitrary_grasping_common_opaque__opaque__001"].condition, "opaque")
        self.assertEqual(len(catalog["arbitrary_grasping_common_opaque__opaque__001"].success_instance_names), 4)

    def test_scene_catalog_covers_all_track_a_cal_v2_trials(self) -> None:
        task_config = load_named_config("tasks", "track_a_cal_v2")
        scene_config = load_named_config("scenes", task_config["scene_catalog"])
        trials = expand_task_set(task_config)

        catalog = build_scene_catalog(trials, scene_config)

        self.assertEqual(len(trials), 60)
        self.assertEqual(set(catalog), {trial.scene_id for trial in trials})
        recipe = catalog["language_conditioned_single_target_pick__basic__001__r01"]
        self.assertEqual(recipe.scene_recipe_id, "language_conditioned_single_target_pick__basic__001")
        self.assertEqual(recipe.replicate_index, 1)
        self.assertGreater(recipe.seed, 0)

    def test_scene_catalog_covers_all_track_a_stress_v2_trials(self) -> None:
        task_config = load_named_config("tasks", "track_a_stress_v2")
        scene_config = load_named_config("scenes", task_config["scene_catalog"])
        trials = expand_task_set(task_config)

        catalog = build_scene_catalog(trials, scene_config)

        self.assertEqual(len(trials), 64)
        self.assertEqual(set(catalog), {trial.scene_id for trial in trials})
        opaque_recipe = catalog["arbitrary_grasping_common_opaque__opaque_clutter__001__r01"]
        self.assertEqual(len(opaque_recipe.success_instance_names), 4)
        self.assertEqual(opaque_recipe.objects[0].object_id, "banana")
        transparent_recipe = catalog["arbitrary_grasping_transparent__transparent_pose_bank__001__r06"]
        self.assertEqual(transparent_recipe.condition, "transparent_pose_bank")
        self.assertEqual(len(transparent_recipe.success_instance_names), 4)

    def test_track_a_cal_v2_scene_catalog_preserves_trial_seed_and_condition(self) -> None:
        task_config = load_named_config("tasks", "track_a_cal_v2")
        scene_config = load_named_config("scenes", task_config["scene_catalog"])
        trials = expand_task_set(task_config)

        catalog = build_scene_catalog(trials, scene_config)

        self.assertEqual(catalog["language_conditioned_single_target_pick__basic__001__r01"].seed, trials[0].seed)
        self.assertEqual(catalog["arbitrary_grasping_common_opaque__opaque_basic__001__r01"].condition, "opaque_basic")


if __name__ == "__main__":
    unittest.main()
