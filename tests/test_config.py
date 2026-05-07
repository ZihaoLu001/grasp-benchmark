from __future__ import annotations

import unittest
from unittest.mock import patch

from grasp_benchmark.config import load_cluster_config, load_named_config, resolve_cluster_config_name
from grasp_benchmark.paths import PROJECT_ROOT
from grasp_benchmark.run.worker import _runtime_config


class ConfigTest(unittest.TestCase):
    def test_cluster_config_contains_expected_keys(self) -> None:
        config = load_named_config("cluster", "default")
        self.assertIn("remote_root", config)
        self.assertIn("pool_hosts", config)
        self.assertIn("default_graspvla_node", config)

    def test_lakeshore_cluster_config_is_selectable(self) -> None:
        config = load_cluster_config("lakeshore")
        self.assertEqual(config["default_graspvla_node"], "lakeshore")
        self.assertIn("/projects/cs_yifan16_chi/zlu31", config["remote_root"])
        self.assertIn("/projects/cs_yifan16_chi/zlu31", config["conda_envs_dir"])
        self.assertIn("/projects/cs_yifan16_chi/zlu31", config["conda_pkgs_dir"])
        self.assertIn("/cm/shared/apps/cuda11.8", config["cuda_home"])
        self.assertIn("lakeshore", config["pool_hosts"])
        self.assertEqual(config["scheduler"]["type"], "slurm")
        self.assertEqual(config["scheduler"]["account"], "cs_yifan16_chi")
        self.assertEqual(config["scheduler"]["partition"], "batch_gpu2")
        self.assertEqual(config["scheduler"]["matrix_slots"], 4)
        self.assertEqual(config["scheduler"]["cpus_per_task"], 2)
        self.assertEqual(config["scheduler"]["mem"], "48G")
        self.assertEqual(config["prepare_scheduler"]["partition"], "batch")
        self.assertIn("srun", config["required_bins"])

    def test_cluster_config_env_override(self) -> None:
        with patch.dict("os.environ", {"GRASP_BENCHMARK_CLUSTER_CONFIG": "lakeshore"}):
            self.assertEqual(resolve_cluster_config_name(), "lakeshore")
            self.assertEqual(load_cluster_config()["default_graspvla_node"], "lakeshore")

    def test_runtime_config_passes_cluster_cuda_home_to_method_adapter(self) -> None:
        cluster_config = load_cluster_config("lakeshore")
        runtime = _runtime_config(load_named_config("methods", "cgn"), cluster_config)

        self.assertEqual(runtime["cuda_home"], cluster_config["cuda_home"])

    def test_bootstrap_cluster_uses_repository_config_module(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "bootstrap_cluster.ps1").read_text(encoding="utf-8")

        self.assertIn('sys.path.insert(0, str(repo_root / "src"))', script)
        self.assertIn("'@ | python - $ClusterConfig $repoRoot", script)


if __name__ == "__main__":
    unittest.main()
