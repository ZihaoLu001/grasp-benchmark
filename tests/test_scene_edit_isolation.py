from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from grasp_benchmark.audit.graspvla_scene_edit_isolation import (
    SceneEditProbeRow,
    compatible_benchmarks,
    compatible_tasks_per_benchmark,
    load_scene_edit_probe_summary,
    scene_edit_compatible_rows,
    scene_edit_gated_rows,
)


class SceneEditIsolationTest(unittest.TestCase):
    def test_probe_summary_loader_parses_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "probe.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "benchmark",
                        "task_id",
                        "task_name",
                        "instruction",
                        "seed_count",
                        "raw_state_compatible_count",
                        "processed_state_compatible_count",
                        "requires_official_scene_edit_for_all_seeds",
                        "raw_incompatible_seeds",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "benchmark": "libero_goal",
                        "task_id": "1",
                        "task_name": "goal_task",
                        "instruction": "pick up bowl",
                        "seed_count": "10",
                        "raw_state_compatible_count": "10",
                        "processed_state_compatible_count": "10",
                        "requires_official_scene_edit_for_all_seeds": "0",
                        "raw_incompatible_seeds": "",
                    }
                )
            rows = load_scene_edit_probe_summary(path)
        self.assertEqual(
            rows,
            [
                SceneEditProbeRow(
                    benchmark="libero_goal",
                    task_id=1,
                    task_name="goal_task",
                    instruction="pick up bowl",
                    seed_count=10,
                    raw_state_compatible_count=10,
                    processed_state_compatible_count=10,
                    requires_official_scene_edit_for_all_seeds=False,
                    raw_incompatible_seeds=tuple(),
                )
            ],
        )

    def test_compatible_and_gated_rows_are_split_correctly(self) -> None:
        rows = [
            SceneEditProbeRow(
                benchmark="libero_goal",
                task_id=1,
                task_name="goal1",
                instruction="pick up bowl",
                seed_count=10,
                raw_state_compatible_count=10,
                processed_state_compatible_count=10,
                requires_official_scene_edit_for_all_seeds=False,
                raw_incompatible_seeds=tuple(),
            ),
            SceneEditProbeRow(
                benchmark="libero_object",
                task_id=0,
                task_name="basket_task",
                instruction="pick up soup can",
                seed_count=10,
                raw_state_compatible_count=0,
                processed_state_compatible_count=10,
                requires_official_scene_edit_for_all_seeds=True,
                raw_incompatible_seeds=tuple(range(10)),
            ),
        ]
        self.assertEqual([row.benchmark for row in scene_edit_compatible_rows(rows)], ["libero_goal"])
        self.assertEqual([row.benchmark for row in scene_edit_gated_rows(rows)], ["libero_object"])
        self.assertEqual(compatible_benchmarks(rows), ["libero_goal"])
        self.assertEqual(compatible_tasks_per_benchmark(rows, ["libero_goal"]), 1)


if __name__ == "__main__":
    unittest.main()
