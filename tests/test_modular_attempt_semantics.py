from __future__ import annotations

import unittest

import numpy as np

from grasp_benchmark.adapters.modular_adapters import _SharedModularAdapterBase
from grasp_benchmark.adapters.modular_components import PerceptionResult
from grasp_benchmark.types import Observation


def _observation() -> Observation:
    return Observation(
        rgb_front=np.zeros((4, 4, 3), dtype=np.uint8),
        rgb_side=np.zeros((4, 4, 3), dtype=np.uint8),
        depth_front=np.zeros((4, 4), dtype=np.float32),
        depth_side=np.zeros((4, 4), dtype=np.float32),
        intrinsics_front={"fx": 100.0, "fy": 100.0, "cx": 2.0, "cy": 2.0},
        intrinsics_side={"fx": 100.0, "fy": 100.0, "cx": 2.0, "cy": 2.0},
        extrinsics_front={"matrix": np.eye(4, dtype=np.float32).tolist()},
        extrinsics_side={"matrix": np.eye(4, dtype=np.float32).tolist()},
        proprio={
            "state": [0.4, 0.0, 0.35, 3.14, 0.0, 0.0, 1.0],
            "history": [[0.4, 0.0, 0.35, 3.14, 0.0, 0.0, 1.0]],
            "robot_base_pose_world": [
                [1.0, 0.0, 0.0, -0.6],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        },
        instruction="pick up banana",
        timestamp=0.0,
    )


class _StubModularAdapter(_SharedModularAdapterBase):
    adapter_kind = "stub"

    def setup(self, config: dict) -> None:
        self.runtime_config = config
        self._np = np
        self._instruction = ""
        self._pending_actions = []
        self._debug_dump_dir = None
        self._planner_config = dict(self.method_config.get("planner", {}))
        self._single_plan_per_attempt = bool(self._planner_config.get("single_plan_per_attempt", False))
        self._attempt_complete = False
        self._perception = type(
            "_StubPerception",
            (),
            {
                "observe": staticmethod(
                    lambda **_kwargs: PerceptionResult(
                        points=np.zeros((1, 3), dtype=np.float32),
                        colors=np.zeros((1, 3), dtype=np.float32),
                        segmap=np.zeros((4, 4), dtype=np.uint8),
                        mask=np.ones((4, 4), dtype=np.uint8),
                        detection=None,
                        debug={},
                    )
                )
            },
        )()

    def _proposal_payload(self, obs: Observation, perception: PerceptionResult) -> dict:
        return {"best_translation": [0.05, -0.02, 0.12], "best_score": 1.0}

    def close(self) -> None:
        return None


class _CandidateRetryAdapter(_StubModularAdapter):
    def _proposal_payload(self, obs: Observation, perception: PerceptionResult) -> dict:
        bad_grasp = np.eye(4, dtype=np.float32)
        bad_grasp[2, 3] = -0.05
        return {
            "candidate_grasps": [
                {
                    "best_translation": [0.0, 0.0, -0.05],
                    "best_grasp": bad_grasp.tolist(),
                    "best_score": 0.9,
                    "proposal_source": "bad_low_grasp",
                },
                {
                    "best_translation": [0.05, -0.02, 0.12],
                    "best_score": 0.8,
                    "proposal_source": "fallback_translation",
                },
            ]
        }


class ModularAttemptSemanticsTest(unittest.TestCase):
    def test_single_plan_per_attempt_flips_complete_after_last_action(self) -> None:
        adapter = _StubModularAdapter(
            method_config={"name": "stub", "planner": {"single_plan_per_attempt": True}},
            sensor_config={},
        )
        adapter.setup({})
        adapter.reset({"instruction": "pick up banana"})

        obs = _observation()
        actions = []
        while not adapter.attempt_complete():
            actions.append(adapter.step(obs))

        self.assertGreater(len(actions), 0)
        self.assertTrue(adapter.attempt_complete())

    def test_planner_retries_next_candidate_when_first_pose_is_below_table(self) -> None:
        adapter = _CandidateRetryAdapter(
            method_config={
                "name": "stub",
                "planner": {
                    "single_plan_per_attempt": True,
                    "reject_below_table_grasps": True,
                    "grasp_min_z_m": 0.02,
                },
            },
            sensor_config={},
        )
        adapter.setup({})
        adapter.reset({"instruction": "pick up banana"})

        action = adapter.step(_observation())
        debug = adapter.latest_debug_payload()

        self.assertGreater(action.ee_delta[0], 0.0)
        self.assertEqual(debug["planner"]["proposal_source"], "fallback_translation")
        self.assertIn("skipped_planner_candidates", debug["planner"])


if __name__ == "__main__":
    unittest.main()
