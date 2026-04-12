from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.types import Action, EpisodeResult, append_episode_results_csv


class TypesTest(unittest.TestCase):
    def test_action_requires_six_dof_delta(self) -> None:
        action = Action(ee_delta=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), gripper=1)
        self.assertEqual(len(action.ee_delta), 6)

    def test_episode_results_append_csv(self) -> None:
        result = EpisodeResult(
            method="graspvla",
            method_tier="graspvla_official",
            track="track_a",
            execution_mode="shared_track_a_sim",
            task="language_conditioned_single_target_pick",
            scene_id="scene_001",
            scene_recipe_id="scene_001",
            object_id="mug_001",
            object_group="ycb_core",
            condition="basic",
            instruction="pick up the mug",
            sensor_stack="dual_fixed_realsense_rgbd",
            attempts=1,
            success=True,
            lift_cm=20.0,
            hold_s=2.5,
            spl=1.0,
            inference_ms=123.0,
            cycle_time_s=4.2,
            failure_stage="",
            failure_reason="",
            collision=False,
            video_path="",
            node="em14",
            commit="deadbeef",
            replicate_index=2,
            seed=12345,
            parent_run_id="parent_001",
            shard_id="shard_000",
            gpu_id="0",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "results.csv"
            append_episode_results_csv(path, [result])
            text = path.read_text(encoding="utf-8")
            self.assertIn("graspvla", text)
            self.assertIn("scene_001", text)
            self.assertIn("shared_track_a_sim", text)
            self.assertIn("parent_001", text)
            self.assertIn("shard_000", text)
            self.assertIn("12345", text)
            self.assertIn(",0", text)


if __name__ == "__main__":
    unittest.main()
