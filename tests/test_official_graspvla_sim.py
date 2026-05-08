from __future__ import annotations

import unittest

from grasp_benchmark.official_graspvla_sim import _build_remote_script


class OfficialGraspvlaSimTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cluster_config = {
            "miniforge_root": "/projects/cs_yifan16_chi/zlu31/miniforge3",
            "remote_root": "/projects/cs_yifan16_chi/zlu31/grasp-benchmark",
            "conda_envs_dir": "/projects/cs_yifan16_chi/zlu31/conda_envs",
        }
        self.method_config = {
            "official_sim_env_name": "gb-graspvla-sim",
        }

    def test_remote_script_uses_parallel_libero_workers(self) -> None:
        script = _build_remote_script(
            self.cluster_config,
            self.method_config,
            mode="full",
            port=6666,
            playground_trials=10,
            libero_trial_num=50,
            max_tasks_per_benchmark=10,
            benchmarks=["libero_object", "libero_10", "libero_goal"],
            exp_name_prefix="graspvla_official_complete",
            parallel_env_num=5,
        )

        self.assertIn('export PARALLEL_ENV_NUM="5"', script)
        self.assertIn('python evaluate_libero_tasks.py --config-path="$OUTPUT_DIR" --config-name="temp_config_${i}"', script)
        self.assertIn('libero_worker_${i}_stdout.txt', script)
        self.assertIn('python playground.py name=graspvla_official_complete_playground trial_num=10 port=6666', script)

    def test_remote_script_uses_sequential_libero_by_default(self) -> None:
        script = _build_remote_script(
            self.cluster_config,
            self.method_config,
            mode="full",
            port=6666,
            playground_trials=1,
            libero_trial_num=1,
            max_tasks_per_benchmark=1,
            benchmarks=["libero_object"],
            exp_name_prefix="graspvla_official_smoke",
            parallel_env_num=1,
        )

        self.assertIn("python evaluate_libero_tasks.py name=graspvla_official_smoke_libero trial_num=1", script)
        self.assertNotIn("libero_worker_${i}_stdout.txt", script)


if __name__ == "__main__":
    unittest.main()
