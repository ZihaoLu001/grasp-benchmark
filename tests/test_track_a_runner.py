from __future__ import annotations

import unittest

import numpy as np

from grasp_benchmark.runners.graspvla_track_a_sim import _eef_pose_from_obs


class SharedTrackARunnerTest(unittest.TestCase):
    def test_eef_pose_prefers_observation_frame(self) -> None:
        obs = {
            "robot0_eef_pos": np.array([-0.15, 0.01, 0.22], dtype=np.float32),
            "robot0_eef_quat": np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        }

        pose = _eef_pose_from_obs(obs, np)

        self.assertIsNotNone(pose)
        np.testing.assert_allclose(pose[:3], obs["robot0_eef_pos"], atol=1e-6)
        np.testing.assert_allclose(pose[3:], np.zeros(3, dtype=np.float32), atol=1e-6)

    def test_eef_pose_returns_none_when_missing(self) -> None:
        self.assertIsNone(_eef_pose_from_obs({}, np))


if __name__ == "__main__":
    unittest.main()
