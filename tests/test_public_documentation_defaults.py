from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PublicDocumentationDefaultsTest(unittest.TestCase):
    def _read(self, relpath: str) -> str:
        return (REPO_ROOT / relpath).read_text(encoding="utf-8")

    def test_readme_uses_current_public_language(self) -> None:
        text = self._read("README.md")
        self.assertIn("Main Shared Grasping Benchmark", text)
        self.assertIn("Hard Shared Grasping Stress Test", text)
        self.assertIn("Instruction Robustness Check", text)
        self.assertIn("Task-Oriented Grasping Pilot", text)
        self.assertIn("Contact-GraspNet modular pipeline", text)
        self.assertIn("View-Matched Main Benchmark", text)
        self.assertIn("Speed and Latency", text)
        self.assertIn("same rendered camera rig", text)
        self.assertIn("front_view", text)
        self.assertIn("side_view", text)
        self.assertIn("256 x 256", text)
        self.assertIn("IK_POSE", text)
        self.assertIn("5 Hz", text)
        self.assertIn("view-matched system comparison", text)
        self.assertIn("view-count parity", text)
        self.assertIn("Single front camera", text)
        self.assertIn("Two cameras", text)
        self.assertIn("68 / 90", text)
        self.assertIn("43 / 90", text)
        self.assertIn("75.56%", text)
        self.assertIn("47.78%", text)
        self.assertIn("declared input interface", text)
        self.assertIn("about `200 ms`", text)
        self.assertIn("`5 Hz` for GraspVLA, `37 Hz` for AnyGrasp", text)
        self.assertIn("Logged latency signal", text)
        self.assertIn("model-server round trip", text)
        self.assertIn("adapter-step average", text)
        self.assertIn("median `136.6 ms`", text)
        self.assertIn("median `4.83 s`", text)
        self.assertIn("median `25.4 ms`", text)
        self.assertIn("median `52.24 s`", text)
        self.assertIn("configs/results/cgn_shared_protocol_h100_20260508.json", text)
        self.assertIn("configs/results/fair_sensor_view_ablation_h100_20260508.json", text)
        self.assertIn("configs/results/speed_validation_lakeshore_h100_20260508.json", text)
        self.assertIn("configs/results/cgn_official_depth_segmap_h100_20260508.json", text)
        self.assertIn("official-input validation", text)
        self.assertNotIn("40 / 138", text)
        self.assertNotIn("39 / 138", text)
        self.assertIn("docs/current_benchmark_report.md", text)
        self.assertNotIn("docs/reports/", text)
        self.assertNotIn("_zh.md", text)
        self.assertNotIn("D:/codex", text)
        self.assertNotIn("D:\\codex", text)
        self.assertNotIn("same cameras", text)

    def test_single_current_report_is_the_documentation_entrypoint(self) -> None:
        text = self._read("docs/current_benchmark_report.md")
        self.assertIn("Main Shared Grasping Benchmark", text)
        self.assertIn("Contact-GraspNet modular pipeline", text)
        self.assertIn("Speed and Latency", text)
        self.assertIn("Shared Experimental Setup", text)
        self.assertIn("front_view", text)
        self.assertIn("side_view", text)
        self.assertIn("256 x 256", text)
        self.assertIn("depth + K + segmap + RGB", text)
        self.assertIn("View-Matched Main Benchmark", text)
        self.assertIn("view-count-matched system comparison", text)
        self.assertIn("Single front camera", text)
        self.assertIn("Two cameras", text)
        self.assertIn("68 / 90", text)
        self.assertIn("43 / 90", text)
        self.assertIn("75.56%", text)
        self.assertIn("47.78%", text)
        self.assertIn("gb-cgn-tf212", text)
        self.assertIn("25 / 90", text)
        self.assertIn("20 / 168", text)
        self.assertIn("8 / 40", text)
        self.assertIn("configs/results/cgn_shared_protocol_h100_20260508.json", text)
        self.assertIn("configs/results/fair_sensor_view_ablation_h100_20260508.json", text)
        self.assertIn("configs/results/cgn_official_depth_segmap_h100_20260508.json", text)
        self.assertNotIn("configs/results/cgn_native_reference_h100_20260507.json", text)
        self.assertNotIn("40 / 138", text)
        self.assertIn("488 / 488", text)
        self.assertNotIn("39 / 138", text)
        self.assertNotIn("28.26%", text)
        self.assertNotIn("939", text)
        self.assertIn("GroundingDINO", text)
        self.assertNotIn("D:/codex", text)
        self.assertNotIn("D:\\codex", text)
        self.assertNotIn("Collaborator-Facing", text)
        self.assertNotIn("same cameras", text)

    def test_bundle_script_targets_current_canonical_suites(self) -> None:
        text = self._read("scripts/build_corl2026_bundle_v3.ps1")
        self.assertIn("track_a_stress_v4", text)
        self.assertIn("instruction_robustness_v2", text)
        self.assertIn("sim2real_proxy_v2", text)
        self.assertIn("phase2_pilot_v1", text)
        self.assertIn("track_b_cgn_official_depth_segmap_v1", text)
        self.assertIn("Get-RunTrialCount", text)
        self.assertIn('Join-Path $Candidate.FullName "shards"', text)
        self.assertIn('Get-ChildItem $shardsRoot -Recurse -Filter "results.csv"', text)
        self.assertNotIn("track_a_stress_v3_shared_sim", text)
        self.assertNotIn("track_b_cgn_native_v1", text)
        self.assertNotIn("D:\\codex", text)

    def test_run_suite_uses_track_a_stress_v4(self) -> None:
        text = self._read("scripts/run_corl2026_graspvla_suite.ps1")
        self.assertIn("--task-set track_a_stress_v4", text)
        self.assertIn("--cluster-config $ClusterConfig", text)
        self.assertNotIn("--task-set track_a_stress_v3", text)

    def test_cgn_method_config_has_explicit_pipeline_contract(self) -> None:
        text = self._read("configs/methods/cgn.yaml")
        self.assertIn("claim_boundary: benchmark_owned_contact_graspnet_shared_pipeline", text)
        self.assertIn("pipeline_contract:", text)
        self.assertIn("task_localization: GroundingDINO", text)
        self.assertIn("grasp_proposal: Contact-GraspNet", text)
        self.assertIn("success_rule: shared_track_a_lift_15cm_hold_2s", text)
        self.assertIn("validate_gripper_opening: true", text)
        self.assertIn("grasp_frame_to_tcp_status: explicit_identity_shared_lane_not_native_calibration", text)

    def test_adapter_modules_have_concrete_implementations(self) -> None:
        self.assertFalse((REPO_ROOT / "src/grasp_benchmark/adapters/placeholders.py").exists())
        text = self._read("src/grasp_benchmark/adapters/__init__.py")
        self.assertIn("from grasp_benchmark.adapters.graspvla import GraspVLAAdapter", text)
        self.assertNotIn("placeholders", text)

    def test_current_cgn_shared_numbers_are_backed_by_tracked_evidence(self) -> None:
        evidence = json.loads(self._read("configs/results/cgn_shared_protocol_h100_20260508.json"))
        suites = {suite["task_set"]: suite for suite in evidence["suites"]}
        expected = {
            "track_a_cal_v3": (25, 90, "27.78%"),
            "track_a_stress_v4": (20, 168, "11.90%"),
            "instruction_robustness_v2": (8, 40, "20.00%"),
            "phase2_pilot_v1": (0, 24, "0.00%"),
        }
        readme = self._read("README.md")
        report = self._read("docs/current_benchmark_report.md")
        for task_set, (successes, trials, percent) in expected.items():
            self.assertEqual(suites[task_set]["successes"], successes)
            self.assertEqual(suites[task_set]["trials"], trials)
            self.assertEqual(suites[task_set]["observed_shard_count"], suites[task_set]["expected_shard_count"])
            self.assertEqual(suites[task_set]["duplicate_scene_ids"], 0)
            self.assertEqual(suites[task_set]["wrong_object_successes"], 0)
            self.assertIn(f"{successes} / {trials}", readme)
            self.assertIn(f"{successes} / {trials}", report)
            self.assertIn(percent, report)

    def test_view_matched_main_numbers_are_backed_by_tracked_evidence(self) -> None:
        evidence = json.loads(self._read("configs/results/fair_sensor_view_ablation_h100_20260508.json"))
        readme = self._read("README.md")
        report = self._read("docs/current_benchmark_report.md")

        self.assertEqual(evidence["batch"], "fair_sensor_ablation_20260508_193155_41238af")
        self.assertTrue(evidence["commit"].startswith("41238af"))

        rows = {row["label"]: row for row in evidence["experiments"]}
        expected = {
            "GraspVLA front-only duplicate RGB": (68, 90, "75.56%"),
            "Contact-GraspNet two-view fused RGB-D": (43, 90, "47.78%"),
        }
        for label, (successes, trials, percent) in expected.items():
            self.assertEqual(rows[label]["successes"], successes)
            self.assertEqual(rows[label]["trials"], trials)
            self.assertEqual(rows[label]["success_rate"], percent)
            self.assertEqual(rows[label]["missing_results"], [])
            self.assertIn(f"{successes} / {trials}", readme)
            self.assertIn(f"{successes} / {trials}", report)
            self.assertIn(percent, readme)
            self.assertIn(percent, report)

        cgn_reference = evidence["cgn_front_rgbd_reference"]["suites"][0]
        self.assertEqual(cgn_reference["task_set"], "track_a_cal_v3")
        self.assertEqual(cgn_reference["successes"], 25)
        self.assertEqual(cgn_reference["trials"], 90)

    def test_cgn_native_reference_appendix_is_backed_by_tracked_evidence(self) -> None:
        evidence = json.loads(self._read("configs/results/cgn_native_reference_h100_20260507.json"))
        self.assertTrue(evidence["completed"])
        self.assertEqual(evidence["task_set"], "track_b_cgn_native_v2")
        self.assertEqual(evidence["successes"], 39)
        self.assertEqual(evidence["trial_count"], 138)
        self.assertEqual(evidence["success_rate"], "28.26%")
        self.assertEqual(evidence["observed_shard_count"], evidence["expected_shards"])
        self.assertEqual(evidence["wrong_object_successes"], 0)
        self.assertEqual(evidence["duplicate_trial_keys"], 0)
        self.assertEqual(evidence["trace_evidence"]["files_checked"], 939)
        self.assertEqual(evidence["trace_evidence"]["official_filtering_confirmed_files"], 939)
        self.assertEqual(evidence["trace_evidence"]["tensorflow_gpu_files"], 939)
        self.assertIn("local_regions=True", evidence["official_filtering_contract"])
        self.assertIn("filter_grasps=True", evidence["official_filtering_contract"])
        for job in evidence["slurm_jobs"]:
            self.assertEqual(job["state"], "COMPLETED")
            self.assertEqual(job["exit_code"], "0:0")

    def test_cgn_official_depth_segmap_appendix_is_backed_by_tracked_evidence(self) -> None:
        evidence = json.loads(self._read("configs/results/cgn_official_depth_segmap_h100_20260508.json"))
        report = self._read("docs/current_benchmark_report.md")

        self.assertTrue(evidence["completed"])
        self.assertEqual(evidence["task_set"], "track_b_cgn_official_depth_segmap_v1")
        self.assertEqual(evidence["successes"], 40)
        self.assertEqual(evidence["trial_count"], 138)
        self.assertEqual(evidence["success_rate"], "28.99%")
        self.assertEqual(evidence["observed_shard_count"], evidence["expected_shards"])
        self.assertEqual(evidence["wrong_object_successes"], 0)
        self.assertEqual(evidence["duplicate_trial_keys"], 0)
        self.assertEqual(evidence["trace_evidence"]["official_depth_k_segmap_files"], 488)
        self.assertEqual(evidence["trace_evidence"]["raw_point_files"], 0)
        self.assertEqual(evidence["trace_evidence"]["official_filtering_confirmed_files"], 488)
        self.assertEqual(evidence["trace_evidence"]["tensorflow_gpu_files"], 488)
        self.assertEqual(evidence["latency_summary"]["all_trials"]["count"], 138)
        self.assertEqual(evidence["latency_summary"]["successful_rows"]["count"], 40)
        self.assertEqual(evidence["latency_summary"]["all_trials"]["inference_ms"]["median"], 5572.87)
        self.assertEqual(evidence["latency_summary"]["successful_rows"]["inference_ms"]["median"], 82.52)
        self.assertIn("depth+K+segmap", evidence["claim_boundary"])
        for job in evidence["slurm_jobs"]:
            self.assertEqual(job["state"], "COMPLETED")
            self.assertEqual(job["exit_code"], "0:0")
        self.assertNotIn("40 / 138", report)
        self.assertIn("official_depth_k_segmap", report)

    def test_tracked_docs_are_kept_small(self) -> None:
        docs = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in (REPO_ROOT / "docs").rglob("*")
            if path.is_file()
        ]
        self.assertEqual(docs, ["docs/current_benchmark_report.md"])

    def test_submission_bundle_defaults_are_not_machine_local(self) -> None:
        text = self._read("scripts/build_corl2026_submission_bundle.ps1")
        self.assertIn('Join-Path $repoRoot "artifacts\\runs"', text)
        self.assertIn('Join-Path $repoRoot "src"', text)
        self.assertNotIn("D:\\codex", text)

    def test_slide_script_matches_current_documentation_policy(self) -> None:
        text = self._read("scripts/build_graspvla_slides.py")
        self.assertIn('"artifacts" / "slides"', text)
        self.assertIn("AnyGrasp is excluded from current comparative claims", text)
        self.assertIn("25/90, 20/168, 8/40, and 0/24", text)
        self.assertIn("Official-input validation confirms", text)
        self.assertIn("cgn_shared_protocol_h100_20260508.json", text)
        self.assertNotIn('"docs" / "slides"', text)
        self.assertNotIn("Fetch the AnyGrasp license", text)
        self.assertNotIn("D:\\", text)

    def test_pyproject_declares_core_runtime_dependencies(self) -> None:
        payload = tomllib.loads(self._read("pyproject.toml"))
        dependencies = payload["project"]["dependencies"]
        self.assertIn("numpy>=1.26,<2", dependencies)
        self.assertIn("PyYAML>=6.0,<7", dependencies)
        self.assertIn("transforms3d>=0.4,<1", dependencies)


if __name__ == "__main__":
    unittest.main()
