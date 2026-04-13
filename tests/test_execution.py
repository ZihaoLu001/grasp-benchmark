from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.adapters.base import AgentAdapter, AdapterExecutionError
from grasp_benchmark.config import load_named_config
from grasp_benchmark.execution import run_integration_suite
from grasp_benchmark.run.worker import _setup_failure_results
from grasp_benchmark.task_specs import expand_task_set
from grasp_benchmark.types import Action


class _SuccessfulAdapter(AgentAdapter):
    def setup(self, config: dict) -> None:
        self.config = config

    def reset(self, task_spec: dict) -> None:
        self.task_spec = task_spec

    def step(self, obs) -> Action:
        return Action(ee_delta=(0.0, 0.0, 0.01, 0.0, 0.0, 0.0), gripper=1)

    def close(self) -> None:
        return None


class _FailingAdapter(AgentAdapter):
    def setup(self, config: dict) -> None:
        self.config = config

    def reset(self, task_spec: dict) -> None:
        self.task_spec = task_spec

    def step(self, obs) -> Action:
        raise RuntimeError("planned adapter failure")

    def close(self) -> None:
        return None


class _StructuredFailingAdapter(AgentAdapter):
    def setup(self, config: dict) -> None:
        self.config = config

    def reset(self, task_spec: dict) -> None:
        self.task_spec = task_spec

    def step(self, obs) -> Action:
        raise AdapterExecutionError("missing AnyGrasp license", failure_stage="license")

    def close(self) -> None:
        return None


class ExecutionTest(unittest.TestCase):
    def test_integration_suite_writes_success_artifact(self) -> None:
        task_config = load_named_config("tasks", "track_a_v1")
        sensor_config = load_named_config("sensors", "track_a_dual_realsense")
        trial = expand_task_set(task_config, max_trials=1)
        adapter = _SuccessfulAdapter({"name": "dummy"}, sensor_config)
        adapter.setup({})

        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir = Path(tmp_dir) / "episodes"
            results = run_integration_suite(
                adapter=adapter,
                sensor_config=sensor_config,
                task_specs=trial,
                artifact_dir=artifact_dir,
                node="em14",
                commit="deadbeef",
            )

            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].success)
            self.assertEqual(results[0].attempts, 1)
            self.assertEqual(results[0].execution_mode, "integration_fixture")
            self.assertEqual(results[0].scene_recipe_id, trial[0].scene_recipe_id)
            self.assertEqual(results[0].replicate_index, trial[0].replicate_index)
            self.assertEqual(results[0].seed, trial[0].seed)
            self.assertTrue((Path(tmp_dir) / results[0].video_path).exists())

    def test_integration_suite_records_failure_reason(self) -> None:
        task_config = load_named_config("tasks", "track_a_v1")
        sensor_config = load_named_config("sensors", "track_a_dual_realsense")
        trial = expand_task_set(task_config, max_trials=1)
        adapter = _FailingAdapter({"name": "dummy"}, sensor_config)
        adapter.setup({})

        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir = Path(tmp_dir) / "episodes"
            results = run_integration_suite(
                adapter=adapter,
                sensor_config=sensor_config,
                task_specs=trial,
                artifact_dir=artifact_dir,
                node="em14",
                commit="deadbeef",
            )

            self.assertEqual(len(results), 1)
            self.assertFalse(results[0].success)
            self.assertEqual(results[0].failure_stage, "adapter_execution")
            self.assertIn("planned adapter failure", results[0].failure_reason)
            self.assertEqual(results[0].execution_mode, "integration_fixture")

    def test_integration_suite_preserves_structured_failure_stage(self) -> None:
        task_config = load_named_config("tasks", "track_a_v1")
        sensor_config = load_named_config("sensors", "track_a_dual_realsense")
        trial = expand_task_set(task_config, max_trials=1)
        adapter = _StructuredFailingAdapter({"name": "dummy"}, sensor_config)
        adapter.setup({})

        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir = Path(tmp_dir) / "episodes"
            results = run_integration_suite(
                adapter=adapter,
                sensor_config=sensor_config,
                task_specs=trial,
                artifact_dir=artifact_dir,
                node="em14",
                commit="deadbeef",
            )

            self.assertEqual(results[0].failure_stage, "license")
            self.assertIn("missing AnyGrasp license", results[0].failure_reason)

    def test_setup_failure_results_use_zero_attempts(self) -> None:
        task_config = load_named_config("tasks", "track_a_v1")
        trial = expand_task_set(task_config, max_trials=1)
        results = _setup_failure_results(
            adapter_name="anygrasp",
            sensor_stack="dual_fixed_realsense_rgbd",
            task_specs=trial,
            node="em14",
            commit="deadbeef",
            execution_mode="integration_fixture",
            exc=AdapterExecutionError("missing checkpoint", failure_stage="model_assets"),
        )
        self.assertEqual(results[0].attempts, 0)
        self.assertEqual(results[0].failure_stage, "model_assets")
        self.assertIn("missing checkpoint", results[0].failure_reason)
        self.assertEqual(results[0].execution_mode, "integration_fixture")
        self.assertEqual(results[0].scene_recipe_id, trial[0].scene_recipe_id)
        self.assertEqual(results[0].replicate_index, trial[0].replicate_index)
        self.assertEqual(results[0].seed, trial[0].seed)
        self.assertEqual(results[0].instruction_variant_id, trial[0].instruction_variant_id)
        self.assertEqual(results[0].instruction_variant_family, trial[0].instruction_variant_family)
        self.assertEqual(results[0].shift_family, trial[0].shift_family)
        self.assertEqual(results[0].shift_severity, trial[0].shift_severity)


if __name__ == "__main__":
    unittest.main()
