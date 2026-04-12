from __future__ import annotations

import unittest

from grasp_benchmark.audit.graspvla_protocol_probe_v2 import _delta_rows


class ProtocolProbeV2Test(unittest.TestCase):
    def test_delta_rows_compare_each_factor_against_baseline(self) -> None:
        summary_rows = [
            {"variant": "P0_baseline_dual_attempt3_success15_hold2_jitter_none", "success_rate": 1.0},
            {"variant": "P1_front_only_duplicate", "success_rate": 0.75},
            {"variant": "P2_attempt_budget_1", "success_rate": 0.5},
            {"variant": "P3_relaxed_success_10cm_1s", "success_rate": 1.0},
            {"variant": "P4_low_camera_jitter", "success_rate": 0.875},
        ]
        rows = _delta_rows(summary_rows)
        self.assertEqual(
            [(row["factor"], row["success_rate_delta"]) for row in rows],
            [
                ("view_mode_effect", -0.25),
                ("attempt_budget_effect", -0.5),
                ("success_rule_effect", 0.0),
                ("camera_jitter_effect", -0.125),
            ],
        )


if __name__ == "__main__":
    unittest.main()
