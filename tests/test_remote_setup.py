from __future__ import annotations

import unittest

from grasp_benchmark.config import load_named_config
from grasp_benchmark.remote_setup import build_method_install_script


class RemoteSetupTest(unittest.TestCase):
    def test_graspvla_install_script_contains_requirements_install(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "graspvla")
        script, notes = build_method_install_script(cluster_config, method_config, "graspvla")
        self.assertIn("GraspVLA/requirements.txt", script)
        self.assertEqual(notes, [])

    def test_anygrasp_install_script_emits_manual_notes(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "anygrasp")
        script, notes = build_method_install_script(cluster_config, method_config, "anygrasp")
        self.assertIn("GroundingDINO", script)
        self.assertIn('export CUDA_VISIBLE_DEVICES=""', script)
        self.assertIn("gsnet.so", script)
        self.assertTrue(notes)


if __name__ == "__main__":
    unittest.main()
