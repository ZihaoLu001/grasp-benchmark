from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from grasp_benchmark.adapters.base import AdapterExecutionError
from grasp_benchmark.adapters.modular_adapters import (
    _legacy_cuda_visible_devices,
    _legacy_ld_library_path,
    _legacy_runner_timeout_s,
)
from grasp_benchmark.adapters.modular_components import DetectionResult, SharedModularPerception
from grasp_benchmark.config import load_named_config
from grasp_benchmark.methods import UPSTREAMS_BY_NAME
from grasp_benchmark.types import Observation


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeCV2:
    CC_STAT_AREA = 4

    @staticmethod
    def connectedComponentsWithStats(binary: np.ndarray, connectivity: int = 8) -> tuple[int, np.ndarray, np.ndarray, None]:
        labels = np.where(binary > 0, 1, 0).astype(np.int32)
        area = int((binary > 0).sum())
        if area <= 0:
            return 1, labels, np.zeros((1, 5), dtype=np.int32), None
        stats = np.zeros((2, 5), dtype=np.int32)
        stats[1, FakeCV2.CC_STAT_AREA] = area
        return 2, labels, stats, None


class FakeDetector:
    calls: list[list[str]] = []
    detections: list[DetectionResult] = []

    def __init__(self, **_: object) -> None:
        return None

    def detect_with_classes(self, image_rgb: np.ndarray, classes: list[str]) -> list[DetectionResult]:
        self.calls.append(list(classes))
        return list(self.detections)


def _observation() -> Observation:
    rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    rgb[:, :, 0] = 128
    depth = np.ones((16, 16), dtype=np.float32)
    intrinsics = {"fx": 100.0, "fy": 100.0, "cx": 8.0, "cy": 8.0}
    extrinsic = {"matrix": np.eye(4, dtype=np.float32)}
    return Observation(
        rgb_front=rgb,
        rgb_side=rgb.copy(),
        depth_front=depth,
        depth_side=depth.copy(),
        intrinsics_front=intrinsics,
        intrinsics_side=intrinsics,
        extrinsics_front=extrinsic,
        extrinsics_side=extrinsic,
        instruction="pick up the banana",
    )


def _perception(task_set: str = "track_a_cal_v3") -> SharedModularPerception:
    return SharedModularPerception(
        method_config=load_named_config("methods", "cgn"),
        runtime_config={"task_set": task_set, "project_root": str(REPO_ROOT)},
        np_module=np,
        cv2_module=FakeCV2,
    )


class CgnPipelineContractTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeDetector.calls = []
        FakeDetector.detections = [
            DetectionResult(
                bbox_xyxy=(2, 2, 14, 14),
                score=0.91,
                label="banana",
                phrase="banana",
                prompt="banana",
            )
        ]

    def test_cgn_method_config_declares_grounding_dino_upstream(self) -> None:
        method_config = load_named_config("methods", "cgn")
        self.assertIn("GroundingDINO", method_config["upstreams"])
        self.assertIn("groundingdino_swint_ogc.pth", method_config["groundingdino"]["checkpoint_relpath"])
        self.assertEqual(method_config["groundingdino"]["device"], "cuda")
        self.assertEqual(method_config["legacy_env_name"], "gb-cgn-tf212")
        self.assertEqual(method_config["legacy_runtime"]["tensorflow_version"], "2.12.0")
        self.assertIn("-gencode=arch=compute_90,code=sm_90", method_config["legacy_runtime"]["custom_op_arch_flags"])
        self.assertGreaterEqual(method_config["planner"]["candidate_top_k"], 5)
        self.assertTrue(method_config["planner"]["reject_below_table_grasps"])

    def test_curobo_upstream_is_pinned_to_playground_compatible_api(self) -> None:
        self.assertEqual(UPSTREAMS_BY_NAME["curobo"].ref, "v0.7.8")

    def test_language_task_uses_grounding_dino_before_cgn_proposal(self) -> None:
        with patch("grasp_benchmark.adapters.modular_components.GroundingDinoDetector", FakeDetector):
            result = _perception().observe(
                task_spec={
                    "task": "language_conditioned_single_target_pick",
                    "object_label": "banana",
                    "object_group": "native_opaque_cal",
                },
                instruction="pick up the banana",
                obs=_observation(),
            )

        self.assertEqual(FakeDetector.calls, [["banana"]])
        self.assertIsNotNone(result.detection)
        self.assertGreaterEqual(int(result.mask.sum()), 96)
        self.assertEqual(result.debug["detection"]["label"], "banana")

    def test_language_task_detector_miss_is_grounding_error(self) -> None:
        FakeDetector.detections = []
        with patch("grasp_benchmark.adapters.modular_components.GroundingDinoDetector", FakeDetector):
            with self.assertRaises(AdapterExecutionError) as exc_info:
                _perception().observe(
                    task_spec={
                        "task": "language_conditioned_single_target_pick",
                        "object_label": "banana",
                        "object_group": "native_opaque_cal",
                    },
                    instruction="pick up the banana",
                    obs=_observation(),
                )

        self.assertEqual(exc_info.exception.failure_stage, "grounding_error")

    def test_arbitrary_task_tries_grounding_dino_then_foreground_fallback(self) -> None:
        FakeDetector.detections = []
        with patch("grasp_benchmark.adapters.modular_components.GroundingDinoDetector", FakeDetector):
            result = _perception().observe(
                task_spec={
                    "task": "arbitrary_grasping_common_opaque",
                    "object_group": "native_opaque_cal",
                },
                instruction="pick up any object",
                obs=_observation(),
            )

        self.assertIn("banana", FakeDetector.calls[0])
        self.assertIn("power drill", FakeDetector.calls[0])
        self.assertIsNone(result.detection)
        self.assertGreaterEqual(int(result.mask.sum()), 96)

    def test_cgn_native_v2_enables_multiview_fusion_override(self) -> None:
        method_config = load_named_config("methods", "cgn")
        override = method_config["task_runtime_overrides"]["track_b_cgn_native_v2"]
        self.assertTrue(override["native_multiview_fusion"])
        self.assertEqual(override["native_top_k"], 5)

    def test_cgn_legacy_bridge_keeps_cuda_and_env_libraries_visible(self) -> None:
        ld_library_path = _legacy_ld_library_path(
            Path("/projects/cs_yifan16_chi/zlu31/conda_envs/gb-cgn-tf212"),
            "/cm/shared/apps/cuda11.8/toolkit/11.8.0",
        )

        self.assertIn("/cm/shared/apps/cuda11.8/toolkit/11.8.0/lib64", ld_library_path)
        self.assertIn("/projects/cs_yifan16_chi/zlu31/conda_envs/gb-cgn-tf212/lib", ld_library_path)
        self.assertIn("/projects/cs_yifan16_chi/zlu31/conda_envs/gb-cgn-tf212/lib/python3.10/site-packages/nvidia/cudnn/lib", ld_library_path)
        self.assertIn("/usr/lib64", ld_library_path)
        self.assertTrue(ld_library_path.endswith("${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"))

    def test_cgn_legacy_bridge_preserves_slurm_visible_gpu_mapping(self) -> None:
        self.assertEqual(
            _legacy_cuda_visible_devices("3", {"CUDA_VISIBLE_DEVICES": "0"}),
            "0",
        )
        self.assertEqual(
            _legacy_cuda_visible_devices("3", {}),
            "3",
        )

    def test_cgn_legacy_timeout_ms_is_converted_to_seconds(self) -> None:
        self.assertEqual(_legacy_runner_timeout_s({"timeout_ms": 10000}), 300.0)
        self.assertEqual(_legacy_runner_timeout_s({"timeout_ms": 600000}), 600.0)

    def test_cgn_tf_ops_sources_are_tf212_status_compatible(self) -> None:
        for relpath in (
            "third_party/upstreams/contact_graspnet/pointnet2/tf_ops/sampling/tf_sampling.cpp",
            "third_party/upstreams/contact_graspnet/pointnet2/tf_ops/grouping/tf_grouping.cpp",
            "third_party/upstreams/contact_graspnet/pointnet2/tf_ops/3d_interpolation/tf_interpolate.cpp",
        ):
            text = (REPO_ROOT / relpath).read_text(encoding="utf-8")
            self.assertIn("CGN_TF_OK_STATUS", text, relpath)
            self.assertNotIn("return Status::OK();", text, relpath)


if __name__ == "__main__":
    unittest.main()
