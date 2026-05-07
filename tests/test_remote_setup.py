from __future__ import annotations

import unittest

from grasp_benchmark.config import load_named_config
from grasp_benchmark.prepare_cgn import _build_remote_script, _tf212_bootstrap_lines, _tf_ops_compile_lines
from grasp_benchmark.remote_setup import build_method_install_script


class RemoteSetupTest(unittest.TestCase):
    def test_graspvla_install_script_contains_requirements_install(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "graspvla")
        script, notes = build_method_install_script(cluster_config, method_config, "graspvla")
        self.assertIn("GraspVLA/requirements.txt", script)
        self.assertEqual(notes, [])

    def test_graspvla_playground_install_script_contains_official_setup_steps(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "graspvla")
        script, _ = build_method_install_script(
            cluster_config,
            method_config,
            "graspvla",
            include_playground=True,
        )
        self.assertIn("conda install -y -c conda-forge ffmpeg", script)
        self.assertIn("hydra-core==1.2.0", script)
        self.assertNotIn("third_party/upstreams/curobo", script)
        self.assertNotIn("PATCHED_FRANKA_YAML", script)

    def test_graspvla_playground_install_script_emits_separate_env_note(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "graspvla")
        _, notes = build_method_install_script(
            cluster_config,
            method_config,
            "graspvla",
            include_playground=True,
        )
        self.assertTrue(notes)
        self.assertIn("prepare_graspvla_playground", notes[0])

    def test_anygrasp_install_script_emits_manual_notes(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        method_config = load_named_config("methods", "anygrasp")
        script, notes = build_method_install_script(cluster_config, method_config, "anygrasp")
        self.assertIn("GroundingDINO", script)
        self.assertIn("--index-url https://download.pytorch.org/whl/cu118", script)
        self.assertIn('python -m pip install "numpy<2" "opencv-python==4.6.0.66"', script)
        self.assertIn("gsnet.so", script)
        self.assertTrue(notes)

    def test_cgn_install_script_installs_groundingdino_editable(self) -> None:
        cluster_config = load_named_config("cluster", "lakeshore")
        method_config = load_named_config("methods", "cgn")
        script, _ = build_method_install_script(cluster_config, method_config, "cgn")
        self.assertIn('python -m pip install -r "/projects/cs_yifan16_chi/zlu31/grasp-benchmark/third_party/upstreams/GroundingDINO/requirements.txt"', script)
        self.assertIn('python -m pip install -e "/projects/cs_yifan16_chi/zlu31/grasp-benchmark/third_party/upstreams/GroundingDINO" --no-build-isolation', script)

    def test_cgn_install_notes_point_to_tf212_runtime_prepare(self) -> None:
        cluster_config = load_named_config("cluster", "lakeshore")
        method_config = load_named_config("methods", "cgn")
        _, notes = build_method_install_script(cluster_config, method_config, "cgn")

        self.assertTrue(any("gb-cgn-tf212" in note for note in notes))
        self.assertTrue(any("--compile-tf-ops" in note for note in notes))

    def test_prepare_cgn_tf212_bootstrap_uses_h100_runtime_not_old_env_file(self) -> None:
        cluster_config = load_named_config("cluster", "lakeshore")
        method_config = load_named_config("methods", "cgn")
        env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["legacy_env_name"]}'
        bootstrap = "\n".join(_tf212_bootstrap_lines(env_prefix))
        compile_script = "\n".join(
            _tf_ops_compile_lines(
                env_prefix,
                cluster_config["cuda_home"],
                f'{cluster_config["remote_root"]}/third_party/upstreams/contact_graspnet',
                h100_runtime=True,
            )
        )

        self.assertIn("gb-cgn-tf212", bootstrap)
        self.assertIn('"tensorflow==2.12.0"', bootstrap)
        self.assertIn('"nvidia-cudnn-cu11==8.6.0.163"', bootstrap)
        self.assertIn("CUDNN_SYMLINK_OK", bootstrap)
        self.assertIn("-gencode=arch=compute_90,code=sm_90", compile_script)
        self.assertIn("-gencode=arch=compute_90,code=compute_90", compile_script)
        self.assertIn('-I"${CUDA_HOME}/include"', compile_script)
        self.assertIn("export compile_script", compile_script)
        self.assertNotIn("contact_graspnet_env.yml", bootstrap + compile_script)

    def test_prepare_cgn_probe_checks_configured_tf212_versions(self) -> None:
        cluster_config = load_named_config("cluster", "default")
        cluster_config = dict(cluster_config)
        cluster_config.pop("scheduler", None)
        cluster_config.pop("prepare_scheduler", None)
        method_config = load_named_config("methods", "cgn")
        script = _build_remote_script(
            cluster_config,
            method_config,
            bootstrap_legacy_env=False,
            compile_tf_ops=False,
        )

        self.assertIn('PY_EXPECTED="3.10"', script)
        self.assertIn('TF_EXPECTED="2.12.0"', script)
        self.assertIn("EXPECTED_TENSORFLOW", script)


if __name__ == "__main__":
    unittest.main()
