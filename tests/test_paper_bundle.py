from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.report.paper_bundle import main as paper_bundle_main


class PaperBundleTest(unittest.TestCase):
    HEADER = (
        "method,method_tier,track,execution_mode,task,scene_id,scene_recipe_id,object_id,object_group,condition,instruction,sensor_stack,"
        "attempts,success,lift_cm,hold_s,spl,inference_ms,cycle_time_s,failure_stage,failure_reason,collision,"
        "video_path,node,commit,replicate_index,seed,parent_run_id,shard_id,gpu_id"
    )

    def _run_bundle(self, root: Path, *extra_args: str) -> Path:
        output_dir = root / "paper_bundle"
        import sys

        argv = sys.argv
        try:
            sys.argv = [
                "paper_bundle.py",
                "--input",
                str(root / "runs"),
                "--output-dir",
                str(output_dir),
                *extra_args,
            ]
            paper_bundle_main()
        finally:
            sys.argv = argv
        return output_dir

    def test_paper_bundle_writes_core_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cal_dir = root / "runs" / "cal_run"
            cal_dir.mkdir(parents=True)
            (cal_dir / "run_metadata.json").write_text(
                json.dumps({"task_set": "track_a_cal_v2", "scene_catalog_name": "graspvla_track_a_playground_cal_v2"}),
                encoding="utf-8",
            )
            (cal_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,scene_recipe_1,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,1,1001,parent_cal,shard_000,0",
                        "cgn,cgn_full_modular,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,scene_recipe_1,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,2,0,0,0.0,0.0,220,10.0,grasp_proposal,none,0,,em14,deadbeef,1,1001,parent_cal,shard_001,0",
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_2,scene_recipe_2,obj_2,native_opaque_cal,distractors_light,pick up the bowl,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,2,1002,parent_cal,shard_000,0",
                        "cgn,cgn_full_modular,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_2,scene_recipe_2,obj_2,native_opaque_cal,distractors_light,pick up the bowl,dual_fixed_realsense_rgbd,3,0,0,0.0,0.0,220,10.0,segmentation_error,mask_empty,0,,em14,deadbeef,2,1002,parent_cal,shard_001,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            stress_dir = root / "runs" / "stress_run"
            stress_dir.mkdir(parents=True)
            (stress_dir / "run_metadata.json").write_text(
                json.dumps({"task_set": "track_a_stress_v2", "scene_catalog_name": "graspvla_track_a_playground_stress_v2"}),
                encoding="utf-8",
            )
            (stress_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_stress,shared_track_a_sim,arbitrary_grasping_transparent,scene_3,scene_recipe_3,obj_3,transparent,transparent_pose_bank,pick up any object,dual_fixed_realsense_rgbd,1,1,18,2.0,1.0,150,5.0,,,0,,em14,deadbeef,1,2001,parent_stress,shard_000,0",
                        "cgn,cgn_full_modular,track_a_stress,shared_track_a_sim,arbitrary_grasping_transparent,scene_3,scene_recipe_3,obj_3,transparent,transparent_pose_bank,pick up any object,dual_fixed_realsense_rgbd,3,0,0,0.0,0.0,250,12.0,task_failure,not_met,0,,em14,deadbeef,1,2001,parent_stress,shard_001,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            native_dir = root / "runs" / "native_run"
            native_dir.mkdir(parents=True)
            (native_dir / "run_metadata.json").write_text(
                json.dumps({"task_set": "track_b_cgn_native_v1", "scene_catalog_name": "graspvla_track_b_cgn_native_v1"}),
                encoding="utf-8",
            )
            (native_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "cgn,cgn_full_modular,track_b_native,shared_track_a_sim,language_conditioned_single_target_pick,scene_4,scene_recipe_4,obj_4,native_opaque_cal,basic,pick up the drill,dual_fixed_realsense_rgbd,3,0,0,0.0,0.0,310,15.0,task_failure,not_met,0,,em10,deadbeef,1,3001,parent_native,shard_000,0",
                        "cgn,cgn_full_modular,track_b_native,shared_track_a_sim,arbitrary_grasping_transparent,scene_5,scene_recipe_5,obj_5,transparent,transparent_pose_bank,pick up any object,dual_fixed_realsense_rgbd,3,0,0,0.0,0.0,320,16.0,task_failure,not_met,0,,em12,deadbeef,1,3002,parent_native,shard_001,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            official_dir = root / "official_sim"
            (official_dir / "playground_data" / "videos").mkdir(parents=True)
            (official_dir / "playground_data" / "videos" / "demo_success.mp4").write_text("", encoding="utf-8")
            summary_path = official_dir / "summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "method": "graspvla",
                        "track": "track_b_native",
                        "statistics_text": "libero_object: 48/50 = 0.96\n",
                    }
                ),
                encoding="utf-8",
            )

            protocol_probe = root / "protocol_probe.json"
            protocol_probe.write_text(json.dumps({"overall": [{"variant": "P0_shared_baseline", "success_rate": 1.0, "mean_attempts": 1.0}]}), encoding="utf-8")
            cgn_bottleneck = root / "cgn_bottleneck.json"
            cgn_bottleneck.write_text(json.dumps({"summary": [{"variant": "D0_shared_cgn", "success_rate": 0.0, "mean_attempts": 3.0}]}), encoding="utf-8")

            output_dir = self._run_bundle(
                root,
                "--track-b-reference",
                str(summary_path),
                "--protocol-probe-summary",
                str(protocol_probe),
                "--cgn-bottleneck-summary",
                str(cgn_bottleneck),
            )

            self.assertTrue((output_dir / "paper_summary.csv").exists())
            self.assertTrue((output_dir / "paper_stats.json").exists())
            self.assertTrue((output_dir / "paper_ready_report.md").exists())
            self.assertTrue((output_dir / "teacher_summary_zh.md").exists())
            self.assertTrue((output_dir / "figures" / "pairwise_stats.csv").exists())
            teacher_text = (output_dir / "teacher_summary_zh.md").read_text(encoding="utf-8")
            self.assertIn("论文主 framing 固定为 `shared benchmark + protocol audit`", teacher_text)
            report_text = (output_dir / "paper_ready_report.md").read_text(encoding="utf-8")
            self.assertIn("## Track A-Cal Shared Benchmark", report_text)
            self.assertIn("## Track B Native Appendix", report_text)
            stats_payload = json.loads((output_dir / "paper_stats.json").read_text(encoding="utf-8"))
            self.assertIn("pairwise_stats", stats_payload)
            self.assertIn("track_b_native_appendix", stats_payload)
            self.assertEqual(stats_payload["pairwise_stats"][0]["paired_scenes"], 2)


if __name__ == "__main__":
    unittest.main()
