from __future__ import annotations

import unittest

from grasp_benchmark.audit.graspvla_success_rule_isolation import _delta_rows


class SuccessRuleIsolationTest(unittest.TestCase):
    def test_delta_rows_split_threshold_and_hold_effects(self) -> None:
        summary_rows = [
            {"variant": "S0_env_done", "success_rate": 1.0},
            {"variant": "S1_lift10_hold1", "success_rate": 0.9},
            {"variant": "S2_lift15_hold1", "success_rate": 0.8},
            {"variant": "S3_lift15_hold10", "success_rate": 0.7},
        ]
        rows = _delta_rows(summary_rows)
        self.assertEqual(
            [(row["factor"], row["success_rate_delta"]) for row in rows],
            [
                ("goal_vs_minimal_lift_rule", -0.1),
                ("lift_threshold_effect", -0.1),
                ("hold_time_effect", -0.1),
            ],
        )


if __name__ == "__main__":
    unittest.main()
