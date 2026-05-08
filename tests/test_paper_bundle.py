from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.report.paper_bundle import main as paper_bundle_main
from grasp_benchmark.types import EpisodeResult


class PaperBundleTest(unittest.TestCase):
    HEADER = EpisodeResult.fieldnames()

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

    def _base_row(self, **overrides: object) -> dict[str, object]:
        row = {field: "" for field in self.HEADER}
        row.update(
            {
                "method": "graspvla",
                "method_tier": "graspvla_official",
                "track": "track_a_cal",
                "execution_mode": "shared_track_a_sim",
                "task": "language_conditioned_single_target_pick",
                "scene_id": "scene_1",
                "scene_recipe_id": "scene_recipe_1",
                "object_id": "obj_1",
                "object_group": "native_opaque_cal",
                "condition": "basic",
                "instruction": "pick up the banana",
                "instruction_variant_id": "canonical",
                "instruction_variant_family": "canonical",
                "shift_family": "",
                "shift_severity": "",
                "sensor_stack": "dual_fixed_realsense_rgbd",
                "attempts": 1,
                "success": 1,
                "lift_cm": 20.0,
                "hold_s": 2.0,
                "spl": 1.0,
                "inference_ms": 120.0,
                "cycle_time_s": 4.0,
                "failure_stage": "",
                "failure_reason": "",
                "collision": 0,
                "video_path": "",
                "node": "em14",
                "commit": "deadbeef",
                "replicate_index": 1,
                "seed": 1001,
                "parent_run_id": "parent_cal",
                "shard_id": "shard_000",
                "gpu_id": "0",
                "grounding_success": 1,
                "mask_nonempty": 1,
                "proposal_nonempty": 1,
                "plan_success": 1,
                "lift_only_success": 1,
                "hold_success": 1,
                "slip_after_lift": 0,
                "collision_count": 0,
                "wrong_object": 0,
                "wrong_part": 0,
            }
        )
        row.update(overrides)
        return row

    def _write_results(self, run_dir: Path, metadata: dict[str, object], rows: list[dict[str, object]]) -> None:
        run_dir.mkdir(parents=True)
        (run_dir / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        with (run_dir / "results.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.HEADER)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in self.HEADER})

    def test_paper_bundle_writes_extended_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            self._write_results(
                root / "runs" / "cal_run",
                {"task_set": "track_a_cal_v3", "scene_catalog_name": "graspvla_track_a_playground_cal_v3"},
                [
                    self._base_row(
                        scene_id="scene_1",
                        scene_recipe_id="scene_recipe_1",
                        parent_run_id="parent_cal",
                        method="graspvla",
                        method_tier="graspvla_official",
                        task="language_conditioned_single_target_pick",
                    ),
                    self._base_row(
                        scene_id="scene_1",
                        scene_recipe_id="scene_recipe_1",
                        parent_run_id="parent_cal",
                        method="cgn",
                        method_tier="cgn_full_modular",
                        attempts=3,
                        success=0,
                        lift_cm=0,
                        hold_s=0.0,
                        spl=0.0,
                        inference_ms=220.0,
                        cycle_time_s=10.0,
                        failure_stage="grasp_proposal",
                        failure_reason="none",
                        plan_success=0,
                        lift_only_success=0,
                        hold_success=0,
                    ),
                    self._base_row(
                        scene_id="scene_2",
                        scene_recipe_id="scene_recipe_2",
                        parent_run_id="parent_cal",
                        replicate_index=2,
                        seed=1002,
                        task="language_conditioned_single_target_pick",
                        condition="distractors_light",
                        object_id="obj_2",
                        instruction="pick up the bowl",
                    ),
                    self._base_row(
                        scene_id="scene_2",
                        scene_recipe_id="scene_recipe_2",
                        parent_run_id="parent_cal",
                        method="cgn",
                        method_tier="cgn_full_modular",
                        replicate_index=2,
                        seed=1002,
                        attempts=3,
                        success=0,
                        lift_cm=0,
                        hold_s=0.0,
                        spl=0.0,
                        inference_ms=220.0,
                        cycle_time_s=10.0,
                        failure_stage="segmentation_error",
                        failure_reason="mask_empty",
                        condition="distractors_light",
                        object_id="obj_2",
                        instruction="pick up the bowl",
                        mask_nonempty=0,
                        proposal_nonempty=0,
                        plan_success=0,
                        lift_only_success=0,
                        hold_success=0,
                    ),
                ],
            )

            self._write_results(
                root / "runs" / "stress_run",
                {"task_set": "track_a_stress_v4", "scene_catalog_name": "graspvla_track_a_playground_stress_v4"},
                [
                    self._base_row(
                        track="track_a_stress",
                        task="arbitrary_grasping_transparent",
                        scene_id="scene_3",
                        scene_recipe_id="scene_recipe_3",
                        parent_run_id="parent_stress",
                        object_id="obj_3",
                        object_group="transparent",
                        condition="transparent_pose_bank",
                        instruction="pick up any object",
                        inference_ms=150.0,
                        cycle_time_s=5.0,
                    ),
                    self._base_row(
                        method="cgn",
                        method_tier="cgn_full_modular",
                        track="track_a_stress",
                        task="arbitrary_grasping_transparent",
                        scene_id="scene_3",
                        scene_recipe_id="scene_recipe_3",
                        parent_run_id="parent_stress",
                        object_id="obj_3",
                        object_group="transparent",
                        condition="transparent_pose_bank",
                        instruction="pick up any object",
                        attempts=3,
                        success=0,
                        lift_cm=0,
                        hold_s=0.0,
                        spl=0.0,
                        inference_ms=250.0,
                        cycle_time_s=12.0,
                        failure_stage="task_failure",
                        failure_reason="not_met",
                        proposal_nonempty=0,
                        plan_success=0,
                        lift_only_success=0,
                        hold_success=0,
                    ),
                ],
            )

            self._write_results(
                root / "runs" / "instruction_run",
                {"task_set": "instruction_robustness_v2", "scene_catalog_name": "graspvla_track_a_playground_cal_v3"},
                [
                    self._base_row(
                        track="track_a_instruction",
                        parent_run_id="parent_instruction",
                        instruction_variant_id="canonical",
                        instruction_variant_family="canonical",
                        instruction="pick up the banana",
                    ),
                    self._base_row(
                        method="cgn",
                        method_tier="cgn_full_modular",
                        track="track_a_instruction",
                        parent_run_id="parent_instruction",
                        instruction_variant_id="lexical",
                        instruction_variant_family="lexical_paraphrase",
                        instruction="grab the banana",
                        attempts=3,
                        success=0,
                        lift_cm=0,
                        hold_s=0.0,
                        spl=0.0,
                        inference_ms=230.0,
                        cycle_time_s=10.5,
                        failure_stage="grounding_error",
                        failure_reason="wrong_box",
                        grounding_success=0,
                        mask_nonempty=0,
                        proposal_nonempty=0,
                        plan_success=0,
                    ),
                ],
            )

            self._write_results(
                root / "runs" / "transfer_run",
                {"task_set": "sim2real_proxy_v2", "scene_catalog_name": "graspvla_sim2real_proxy_v2"},
                [
                    self._base_row(
                        track="track_a_transfer",
                        parent_run_id="parent_transfer",
                        shift_family="camera_jitter",
                        shift_severity="low",
                    ),
                    self._base_row(
                        method="cgn",
                        method_tier="cgn_full_modular",
                        track="track_a_transfer",
                        parent_run_id="parent_transfer",
                        shift_family="depth_noise_bias",
                        shift_severity="low",
                        attempts=3,
                        success=0,
                        lift_cm=0,
                        hold_s=0.0,
                        spl=0.0,
                        inference_ms=240.0,
                        cycle_time_s=11.0,
                        failure_stage="task_failure",
                        failure_reason="not_met",
                        proposal_nonempty=0,
                        plan_success=0,
                    ),
                ],
            )

            self._write_results(
                root / "runs" / "phase2_run",
                {"task_set": "phase2_pilot_v1", "scene_catalog_name": "graspvla_phase2_pilot_v1"},
                [
                    self._base_row(
                        track="track_a_phase2",
                        task="mug_handle_grasp",
                        parent_run_id="parent_phase2",
                        object_group="phase2_objects",
                        condition="part_basic",
                        object_id="clear_plastic_cup",
                        instruction="pick up the mug by the handle",
                        wrong_part=0,
                    ),
                    self._base_row(
                        method="cgn",
                        method_tier="cgn_full_modular",
                        track="track_a_phase2",
                        task="mug_handle_grasp",
                        parent_run_id="parent_phase2",
                        object_group="phase2_objects",
                        condition="part_basic",
                        object_id="clear_plastic_cup",
                        instruction="pick up the mug by the handle",
                        attempts=3,
                        success=0,
                        lift_cm=0,
                        hold_s=0.0,
                        spl=0.0,
                        inference_ms=245.0,
                        cycle_time_s=11.5,
                        failure_stage="task_failure",
                        failure_reason="wrong_part",
                        proposal_nonempty=0,
                        plan_success=0,
                        wrong_part=1,
                    ),
                ],
            )

            self._write_results(
                root / "runs" / "native_run",
                {
                    "task_set": "track_b_cgn_official_depth_segmap_v1",
                    "scene_catalog_name": "graspvla_track_b_cgn_native_v2",
                },
                [
                    self._base_row(
                        method="cgn",
                        method_tier="cgn_full_modular",
                        track="track_b_native",
                        task="language_conditioned_single_target_pick",
                        parent_run_id="parent_native",
                        attempts=3,
                        success=0,
                        lift_cm=0,
                        hold_s=0.0,
                        spl=0.0,
                        inference_ms=310.0,
                        cycle_time_s=15.0,
                        failure_stage="task_failure",
                        failure_reason="not_met",
                    ),
                ],
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
            protocol_probe.write_text(
                json.dumps({"overall": [{"variant": "P0_shared_baseline", "success_rate": 1.0, "mean_attempts": 1.0}]}),
                encoding="utf-8",
            )
            cgn_bottleneck = root / "cgn_bottleneck.json"
            cgn_bottleneck.write_text(
                json.dumps({"summary": [{"variant": "D0_shared_cgn", "success_rate": 0.0, "mean_attempts": 3.0}]}),
                encoding="utf-8",
            )

            output_dir = self._run_bundle(
                root,
                "--submission-mode",
                "--track-a-cal-parent-run-id",
                "parent_cal",
                "--track-a-stress-parent-run-id",
                "parent_stress",
                "--instruction-parent-run-id",
                "parent_instruction",
                "--sim2real-parent-run-id",
                "parent_transfer",
                "--phase2-parent-run-id",
                "parent_phase2",
                "--track-b-native-parent-run-id",
                "parent_native",
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
            self.assertTrue((output_dir / "collaborator_summary.md").exists())
            self.assertTrue((output_dir / "figures" / "pairwise_stats.csv").exists())
            self.assertTrue((output_dir / "figures" / "instruction_robustness_summary.csv").exists())
            self.assertTrue((output_dir / "figures" / "sim2real_proxy_summary.csv").exists())
            self.assertTrue((output_dir / "figures" / "stage_metrics_summary.csv").exists())
            self.assertTrue((output_dir / "figures" / "phase2_pilot_summary.csv").exists())
            collaborator_text = (output_dir / "collaborator_summary.md").read_text(encoding="utf-8")
            self.assertIn("Simulation Summary", collaborator_text)
            self.assertIn("shared benchmark + protocol audit", collaborator_text)
            self.assertIn("Main Shared Grasping Benchmark", collaborator_text)
            self.assertIn("Hard Shared Grasping Stress Test", collaborator_text)
            report_text = (output_dir / "paper_ready_report.md").read_text(encoding="utf-8")
            self.assertIn("## Main Shared Grasping Benchmark", report_text)
            self.assertIn("Main Shared Grasping Benchmark", report_text)
            self.assertIn("## Hard Shared Grasping Stress Test", report_text)
            self.assertIn("Hard Shared Grasping Stress Test", report_text)
            self.assertIn("## Instruction Robustness Check", report_text)
            self.assertIn("## Sim-to-Real Proxy Robustness", report_text)
            self.assertIn("## Task-Oriented Grasping Pilot", report_text)
            stats_payload = json.loads((output_dir / "paper_stats.json").read_text(encoding="utf-8"))
            self.assertIn("pairwise_stats", stats_payload)
            self.assertIn("track_b_native_appendix", stats_payload)
            self.assertIn("instruction_robustness", stats_payload)
            self.assertIn("sim2real_proxy", stats_payload)
            self.assertIn("phase2_pilot", stats_payload)
            self.assertIn("task_set_labels", stats_payload["track_a_cal"])
            self.assertIn("Main Shared Grasping Benchmark", stats_payload["track_a_cal"]["task_set_labels"]["track_a_cal_v3"])
            self.assertEqual(stats_payload["pairwise_stats"][0]["paired_scenes"], 2)


if __name__ == "__main__":
    unittest.main()
