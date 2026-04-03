from __future__ import annotations

import unittest

from grasp_benchmark.adapters import build_adapter
from grasp_benchmark.config import load_named_config
from grasp_benchmark.run.worker import _shared_protocol


class WorkerMetadataTest(unittest.TestCase):
    def test_shared_protocol_includes_track_a_freeze_fields(self) -> None:
        sensor_config = load_named_config("sensors", "track_a_dual_realsense")
        protocol = _shared_protocol(sensor_config)
        self.assertEqual(protocol["track"], "track_a")
        self.assertEqual(protocol["control_mode"], "blocking")
        self.assertEqual(protocol["scene_edit_policy"], "shared_only")
        self.assertEqual(protocol["embodiment"]["robot"], "franka")
        self.assertEqual(protocol["logging_contract"], "episode_result_v1")

    def test_graspvla_adapter_exposes_track_a_input_policy(self) -> None:
        method_config = load_named_config("methods", "graspvla")
        sensor_config = load_named_config("sensors", "track_a_dual_realsense")
        adapter = build_adapter("graspvla", method_config, sensor_config)
        policy = adapter.input_policy()
        self.assertEqual(policy["observation_contract"], "shared_observation")
        self.assertIn("rgb_front", policy["consumes"])
        self.assertIn("depth_front", policy["ignores"])
        self.assertEqual(policy["scene_edit_policy"], "shared_only")

    def test_cgn_adapter_exposes_shared_track_a_input_policy(self) -> None:
        method_config = load_named_config("methods", "cgn")
        sensor_config = load_named_config("sensors", "track_a_dual_realsense")
        adapter = build_adapter("cgn", method_config, sensor_config)
        policy = adapter.input_policy()
        self.assertEqual(policy["observation_contract"], "shared_observation")
        self.assertIn("depth_front", policy["consumes"])
        self.assertIn("rgb_side", policy["ignores"])
        self.assertEqual(policy["scene_edit_policy"], "shared_only")


if __name__ == "__main__":
    unittest.main()
