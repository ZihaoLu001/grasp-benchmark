from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from grasp_benchmark.paths import PROJECT_ROOT
from grasp_benchmark.runners.graspvla_track_a_sim import _eef_pose_from_obs, _ensure_playground_imports


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

    def test_ensure_playground_imports_adds_curobo_src(self) -> None:
        playground_root = PROJECT_ROOT / "third_party" / "upstreams" / "GraspVLA-playground"
        curobo_src = str(PROJECT_ROOT / "third_party" / "upstreams" / "curobo" / "src")
        original_sys_path = list(__import__("sys").path)
        try:
            __import__("sys").path = [entry for entry in original_sys_path if entry != curobo_src]
            _ensure_playground_imports(Path(playground_root))
            self.assertIn(curobo_src, __import__("sys").path)
        finally:
            __import__("sys").path = original_sys_path


if __name__ == "__main__":
    unittest.main()
