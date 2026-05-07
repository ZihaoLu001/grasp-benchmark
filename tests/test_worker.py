from __future__ import annotations

import unittest

from grasp_benchmark.adapters import build_adapter
from grasp_benchmark.config import load_named_config
from grasp_benchmark.run.worker import (
    _is_official_aligned_execution_mode,
    _official_setup_failure_results,
    _is_shared_track_a_execution_mode,
    _shared_protocol,
)


class WorkerMetadataTest(unittest.TestCase):
    def test_track_a_diag_modes_route_to_shared_backend(self) -> None:
        self.assertTrue(_is_shared_track_a_execution_mode("shared_track_a_sim"))
        self.assertTrue(_is_shared_track_a_execution_mode("track_a_diag_a0"))
        self.assertFalse(_is_shared_track_a_execution_mode("integration_fixture"))
        self.assertFalse(_is_shared_track_a_execution_mode("official_aligned_sim"))

    def test_official_aligned_mode_routes_separately(self) -> None:
        self.assertTrue(_is_official_aligned_execution_mode("official_aligned_sim"))
        self.assertFalse(_is_official_aligned_execution_mode("shared_track_a_sim"))

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

    def test_official_aligned_setup_failure_preserves_expected_trial_count(self) -> None:
        results = _official_setup_failure_results(
            adapter_name="graspvla",
            method_tier="graspvla_official",
            sensor_stack="official_aligned",
            benchmarks=["libero_object", "libero_10"],
            tasks_per_benchmark=2,
            seeds=[0, 1, 2],
            playground_seed_list=[7, 8],
            run_playground_sanity=True,
            node="node-a",
            commit="deadbeef",
            execution_mode="official_aligned_sim",
            exc=RuntimeError("bootstrap failed"),
            parent_run_id="parent",
            shard_id="shard_000",
            gpu_id="0",
        )

        self.assertEqual(len(results), 14)
        self.assertTrue(all(not result.success for result in results))
        self.assertEqual({result.failure_stage for result in results}, {"adapter_setup"})
        self.assertIn("bootstrap failed", results[0].failure_reason)
        self.assertEqual(results[0].parent_run_id, "parent")


if __name__ == "__main__":
    unittest.main()
