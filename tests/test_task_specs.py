from __future__ import annotations

import unittest

from grasp_benchmark.config import load_named_config
from grasp_benchmark.task_specs import expand_task_set


class TaskSpecTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
