from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
