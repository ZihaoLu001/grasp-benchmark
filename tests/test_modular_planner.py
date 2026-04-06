from __future__ import annotations

import unittest

import numpy as np

from grasp_benchmark.adapters.modular_components import build_shared_pick_plan
from grasp_benchmark.types import Observation


def _observation() -> Observation:
    return Observation(
        rgb_front=np.zeros((4, 4, 3), dtype=np.uint8),
        rgb_side=np.zeros((4, 4, 3), dtype=np.uint8),
        depth_front=np.zeros((4, 4), dtype=np.float32),
        depth_side=np.zeros((4, 4), dtype=np.float32),
        intrinsics_front={"fx": 100.0, "fy": 100.0, "cx": 2.0, "cy": 2.0},
        intrinsics_side={"fx": 100.0, "fy": 100.0, "cx": 2.0, "cy": 2.0},
        extrinsics_front={"matrix": np.eye(4, dtype=np.float32).tolist()},
        extrinsics_side={"matrix": np.eye(4, dtype=np.float32).tolist()},
        proprio={
            "state": [0.4, 0.0, 0.35, 3.14, 0.0, 0.0, 1.0],
            "history": [[0.4, 0.0, 0.35, 3.14, 0.0, 0.0, 1.0]],
            "robot_base_pose_world": [
                [1.0, 0.0, 0.0, -0.6],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        },
        instruction="pick up banana",
        timestamp=0.0,
    )


class ModularPlannerTest(unittest.TestCase):
    def test_split_hover_waypoints_start_with_vertical_motion(self) -> None:
        obs = _observation()
        plan, debug = build_shared_pick_plan(
            obs,
            np,
            translation_cam=np.asarray([0.05, -0.02, 0.12], dtype=np.float32),
            planner_config={
                "split_hover_waypoints": True,
                "hover_raise_m": 0.1,
                "approach_clearance_m": 0.08,
                "grasp_offset_m": 0.015,
                "lift_height_m": 0.18,
                "chunk_size_m": 0.02,
                "chunk_size_rad": 0.2,
                "close_steps": 2,
            },
            return_debug=True,
        )
        self.assertTrue(debug["split_hover_waypoints"])
        self.assertIn("vertical_hover_pose", debug)
        first = plan[0].ee_delta
        self.assertAlmostEqual(first[0], 0.0, places=5)
        self.assertAlmostEqual(first[1], 0.0, places=5)
        self.assertGreater(first[2], 0.0)

    def test_without_split_hover_waypoints_first_motion_is_diagonal(self) -> None:
        obs = _observation()
        plan, debug = build_shared_pick_plan(
            obs,
            np,
            translation_cam=np.asarray([0.05, -0.02, 0.12], dtype=np.float32),
            planner_config={
                "split_hover_waypoints": False,
                "approach_clearance_m": 0.08,
                "grasp_offset_m": 0.015,
                "lift_height_m": 0.18,
                "chunk_size_m": 0.02,
                "chunk_size_rad": 0.2,
                "close_steps": 2,
            },
            return_debug=True,
        )
        self.assertFalse(debug["split_hover_waypoints"])
        first = plan[0].ee_delta
        self.assertNotAlmostEqual(first[0], 0.0, places=5)

    def test_translation_targets_are_converted_into_robot_base_frame(self) -> None:
        obs = _observation()
        _plan, debug = build_shared_pick_plan(
            obs,
            np,
            translation_cam=np.asarray([0.05, -0.02, 0.12], dtype=np.float32),
            planner_config={
                "split_hover_waypoints": True,
                "hover_raise_m": 0.1,
                "approach_clearance_m": 0.08,
                "grasp_offset_m": 0.015,
                "lift_height_m": 0.18,
                "chunk_size_m": 0.02,
                "chunk_size_rad": 0.2,
                "close_steps": 2,
            },
            return_debug=True,
        )
        self.assertAlmostEqual(debug["target_world"][0], 0.05, places=5)
        self.assertAlmostEqual(debug["target_base"][0], 0.65, places=5)


if __name__ == "__main__":
    unittest.main()
