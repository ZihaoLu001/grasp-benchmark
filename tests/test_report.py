from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.report.aggregate import main as aggregate_main


class ReportTest(unittest.TestCase):
    def test_aggregate_creates_summary_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        "method,track,task,scene_id,object_id,object_group,condition,instruction,sensor_stack,attempts,success,lift_cm,hold_s,spl,inference_ms,cycle_time_s,failure_stage,failure_reason,collision,video_path,node,commit",
                        "graspvla,track_a,language_conditioned_single_target_pick,scene_1,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef",
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

    def test_aggregate_writes_track_b_reference_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_dir = root / "runs" / "sample"
            runs_dir.mkdir(parents=True)
            (runs_dir / "results.csv").write_text(
                "\n".join(
                    [
                        "method,track,task,scene_id,object_id,object_group,condition,instruction,sensor_stack,attempts,success,lift_cm,hold_s,spl,inference_ms,cycle_time_s,failure_stage,failure_reason,collision,video_path,node,commit",
                        "graspvla,track_a,language_conditioned_single_target_pick,scene_1,obj_1,ycb_core,basic,pick up the mug,dual_fixed_realsense_rgbd,1,1,20,2.0,1.0,120,4.0,,,0,,em14,deadbeef",
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


if __name__ == "__main__":
    unittest.main()
