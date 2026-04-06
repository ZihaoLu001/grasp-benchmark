from __future__ import annotations

import unittest

from grasp_benchmark.config import load_named_config
from grasp_benchmark.task_specs import expand_task_set


class BoundaryProbeConfigTest(unittest.TestCase):
    def test_boundary_probe_task_set_expands_deterministically(self) -> None:
        task_config = load_named_config("tasks", "graspvla_boundary_probe_v1")
        trials = expand_task_set(task_config)
        self.assertEqual(len(trials), 28)
        self.assertEqual(trials[0].scene_id, "language_conditioned_single_target_pick__basic__001")
        self.assertEqual(trials[-1].scene_id, "arbitrary_grasping_transparent__transparent__004")


if __name__ == "__main__":
    unittest.main()
