from __future__ import annotations

import unittest

from grasp_benchmark.config import load_named_config
from grasp_benchmark.serve.graspvla import _build_remote_launch_script, _build_validate_script


class ServeGraspVLATest(unittest.TestCase):
    def test_launch_script_uses_env_python_directly(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "graspvla")
        script = _build_remote_launch_script(
            cluster_config=cluster_config,
            method_config=method_config,
            model_path="/tmp/model.safetensors",
            port=6666,
            compile_model=True,
            cuda_visible_devices="3",
        )
        self.assertIn('/projects/cs_yifan16_chi/zlu31/conda_envs/gb-core/bin/python', script)
        self.assertNotIn('conda activate', script)
        self.assertNotIn('profile.d/conda.sh', script)
        self.assertIn('export CUDA_VISIBLE_DEVICES="3"', script)

    def test_validate_script_uses_env_python_directly(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "graspvla")
        script = _build_validate_script(
            cluster_config=cluster_config,
            method_config=method_config,
            port=6666,
            timeout_s=5,
            retries=3,
            retry_sleep_s=2,
        )
        self.assertIn('/projects/cs_yifan16_chi/zlu31/conda_envs/gb-core/bin/python', script)
        self.assertNotIn('conda activate', script)
        self.assertNotIn('profile.d/conda.sh', script)


if __name__ == "__main__":
    unittest.main()
