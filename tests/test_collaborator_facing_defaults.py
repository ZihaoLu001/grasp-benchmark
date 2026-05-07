from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class CollaboratorFacingDefaultsTest(unittest.TestCase):
    def _read(self, relpath: str) -> str:
        return (REPO_ROOT / relpath).read_text(encoding="utf-8")

    def test_readme_matches_current_pdf_task_sets(self) -> None:
        text = self._read("README.md")
        self.assertIn("Main Shared Grasping Benchmark", text)
        self.assertIn("Hard Shared Grasping Stress Test", text)
        self.assertIn("track_a_cal_v3", text)
        self.assertIn("track_a_stress_v4", text)
        self.assertIn("instruction_robustness_v2", text)
        self.assertIn("phase2_pilot_v1", text)
        self.assertIn("CGN shared lane", text)
        self.assertIn("Which Task Set Should I Use?", text)
        self.assertIn("Internal `task_set` IDs are kept stable", text)
        self.assertIn("CGN Native-Reference Appendix", text)
        self.assertIn("pre-rerun shared-lane evidence", text)
        self.assertIn("TensorFlow 2.12.0 / CUDA 11.8 / cuDNN 8.6", text)
        self.assertIn("raw Contact-GraspNet proposal generation works on H100", text)
        self.assertIn("1 / 90", text)
        self.assertIn("2 / 168", text)
        self.assertIn("25 / 90", text)
        self.assertIn("20 / 168", text)
        self.assertIn("8 / 40", text)
        self.assertIn("docs/current_benchmark_report.md", text)
        self.assertNotIn("docs/reports/", text)
        self.assertNotIn("_zh.md", text)
        self.assertNotIn("older 60-trial draft is the headline", text)
        self.assertNotIn("D:/codex", text)
        self.assertNotIn("D:\\codex", text)

    def test_single_current_report_is_the_documentation_entrypoint(self) -> None:
        text = self._read("docs/current_benchmark_report.md")
        self.assertIn("Main Shared Grasping Benchmark", text)
        self.assertIn("CGN shared lane", text)
        self.assertIn("gb-cgn-tf212", text)
        self.assertIn("1/90", text)
        self.assertIn("2/168", text)
        self.assertIn("25/90", text)
        self.assertIn("20/168", text)
        self.assertIn("8/40", text)
        self.assertIn("GroundingDINO", text)
        self.assertIn("do not establish that official Contact-GraspNet capability is zero", text)
        self.assertNotIn("D:/codex", text)
        self.assertNotIn("D:\\codex", text)

    def test_bundle_script_targets_current_canonical_suites(self) -> None:
        text = self._read("scripts/build_corl2026_bundle_v3.ps1")
        self.assertIn("track_a_stress_v4", text)
        self.assertIn("instruction_robustness_v2", text)
        self.assertIn("sim2real_proxy_v2", text)
        self.assertIn("phase2_pilot_v1", text)
        self.assertIn("track_b_cgn_native_v2", text)
        self.assertNotIn("track_a_stress_v3_shared_sim", text)
        self.assertNotIn("track_b_cgn_native_v1", text)
        self.assertNotIn("D:\\codex", text)

    def test_run_suite_uses_track_a_stress_v4(self) -> None:
        text = self._read("scripts/run_corl2026_graspvla_suite.ps1")
        self.assertIn("--task-set track_a_stress_v4", text)
        self.assertIn("--cluster-config $ClusterConfig", text)
        self.assertNotIn("--task-set track_a_stress_v3", text)

    def test_cgn_pipeline_audit_documents_grounding_dino_boundary(self) -> None:
        text = self._read("docs/current_benchmark_report.md")
        self.assertIn("GroundingDINO", text)
        self.assertIn("Contact-GraspNet", text)
        self.assertIn("oracle_gt", text)
        self.assertIn("do not establish that official Contact-GraspNet capability is zero", text)
        self.assertIn("TensorFlow matmul", text)
        self.assertIn("raw Contact-GraspNet", text)
        self.assertIn("task_failure", text)
        self.assertIn("oracle topdown", text)

    def test_cgn_method_config_has_explicit_pipeline_contract(self) -> None:
        text = self._read("configs/methods/cgn.yaml")
        self.assertIn("claim_boundary: benchmark_owned_shared_lane_not_official_contact_graspnet_native", text)
        self.assertIn("pipeline_contract:", text)
        self.assertIn("task_localization: GroundingDINO", text)
        self.assertIn("grasp_proposal: Contact-GraspNet", text)
        self.assertIn("success_rule: shared_track_a_lift_15cm_hold_2s", text)

    def test_cgn_h100_rerun_report_documents_nonzero_shared_lane(self) -> None:
        text = self._read("docs/current_benchmark_report.md")
        self.assertIn("27.78%", text)
        self.assertIn("11.90%", text)
        self.assertIn("watermelon", text)
        self.assertIn("oracle topdown", text)
        self.assertIn("pre-rerun", text)

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


if __name__ == "__main__":
    unittest.main()
