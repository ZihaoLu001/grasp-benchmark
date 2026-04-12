from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.report.aggregate import main as aggregate_main


class ReportTest(unittest.TestCase):
    HEADER = (
        "method,method_tier,track,execution_mode,task,scene_id,scene_recipe_id,object_id,object_group,condition,instruction,sensor_stack,"
        "attempts,success,lift_cm,hold_s,spl,inference_ms,cycle_time_s,failure_stage,failure_reason,collision,"
        "video_path,node,commit,replicate_index,seed,parent_run_id,shard_id,gpu_id"
    )

    def _run_aggregate(self, root: Path, *extra_args: str) -> Path:
        output_dir = root / "report"
        import sys

        argv = sys.argv
        try:
            sys.argv = [
                "aggregate.py",
                "--input",
                str(root / "runs"),
                "--output-dir",
                str(output_dir),
                *extra_args,
            ]
            aggregate_main()
        finally:
            sys.argv = argv
        return output_dir

    def test_aggregate_creates_summary_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,scene_1,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,1,1001,parent_run_a,shard_000,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            output_dir = self._run_aggregate(root)

            self.assertTrue((output_dir / "summary.csv").exists())
            self.assertTrue((output_dir / "report.md").exists())
            self.assertTrue((output_dir / "teacher_summary_zh.md").exists())
            teacher_text = (output_dir / "teacher_summary_zh.md").read_text(encoding="utf-8")
            self.assertIn("# Benchmark 汇总说明", teacher_text)
            self.assertIn("`Track A-Cal` 才是 benchmark setting 下用于公平比较的主榜单。", teacher_text)

    def test_aggregate_writes_track_b_reference_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,scene_1,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,1,1001,parent_run_a,shard_000,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            official_dir = root / "official_sim"
            (official_dir / "playground_data" / "videos").mkdir(parents=True)
            (official_dir / "playground_data" / "videos" / "demo_success.mp4").write_text("", encoding="utf-8")
            (official_dir / "playground_data" / "videos" / "demo_fail.mp4").write_text("", encoding="utf-8")
            summary_path = official_dir / "summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "method": "graspvla",
                        "track": "track_b_native",
                        "statistics_text": "libero_object: 482/500 = 0.964\nlibero_10: 325/350 = 0.929\n",
                    }
                ),
                encoding="utf-8",
            )

            output_dir = self._run_aggregate(root, "--track-b-reference", str(summary_path))

            report_text = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertTrue((output_dir / "track_b_reference.csv").exists())
            self.assertIn("## Track A-Cal Shared Benchmark", report_text)
            self.assertIn("## Track B Native Deployment Reference", report_text)
            self.assertIn("track_b_native", report_text)
            self.assertIn("_No failures recorded._", report_text)

    def test_aggregate_embeds_diagnostic_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,scene_1,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,1,0,0,0.0,0.0,120,4.0,task_failure,not_met,0,,em14,deadbeef,1,1001,parent_run_a,shard_000,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            diagnostic_report = root / "diagnostic_report.md"
            diagnostic_report.write_text(
                "\n".join(
                    [
                        "# GraspVLA Track A Diagnostic Report",
                        "",
                        "## Diagnostic Note",
                        "",
                        "- Gripper mismatch is not the main factor.",
                        "- The gap is not mainly a threshold artifact.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            output_dir = self._run_aggregate(root, "--diagnostic-report", str(diagnostic_report))

            report_text = (output_dir / "report.md").read_text(encoding="utf-8")
            teacher_text = (output_dir / "teacher_summary_zh.md").read_text(encoding="utf-8")
            report_json = (output_dir / "report.json").read_text(encoding="utf-8")
            self.assertIn("## GraspVLA Diagnostic Note", report_text)
            self.assertIn("- Gripper mismatch is not the main factor.", report_text)
            self.assertIn("- The gap is not mainly a threshold artifact.", teacher_text)
            self.assertIn("diagnostic_note", report_json)

    def test_aggregate_embeds_track_a_stress_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,scene_1,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,1,1,18,2.0,1.0,120,4.0,,,0,,em14,deadbeef,1,1001,parent_cal,shard_000,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            stress_report = root / "stress_report.json"
            stress_report.write_text(
                json.dumps(
                    {
                        "summary": [
                            {
                                "track": "track_a",
                                "method": "graspvla",
                                "task": "language_conditioned_single_target_pick",
                                "trials": 25,
                                "success_rate": 0.0,
                                "mean_attempts": 3.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            output_dir = self._run_aggregate(root, "--track-a-stress-reference", str(stress_report))

            report_text = (output_dir / "report.md").read_text(encoding="utf-8")
            teacher_text = (output_dir / "teacher_summary_zh.md").read_text(encoding="utf-8")
            report_json = (output_dir / "report.json").read_text(encoding="utf-8")
            self.assertIn("## Track A-Stress Shared Stress Test", report_text)
            self.assertIn("stress_report.json", report_text)
            self.assertIn("Track A-Stress", teacher_text)
            self.assertIn("track_a_stress_reference", report_json)

    def test_aggregate_excludes_interim_rows_from_headline_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,scene_1,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,1,1001,parent_run_a,shard_000,0",
                        "cgn,cgn_raw_interim,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_2,scene_2,obj_2,native_opaque_cal,basic,pick up the bowl,dual_fixed_realsense_rgbd,1,0,0,0.0,0.0,150,8.0,grasp_proposal,none,0,,rll_6000_1,deadbeef,1,1002,parent_run_a,shard_001,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            output_dir = self._run_aggregate(root, "--parent-run-id", "parent_run_a")

            summary_text = (output_dir / "summary.csv").read_text(encoding="utf-8")
            interim_text = (output_dir / "historical_interim_summary.csv").read_text(encoding="utf-8")
            report_text = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("graspvla_official", summary_text)
            self.assertNotIn("cgn_raw_interim", summary_text)
            self.assertIn("cgn_raw_interim", interim_text)
            self.assertIn("## Historical / Interim Modular References", report_text)

    def test_aggregate_ignores_integration_fixture_rows_for_track_a_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_cal,integration_fixture,language_conditioned_single_target_pick,scene_fixture,scene_fixture,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,1,2001,parent_fixture,,",
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_real,scene_real,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,2,0,0,0.0,0.0,220,14.0,task_failure,not_met,0,,em14,deadbeef,1,2002,parent_real,shard_000,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            output_dir = self._run_aggregate(root)

            summary_text = (output_dir / "summary.csv").read_text(encoding="utf-8")
            taxonomy_text = (output_dir / "failure_taxonomy.csv").read_text(encoding="utf-8")
            self.assertIn("0.0", summary_text)
            self.assertNotIn("120", summary_text)
            self.assertIn("task_failure", taxonomy_text)

    def test_aggregate_defaults_to_latest_parent_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_old,scene_old,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,1,3001,20260403_old,shard_000,0",
                        "cgn,cgn_full_modular,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_new,scene_new,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,2,0,0,0.0,0.0,220,14.0,task_failure,not_met,0,,rll_6000_1,deadbeef,1,3002,20260403_new,shard_001,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            output_dir = self._run_aggregate(root)

            summary_text = (output_dir / "summary.csv").read_text(encoding="utf-8")
            self.assertIn("20260403_new", (output_dir / "report.json").read_text(encoding="utf-8"))
            self.assertIn("cgn", summary_text)
            self.assertNotIn("scene_old", summary_text)
            shard_text = (output_dir / "by_shard.csv").read_text(encoding="utf-8")
            self.assertIn("shard_001", shard_text)

    def test_aggregate_infers_parent_run_id_from_results_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "20260403_legacy_graspvla"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,graspvla_official,track_a_cal,shared_track_a_sim,language_conditioned_single_target_pick,scene_old,scene_old,obj_1,native_opaque_cal,basic,pick up the banana,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,1,3001,,,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            output_dir = self._run_aggregate(root, "--parent-run-id", "20260403_legacy_graspvla")

            summary_text = (output_dir / "summary.csv").read_text(encoding="utf-8")
            report_json = (output_dir / "report.json").read_text(encoding="utf-8")
            self.assertIn("graspvla", summary_text)
            self.assertIn("20260403_legacy_graspvla", report_json)


if __name__ == "__main__":
    unittest.main()
