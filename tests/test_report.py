from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.report.aggregate import main as aggregate_main


class ReportTest(unittest.TestCase):
    HEADER = (
        "method,track,execution_mode,task,scene_id,object_id,object_group,condition,instruction,sensor_stack,"
        "attempts,success,lift_cm,hold_s,spl,inference_ms,cycle_time_s,failure_stage,failure_reason,collision,"
        "video_path,node,commit,parent_run_id,shard_id,gpu_id"
    )

    def test_aggregate_creates_summary_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,track_a,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,parent_run_a,shard_000,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
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
                ]
                aggregate_main()
            finally:
                sys.argv = argv

            self.assertTrue((output_dir / "summary.csv").exists())
            self.assertTrue((output_dir / "report.md").exists())
            self.assertTrue((output_dir / "teacher_summary_zh.md").exists())
            teacher_text = (output_dir / "teacher_summary_zh.md").read_text(encoding="utf-8")
            self.assertIn("# Benchmark 汇总说明", teacher_text)
            self.assertIn("Track A 才是 benchmark setting 下可用于公平比较的正式分数。", teacher_text)

    def test_aggregate_writes_track_b_reference_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,track_a,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,parent_run_a,shard_000,0",
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
                """
{
  "method": "graspvla",
  "track": "track_b_native",
  "statistics_text": "libero_object: 482/500 = 0.964\\nlibero_10: 325/350 = 0.929\\n"
}
""".strip(),
                encoding="utf-8",
            )
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
                    "--track-b-reference",
                    str(summary_path),
                ]
                aggregate_main()
            finally:
                sys.argv = argv

            report_text = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertTrue((output_dir / "track_b_reference.csv").exists())
            self.assertIn("## Track A Shared Benchmark", report_text)
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
                        "graspvla,track_a,shared_track_a_sim,language_conditioned_single_target_pick,scene_1,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,1,0,0,0.0,0.0,120,4.0,task_failure,not_met,0,,em14,deadbeef,parent_run_a,shard_000,0",
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
                    "--diagnostic-report",
                    str(diagnostic_report),
                ]
                aggregate_main()
            finally:
                sys.argv = argv

            report_text = (output_dir / "report.md").read_text(encoding="utf-8")
            teacher_text = (output_dir / "teacher_summary_zh.md").read_text(encoding="utf-8")
            report_json = (output_dir / "report.json").read_text(encoding="utf-8")
            self.assertIn("## GraspVLA Diagnostic Note", report_text)
            self.assertIn("- Gripper mismatch is not the main factor.", report_text)
            self.assertIn("- The gap is not mainly a threshold artifact.", teacher_text)
            self.assertIn("diagnostic_note", report_json)

    def test_aggregate_ignores_integration_fixture_rows_for_track_a_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        self.HEADER,
                        "graspvla,track_a,integration_fixture,language_conditioned_single_target_pick,scene_fixture,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,parent_fixture,,",
                        "graspvla,track_a,shared_track_a_sim,language_conditioned_single_target_pick,scene_real,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,2,0,0,0.0,0.0,220,14.0,task_failure,not_met,0,,em14,deadbeef,parent_real,shard_000,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
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
                ]
                aggregate_main()
            finally:
                sys.argv = argv

            summary_text = (output_dir / "summary.csv").read_text(encoding="utf-8")
            self.assertIn("0.0", summary_text)
            self.assertNotIn("120", summary_text)
            taxonomy_text = (output_dir / "failure_taxonomy.csv").read_text(encoding="utf-8")
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
                        "graspvla,track_a,shared_track_a_sim,language_conditioned_single_target_pick,scene_old,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,20260403_old,shard_000,0",
                        "cgn,track_a,shared_track_a_sim,language_conditioned_single_target_pick,scene_new,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,2,0,0,0.0,0.0,220,14.0,task_failure,not_met,0,,rll_6000_1,deadbeef,20260403_new,shard_001,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
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
                ]
                aggregate_main()
            finally:
                sys.argv = argv

            summary_text = (output_dir / "summary.csv").read_text(encoding="utf-8")
            self.assertIn("20260403_new", (output_dir / "report.json").read_text(encoding="utf-8"))
            self.assertIn("cgn", summary_text)
            self.assertNotIn("graspvla", summary_text)
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
                        "graspvla,track_a,shared_track_a_sim,language_conditioned_single_target_pick,scene_old,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef,,,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
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
                    "--parent-run-id",
                    "20260403_legacy_graspvla",
                ]
                aggregate_main()
            finally:
                sys.argv = argv

            summary_text = (output_dir / "summary.csv").read_text(encoding="utf-8")
            report_json = (output_dir / "report.json").read_text(encoding="utf-8")
            self.assertIn("graspvla", summary_text)
            self.assertIn("20260403_legacy_graspvla", report_json)


if __name__ == "__main__":
    unittest.main()
