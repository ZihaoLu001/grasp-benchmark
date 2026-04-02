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

    def test_graspvla_playground_install_script_contains_official_setup_steps(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "graspvla")
        script, _ = build_method_install_script(
            cluster_config,
            method_config,
            "graspvla",
            include_playground=True,
        )
        self.assertIn("conda install -y -c conda-forge ffmpeg", script)
        self.assertIn("hydra-core==1.2.0", script)
        self.assertNotIn("third_party/upstreams/curobo", script)
        self.assertNotIn("PATCHED_FRANKA_YAML", script)

    def test_graspvla_playground_install_script_emits_separate_env_note(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "graspvla")
        _, notes = build_method_install_script(
            cluster_config,
            method_config,
            "graspvla",
            include_playground=True,
        )
        self.assertTrue(notes)
        self.assertIn("prepare_graspvla_playground", notes[0])

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
