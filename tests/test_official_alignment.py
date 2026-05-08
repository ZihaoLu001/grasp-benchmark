from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from grasp_benchmark.audit.graspvla_official_alignment import classify_parity_status
from grasp_benchmark.runners.graspvla_official_aligned import (
    OfficialLiberoTaskSpec,
    select_non_invalid_official_tasks,
)
from grasp_benchmark.run.sim import (
    _allocate_run_dir,
    _build_remote_command,
    _remote_env_name,
    _select_matrix_hosts,
    _wrap_scheduler_command,
)
from grasp_benchmark.config import load_named_config


class OfficialAlignmentSelectionTest(unittest.TestCase):
    def test_select_non_invalid_official_tasks_is_deterministic(self) -> None:
        candidates = {
            "libero_object": [
                {"benchmark": "libero_object", "task_id": 0, "task_name": "task0", "bddl_file": "a.bddl", "problem_folder": "p"},
                {"benchmark": "libero_object", "task_id": 1, "task_name": "task1", "bddl_file": "b.bddl", "problem_folder": "p"},
                {"benchmark": "libero_object", "task_id": 2, "task_name": "task2", "bddl_file": "c.bddl", "problem_folder": "p"},
            ],
            "libero_goal": [
                {"benchmark": "libero_goal", "task_id": 0, "task_name": "goal0", "bddl_file": "d.bddl", "problem_folder": "q"},
                {"benchmark": "libero_goal", "task_id": 1, "task_name": "goal1", "bddl_file": "e.bddl", "problem_folder": "q"},
            ],
        }

        def _is_valid(benchmark: str, task_id: int) -> tuple[bool, str, tuple[str, ...]]:
            if (benchmark, task_id) in {("libero_object", 0), ("libero_goal", 0)}:
                return False, "invalid", tuple()
            return True, f"pick up {benchmark}_{task_id}", (f"{benchmark}_{task_id}",)

        selected = select_non_invalid_official_tasks(candidates, 1, _is_valid)
        self.assertEqual(
            selected,
            [
                OfficialLiberoTaskSpec(
                    benchmark="libero_object",
                    task_id=1,
                    task_name="task1",
                    bddl_file="b.bddl",
                    problem_folder="p",
                    instruction="pick up libero_object_1",
                    obj_of_interest=("libero_object_1",),
                ),
                OfficialLiberoTaskSpec(
                    benchmark="libero_goal",
                    task_id=1,
                    task_name="goal1",
                    bddl_file="e.bddl",
                    problem_folder="q",
                    instruction="pick up libero_goal_1",
                    obj_of_interest=("libero_goal_1",),
                ),
            ],
        )

    def test_official_aligned_uses_official_sim_env(self) -> None:
        method_config = load_named_config("methods", "graspvla")
        self.assertEqual(_remote_env_name(method_config, "official_aligned_sim"), method_config["official_sim_env_name"])

    def test_shared_track_a_uses_shared_sim_env_when_configured(self) -> None:
        method_config = load_named_config("methods", "graspvla")
        self.assertEqual(_remote_env_name(method_config, "shared_track_a_sim"), method_config["shared_sim_env_name"])

    def test_classify_parity_status_can_be_reproducibility_limited(self) -> None:
        status = classify_parity_status(
            expected_episodes=65,
            coverage_counts={
                "V0_official_runner": 65,
                "V0_repeat_official_runner": 65,
                "V1_wrapper_official_parity": 65,
            },
            setup_errors={
                "V0_official_runner": "",
                "V0_repeat_official_runner": "",
                "V1_wrapper_official_parity": "",
            },
            v0_repeat_mismatch_count=2,
            v1_mismatch_count=2,
        )
        self.assertEqual(status["status_code"], "reproducibility_limited_parity")
        self.assertTrue(status["advance_to_attribution"])

    def test_classify_parity_status_is_strict_when_wrapper_has_zero_mismatch(self) -> None:
        status = classify_parity_status(
            expected_episodes=65,
            coverage_counts={
                "V0_official_runner": 65,
                "V0_repeat_official_runner": 65,
                "V1_wrapper_official_parity": 65,
            },
            setup_errors={
                "V0_official_runner": "",
                "V0_repeat_official_runner": "",
                "V1_wrapper_official_parity": "",
            },
            v0_repeat_mismatch_count=2,
            v1_mismatch_count=0,
        )
        self.assertEqual(status["status_code"], "strict_parity_passed")

    def test_classify_parity_status_fails_when_coverage_is_missing(self) -> None:
        status = classify_parity_status(
            expected_episodes=65,
            coverage_counts={
                "V0_official_runner": 65,
                "V0_repeat_official_runner": 64,
                "V1_wrapper_official_parity": 65,
            },
            setup_errors={
                "V0_official_runner": "",
                "V0_repeat_official_runner": "",
                "V1_wrapper_official_parity": "",
            },
            v0_repeat_mismatch_count=1,
            v1_mismatch_count=1,
        )
        self.assertEqual(status["status_code"], "parity_failed")
        self.assertFalse(status["advance_to_attribution"])

    def test_matrix_mode_honors_explicit_single_node_override(self) -> None:
        available_nodes = {
            "dispatch_hosts": ["lakeshore", "lakeshore_batch_gpu2"],
            "nodes": [
                {"host": "lakeshore", "status": "available", "gpu_names": ["A100"]},
                {"host": "lakeshore_batch_gpu2", "status": "available", "gpu_names": ["L40"]},
            ],
        }
        method_config = load_named_config("methods", "cgn")
        selected = _select_matrix_hosts(
            method_name="cgn",
            method_config=method_config,
            available_nodes=available_nodes,
            explicit_nodes="",
            explicit_node="lakeshore",
        )
        self.assertEqual(selected, ["lakeshore"])

    def test_matrix_mode_falls_back_to_lakeshore_dispatch_host(self) -> None:
        available_nodes = {
            "dispatch_hosts": ["lakeshore"],
            "nodes": [
                {"host": "lakeshore", "status": "warning", "gpu_names": ["slurm:batch_gpu2:gpu:1:slot0"]},
            ],
        }
        method_config = load_named_config("methods", "cgn")
        selected = _select_matrix_hosts(
            method_name="cgn",
            method_config=method_config,
            available_nodes=available_nodes,
            explicit_nodes="",
            explicit_node="",
        )
        self.assertEqual(selected, ["lakeshore"])

    def test_allocate_run_dir_appends_dup_suffix_on_collision(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = _allocate_run_dir(root, "example_run")
            second = _allocate_run_dir(root, "example_run")
            self.assertEqual(first.name, "example_run")
            self.assertEqual(second.name, "example_run__dup01")
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_lakeshore_scheduler_wraps_worker_in_srun(self) -> None:
        command = _wrap_scheduler_command(
            {
                "source_files": ["/etc/profile.d/modules.sh"],
                "module_loads": ["slurm/lakeshore/23.02.4"],
                "scheduler": {
                    "type": "slurm",
                    "account": "cs_yifan16_chi",
                    "partition": "batch_gpu2",
                    "gres": "gpu:1",
                    "cpus_per_task": 2,
                    "mem": "48G",
                    "time": "04:00:00",
                },
            },
            'cd "/repo" && python -m grasp_benchmark.run.worker --gpu-id "0"',
        )

        self.assertIn("module load slurm/lakeshore/23.02.4", command)
        self.assertIn("srun", command)
        self.assertIn("-A cs_yifan16_chi", command)
        self.assertIn("-p batch_gpu2", command)
        self.assertIn("--gres=gpu:1", command)
        self.assertIn("grasp_benchmark.run.worker", command)

    def test_remote_worker_command_preseeds_libero_config(self) -> None:
        command = _build_remote_command(
            cluster_config={
                "remote_root": "/projects/cs_yifan16_chi/zlu31/grasp-benchmark",
                "miniforge_root": "/projects/cs_yifan16_chi/zlu31/miniforge3",
                "conda_envs_dir": "/projects/cs_yifan16_chi/zlu31/conda_envs",
                "cuda_home": "/cm/shared/apps/cuda11.8/toolkit/11.8.0",
            },
            method_config={"name": "cgn", "env_name": "gb-cgn"},
            task_set="cgn_bottleneck_v2",
            sensor_config="track_a_dual_realsense",
            run_dir="/projects/cs_yifan16_chi/zlu31/grasp-benchmark/artifacts/runs/example",
            execution_mode="shared_track_a_sim",
            smoke_only=False,
            max_trials=1,
            cluster_config_name="lakeshore",
        )

        self.assertIn("> \"/projects/cs_yifan16_chi/zlu31/grasp-benchmark/artifacts/libero_config/config.yaml\"", command)
        self.assertIn("benchmark_root:", command)
        self.assertIn("datasets:", command)
        self.assertIn('export CUDA_HOME="/cm/shared/apps/cuda11.8/toolkit/11.8.0"', command)
        self.assertIn('export TORCH_EXTENSIONS_DIR="/projects/cs_yifan16_chi/zlu31/grasp-benchmark/artifacts/cache/torch_extensions"', command)
        self.assertIn('export HF_HOME="/projects/cs_yifan16_chi/zlu31/grasp-benchmark/artifacts/cache/huggingface"', command)
        self.assertIn("GB_FAULTHANDLER_PATH", command)
        self.assertIn("worker_stdout.log", command)


if __name__ == "__main__":
    unittest.main()
