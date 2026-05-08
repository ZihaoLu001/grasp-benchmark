from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from grasp_benchmark.adapters.base import AdapterExecutionError
from grasp_benchmark.adapters.modular_adapters import (
    _cgn_runner_trace_summary,
    _legacy_cuda_visible_devices,
    _legacy_ld_library_path,
    _legacy_runner_timeout_s,
)
from grasp_benchmark.adapters.modular_components import DetectionResult, SharedModularPerception
from grasp_benchmark.config import load_named_config
from grasp_benchmark.methods import UPSTREAMS_BY_NAME
from grasp_benchmark.runners.contact_graspnet import _raw_point_segments
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


class FailingDetector:
    def __init__(self, **_: object) -> None:
        raise AssertionError("GroundingDINO should not be initialized for oracle official-depth+segmap CGN.")


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
        self.assertTrue(method_config["planner"]["validate_gripper_opening"])
        self.assertLessEqual(method_config["planner"]["max_gripper_opening_m"], 0.08)
        self.assertTrue(method_config["planner"]["reject_below_table_grasps"])
        self.assertEqual(
            method_config["planner"]["grasp_frame_to_tcp_status"],
            "explicit_identity_shared_lane_not_native_calibration",
        )

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
        self.assertEqual(override["native_top_k"], 20)
        self.assertEqual(override["planner_overrides"]["candidate_top_k"], 20)

    def test_cgn_official_depth_segmap_override_uses_oracle_segmap_not_multiview(self) -> None:
        method_config = load_named_config("methods", "cgn")
        override = method_config["task_runtime_overrides"]["track_b_cgn_official_depth_segmap_v1"]

        self.assertEqual(override["official_input_contract"], "official_depth_k_segmap")
        self.assertEqual(override["segmentation_mode"], "oracle_gt")
        self.assertFalse(override["native_multiview_fusion"])
        self.assertEqual(override["native_top_k"], 20)
        self.assertEqual(
            override["planner_overrides"]["grasp_frame_to_tcp_status"],
            "official_contact_graspnet_pose_with_benchmark_franka_execution",
        )

    def test_oracle_official_depth_segmap_mode_does_not_require_grounding_dino(self) -> None:
        obs = _observation()
        mask = np.zeros((16, 16), dtype=bool)
        mask[4:12, 4:12] = True
        obs.proprio["sim_gt_target_mask_front"] = mask

        with patch("grasp_benchmark.adapters.modular_components.GroundingDinoDetector", FailingDetector):
            perception = SharedModularPerception(
                method_config=load_named_config("methods", "cgn"),
                runtime_config={
                    "task_set": "track_b_cgn_official_depth_segmap_v1",
                    "project_root": str(REPO_ROOT),
                    "segmentation_mode": "oracle_gt",
                    "native_multiview_fusion": False,
                },
                np_module=np,
                cv2_module=FakeCV2,
            )
            result = perception.observe(
                task_spec={
                    "task": "language_conditioned_single_target_pick",
                    "object_label": "banana",
                    "object_group": "native_opaque_cal",
                },
                instruction="pick up the banana",
                obs=obs,
            )

        self.assertEqual(result.debug["segmentation_source"], "oracle_gt")
        self.assertEqual(int(result.segmap.sum()), 64)

    def test_native_multiview_fusion_preserves_target_segment_for_official_cgn_filtering(self) -> None:
        with patch("grasp_benchmark.adapters.modular_components.GroundingDinoDetector", FakeDetector):
            perception = SharedModularPerception(
                method_config=load_named_config("methods", "cgn"),
                runtime_config={
                    "task_set": "track_b_cgn_native_v2",
                    "project_root": str(REPO_ROOT),
                    "native_multiview_fusion": True,
                },
                np_module=np,
                cv2_module=FakeCV2,
            )
            result = perception.observe(
                task_spec={
                    "task": "language_conditioned_single_target_pick",
                    "object_label": "banana",
                    "object_group": "native_opaque_cal",
                },
                instruction="pick up the banana",
                obs=_observation(),
            )

        self.assertIsNotNone(result.segment_ids)
        self.assertEqual(len(result.segment_ids), result.points.shape[0])
        self.assertEqual(set(np.asarray(result.segment_ids).tolist()), {1})
        self.assertEqual(result.debug["segment_filtering"], "single_target_segment_preserved_for_cgn_local_regions")

    def test_raw_point_runner_builds_official_object_segments_from_segment_ids(self) -> None:
        points = np.asarray(
            [
                [0.0, 0.0, 0.5],
                [0.01, 0.0, 0.5],
                [0.5, 0.0, 0.8],
            ],
            dtype=np.float32,
        )
        segments = _raw_point_segments(points, np.asarray([1, 1, 2], dtype=np.int32))

        self.assertEqual(sorted(segments), [1, 2])
        self.assertEqual(segments[1].shape, (2, 3))
        self.assertEqual(segments[2].shape, (1, 3))

    def test_cgn_runner_trace_summary_preserves_official_filtering_evidence(self) -> None:
        summary = _cgn_runner_trace_summary(
            [
                {"stage": "tensorflow_imported", "gpu_count": 1},
                {
                    "stage": "input_loaded",
                    "input_contract": "official_depth_k_segmap",
                    "use_raw_points": True,
                    "points_shape": [128, 3],
                    "segment_ids_shape": [128],
                    "depth_shape": [256, 256],
                    "K_shape": [3, 3],
                    "segmap_shape": [256, 256],
                    "has_rgb": True,
                },
                {
                    "stage": "point_cloud_ready",
                    "pc_full_shape": [128, 3],
                    "segment_shapes": {"1": [128, 3]},
                },
                {
                    "stage": "predict_scene_grasps_start",
                    "local_regions": True,
                    "filter_grasps": True,
                    "forward_passes": 1,
                },
                {
                    "stage": "predict_scene_grasps_done",
                    "grasp_counts": {"1": 5},
                    "score_counts": {"1": 5},
                },
            ]
        )

        self.assertEqual(summary["tensorflow_gpu_count"], 1)
        self.assertEqual(summary["input_contract"], "official_depth_k_segmap")
        self.assertTrue(summary["use_raw_points"])
        self.assertEqual(summary["segment_ids_shape"], [128])
        self.assertEqual(summary["depth_shape"], [256, 256])
        self.assertEqual(summary["K_shape"], [3, 3])
        self.assertEqual(summary["segmap_shape"], [256, 256])
        self.assertTrue(summary["has_rgb"])
        self.assertEqual(summary["segment_shapes"], {"1": [128, 3]})
        self.assertTrue(summary["local_regions"])
        self.assertTrue(summary["filter_grasps"])
        self.assertEqual(summary["grasp_counts"], {"1": 5})

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
