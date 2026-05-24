from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.paths import PROJECT_ROOT
from grasp_benchmark.vla_continual.lora_svd import summarize_lora_effective_rank
from grasp_benchmark.vla_continual.prepare_next_experiments import DEFAULT_CONFIG, generate_jobs


class VlaContinualPrepareTest(unittest.TestCase):
    def test_default_config_tracks_third_party_repo(self) -> None:
        text = DEFAULT_CONFIG.read_text(encoding="utf-8")
        self.assertIn("continual-vla-rl", text)
        self.assertIn("dc1b1c8a7fb630c8d9aaf349376ae5a49b575b4e", text)

    def test_generate_spatial_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = generate_jobs(
                config_path=DEFAULT_CONFIG,
                output_dir=Path(tmp),
                suites=["libero_spatial"],
            )

            self.assertEqual(manifest["selected_suites"], ["libero_spatial"])
            self.assertEqual(len(manifest["jobs"]), 2)
            self.assertGreaterEqual(len(manifest["scripts"]), 4)

            names = {job["name"] for job in manifest["jobs"]}
            self.assertIn("sca-vla-seq-rl-ref-libero-spatial", names)
            self.assertIn("sca-vla-offline-collect-libero-spatial", names)
            script_names = {script["name"] for script in manifest["scripts"]}
            self.assertIn("submit_policy_anchor_smoke.sh", script_names)
            self.assertIn("submit_policy_anchor_full.sh", script_names)
            self.assertIn("submit_behavior_field_anchor_smoke.sh", script_names)
            self.assertIn("submit_behavior_field_anchor_full.sh", script_names)
            self.assertIn("prepare_seq_rl_checkpoints.sh", script_names)

            seq_job = next(job for job in manifest["jobs"] if job["kind"] == "seq-rl-ref")
            self.assertIn("run_embodiment_sequential.sh", seq_job["command"])
            self.assertIn('"0,9"', seq_job["command"])
            self.assertIn("libero_spatial_grpo_openvlaoft_spatial", seq_job["command"])
            self.assertIn("Missing local Seq-RL model directory", seq_job["command"])

            smoke_script = next(script for script in manifest["scripts"] if script["name"] == "submit_policy_anchor_smoke.sh")
            self.assertIn("--methods policy_anchor_balanced", smoke_script["command"])
            self.assertIn("--max-stages 3", smoke_script["command"])
            self.assertIn("--teacher-distill-lambda 0.5", smoke_script["command"])
            self.assertIn("--teacher-distill-balance-groups", smoke_script["command"])

            bfa_smoke_script = next(
                script for script in manifest["scripts"] if script["name"] == "submit_behavior_field_anchor_smoke.sh"
            )
            self.assertIn("--methods behavior_field_anchor", bfa_smoke_script["command"])
            self.assertIn("--bfa-lambda-field 0.5", bfa_smoke_script["command"])
            self.assertIn("--bfa-image-noise-std 0.02", bfa_smoke_script["command"])
            self.assertIn("--bfa-proprio-noise-std 0.01", bfa_smoke_script["command"])

            manifest_path = Path(tmp) / "manifest.json"
            self.assertTrue(manifest_path.exists())
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["jobs"][0]["suite"], "libero_spatial")

    def test_submodule_metadata_exists(self) -> None:
        gitmodules = PROJECT_ROOT / ".gitmodules"
        self.assertTrue(gitmodules.exists())
        text = gitmodules.read_text(encoding="utf-8")
        self.assertIn("third_party/continual-vla-rl", text)

    def test_lora_effective_rank_summary_on_synthetic_adapter(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp)
            state = {
                "base_model.model.foo.lora_A.default.weight": torch.eye(2, 4),
                "base_model.model.foo.lora_B.default.weight": torch.eye(3, 2),
            }
            torch.save(state, checkpoint / "adapter_model.bin")

            summary = summarize_lora_effective_rank(checkpoint)
            self.assertEqual(summary["num_lora_layers"], 1)
            self.assertAlmostEqual(summary["mean_nonzero_rank"], 2.0)
            self.assertGreater(summary["mean_effective_rank"], 1.9)


if __name__ == "__main__":
    unittest.main()
