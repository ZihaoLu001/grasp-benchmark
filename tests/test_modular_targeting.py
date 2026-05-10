from __future__ import annotations

import unittest

from grasp_benchmark.adapters.modular_components import is_target_specific_task, target_specific_labels


class ModularTargetingTest(unittest.TestCase):
    def test_task_oriented_prompts_are_target_specific(self) -> None:
        self.assertTrue(is_target_specific_task("mug_handle_grasp"))
        self.assertTrue(is_target_specific_task("avoid_inside_cup"))
        self.assertTrue(is_target_specific_task("power_drill_handle_grasp"))

    def test_arbitrary_grasping_prompts_are_not_target_specific(self) -> None:
        self.assertFalse(is_target_specific_task("arbitrary_grasping_common_opaque"))
        self.assertFalse(is_target_specific_task("arbitrary_grasping_transparent"))

    def test_task_oriented_labels_include_instruction_object(self) -> None:
        labels = target_specific_labels(
            {"object_id": "clear_plastic_cup", "object_label": "clear plastic cup"},
            "pick up the mug by the handle",
        )

        self.assertIn("clear plastic cup", labels)
        self.assertIn("mug", labels)
        self.assertIn("cup", labels)

    def test_power_drill_labels_include_drill_synonym(self) -> None:
        labels = target_specific_labels(
            {"object_id": "power_drill", "object_label": "power drill"},
            "pick up the power drill by the handle",
        )

        self.assertIn("power drill", labels)
        self.assertIn("drill", labels)


if __name__ == "__main__":
    unittest.main()
