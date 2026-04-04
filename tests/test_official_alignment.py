from __future__ import annotations

import unittest

from grasp_benchmark.audit.graspvla_official_alignment import classify_parity_status
from grasp_benchmark.runners.graspvla_official_aligned import (
    OfficialLiberoTaskSpec,
    select_non_invalid_official_tasks,
)
from grasp_benchmark.run.sim import _remote_env_name
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


if __name__ == "__main__":
    unittest.main()
