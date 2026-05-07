from __future__ import annotations

import unittest

import numpy as np
import transforms3d as t3d

from grasp_benchmark.adapters.base import AdapterExecutionError
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
    def _final_rotation_after_plan(self, start_euler: list[float], plan) -> np.ndarray:
        rotation = np.asarray(t3d.euler.euler2mat(*start_euler, axes="sxyz"), dtype=np.float64)
        for action in plan:
            delta_rotation = np.asarray(t3d.euler.euler2mat(*action.ee_delta[3:6], axes="sxyz"), dtype=np.float64)
            rotation = delta_rotation @ rotation
        return rotation

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

    def test_rejects_full_grasp_pose_below_workspace_floor(self) -> None:
        obs = _observation()
        grasp = np.eye(4, dtype=np.float32)
        grasp[2, 3] = -0.05
        with self.assertRaises(AdapterExecutionError) as exc_info:
            build_shared_pick_plan(
                obs,
                np,
                translation_cam=grasp[:3, 3],
                grasp_matrix_cam=grasp,
                planner_config={
                    "reject_below_table_grasps": True,
                    "grasp_min_z_m": 0.02,
                    "approach_clearance_m": 0.08,
                    "lift_height_m": 0.18,
                    "chunk_size_m": 0.02,
                    "close_steps": 2,
                },
            )
        self.assertEqual(exc_info.exception.failure_stage, "planner_failure")

    def test_allows_full_grasp_pose_within_floor_tolerance(self) -> None:
        obs = _observation()
        grasp = np.eye(4, dtype=np.float32)
        grasp[2, 3] = 0.0198
        actions, debug = build_shared_pick_plan(
            obs,
            np,
            translation_cam=grasp[:3, 3],
            grasp_matrix_cam=grasp,
            planner_config={
                "reject_below_table_grasps": True,
                "grasp_min_z_m": 0.02,
                "grasp_min_z_tolerance_m": 0.002,
                "approach_clearance_m": 0.08,
                "lift_height_m": 0.18,
                "chunk_size_m": 0.02,
                "close_steps": 2,
            },
            return_debug=True,
        )

        self.assertGreater(len(actions), 0)
        self.assertAlmostEqual(debug["target_base"][2], 0.0198, places=4)

    def test_grasp_pose_rotation_chunks_compose_to_absolute_goal(self) -> None:
        obs = _observation()
        grasp = np.eye(4, dtype=np.float32)
        grasp[:3, :3] = np.asarray(t3d.euler.euler2mat(0.45, -0.65, 1.05, axes="sxyz"), dtype=np.float32)
        grasp[:3, 3] = np.asarray([0.05, -0.02, 0.12], dtype=np.float32)

        plan, debug = build_shared_pick_plan(
            obs,
            np,
            translation_cam=grasp[:3, 3],
            grasp_matrix_cam=grasp,
            planner_config={
                "reject_below_table_grasps": True,
                "grasp_min_z_m": 0.02,
                "approach_clearance_m": 0.08,
                "lift_height_m": 0.18,
                "chunk_size_m": 0.02,
                "chunk_size_rad": 0.12,
                "close_steps": 2,
            },
            return_debug=True,
        )

        final_rotation = self._final_rotation_after_plan(obs.proprio["state"][3:6], plan)
        np.testing.assert_allclose(final_rotation, grasp[:3, :3], atol=2e-5)
        self.assertEqual(debug["planner_mode"], "grasp_pose")
        self.assertGreater(sum(1 for action in plan if any(abs(item) > 1e-8 for item in action.ee_delta[3:6])), 1)

    def test_grasp_frame_to_tcp_transform_is_explicitly_applied(self) -> None:
        obs = _observation()
        grasp = np.eye(4, dtype=np.float32)
        grasp[:3, 3] = np.asarray([0.05, -0.02, 0.12], dtype=np.float32)
        grasp_frame_to_tcp = np.eye(4, dtype=np.float32)
        grasp_frame_to_tcp[0, 3] = 0.03

        _plan, debug = build_shared_pick_plan(
            obs,
            np,
            translation_cam=grasp[:3, 3],
            grasp_matrix_cam=grasp,
            planner_config={
                "grasp_frame_to_tcp_matrix": grasp_frame_to_tcp.tolist(),
                "grasp_frame_to_tcp_status": "unit_test_offset",
                "reject_below_table_grasps": True,
                "grasp_min_z_m": 0.02,
                "approach_clearance_m": 0.08,
                "lift_height_m": 0.18,
                "chunk_size_m": 0.02,
                "close_steps": 2,
            },
            return_debug=True,
        )

        self.assertEqual(debug["grasp_frame_to_tcp_status"], "unit_test_offset")
        self.assertAlmostEqual(debug["raw_grasp_translation_cam"][0], 0.05, places=5)
        self.assertAlmostEqual(debug["translation_cam"][0], 0.08, places=5)
        self.assertAlmostEqual(debug["target_base"][0], 0.68, places=5)

    def test_post_lift_hold_keeps_gripper_closed(self) -> None:
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
                "post_lift_hold_steps": 3,
            },
            return_debug=True,
        )

        self.assertEqual(debug["post_lift_hold_steps"], 3)
        self.assertEqual([action.gripper for action in plan[-3:]], [-1, -1, -1])
        for action in plan[-3:]:
            self.assertEqual(action.ee_delta, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
