from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

import numpy as np

from grasp_benchmark.paths import PROJECT_ROOT
from grasp_benchmark.runners.graspvla_track_a_sim import (
    _eef_pose_from_obs,
    _ensure_playground_imports,
    _patch_playground_franka_config,
)


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
        curobo_src = str(PROJECT_ROOT / "third_party" / "upstreams" / "curobo" / "src")
        original_sys_path = list(__import__("sys").path)
        original_cwd = Path.cwd()
        try:
            with TemporaryDirectory() as tmp:
                playground_root = Path(tmp) / "GraspVLA-playground"
                (playground_root / "third_party" / "robosuite").mkdir(parents=True)
                playground_root.mkdir(exist_ok=True)
                try:
                    __import__("sys").path = [entry for entry in original_sys_path if entry != curobo_src]
                    _ensure_playground_imports(playground_root)
                    self.assertIn(curobo_src, __import__("sys").path)
                finally:
                    __import__("os").chdir(original_cwd)
        finally:
            __import__("sys").path = original_sys_path
            __import__("os").chdir(original_cwd)

    def test_patch_playground_franka_config_rewrites_legacy_asset_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            playground_root = Path(tmp) / "GraspVLA-playground"
            asset_dir = playground_root / "assets" / "franka_with_extended_finger"
            asset_dir.mkdir(parents=True)
            config_path = asset_dir / "franka.yml"
            config_path.write_text(
                "\n".join(
                    [
                        'urdf_path: "/mnt/afs/grasp-sim/yanmi/LIBERO-test/assets/franka_with_extended_finger/franka_with_extended_finger.urdf"',
                        'asset_root_path: "/mnt/afs/grasp-sim/yanmi/LIBERO-test/assets/franka_with_extended_finger"',
                        'collision_spheres: "/mnt/afs/grasp-sim/yanmi/LIBERO-test/assets/franka_with_extended_finger/collision_spheres.yml"',
                    ]
                ),
                encoding="utf-8",
            )

            patched_path = _patch_playground_franka_config(playground_root)

            self.assertEqual(config_path, patched_path)
            patched = config_path.read_text(encoding="utf-8")
            self.assertNotIn("/mnt/afs/grasp-sim/yanmi/LIBERO-test", patched)
            self.assertIn(str(asset_dir / "franka_with_extended_finger.urdf"), patched)
            self.assertIn(str(asset_dir / "collision_spheres.yml"), patched)


if __name__ == "__main__":
    unittest.main()
