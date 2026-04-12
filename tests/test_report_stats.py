from __future__ import annotations

import unittest

from grasp_benchmark.report.stats import build_pair_matrix, exact_mcnemar, paired_bootstrap_delta, wilson_ci


class ReportStatsTest(unittest.TestCase):
    def test_wilson_ci_for_14_of_15_is_reasonable(self) -> None:
        low, high = wilson_ci(14, 15)
        self.assertGreater(low, 0.68)
        self.assertLess(low, 0.75)
        self.assertGreater(high, 0.97)
        self.assertLessEqual(high, 1.0)

    def test_exact_mcnemar_handles_known_small_case(self) -> None:
        self.assertEqual(exact_mcnemar(0, 0), 1.0)
        self.assertEqual(exact_mcnemar(0, 4), 0.125)

    def test_paired_bootstrap_delta_is_deterministic(self) -> None:
        ci_low, ci_high = paired_bootstrap_delta([(1, 0), (1, 0), (0, 1), (0, 1)], iterations=2000, seed=7)
        self.assertLessEqual(ci_low, 0.0)
        self.assertGreaterEqual(ci_high, 0.0)

    def test_build_pair_matrix_reports_missing_coverage(self) -> None:
        rows = [
            {"method_tier": "graspvla_official", "scene_recipe_id": "scene_a", "success": 1},
            {"method_tier": "cgn_full_modular", "scene_recipe_id": "scene_a", "success": 0},
            {"method_tier": "graspvla_official", "scene_recipe_id": "scene_b", "success": 1},
        ]
        matrix = build_pair_matrix(rows, method_a="graspvla_official", method_b="cgn_full_modular")
        self.assertEqual(matrix["pairs"], [(1, 0)])
        self.assertEqual(matrix["missing_for_a"], [])
        self.assertEqual(matrix["missing_for_b"], [("scene_b",)])


if __name__ == "__main__":
    unittest.main()
