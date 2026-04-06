from __future__ import annotations

import re
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from grasp_benchmark.adapters.base import AdapterExecutionError
from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import PROJECT_ROOT
from grasp_benchmark.types import Action, Observation


@dataclass(slots=True)
class DetectionResult:
    bbox_xyxy: tuple[int, int, int, int]
    score: float
    label: str
    phrase: str
    prompt: str


@dataclass(slots=True)
class PerceptionResult:
    points: Any
    colors: Any
    segmap: Any
    mask: Any
    detection: DetectionResult | None
    debug: dict[str, Any]


def method_tier(method_config: dict[str, Any]) -> str:
    explicit = str(method_config.get("benchmark_method_tier", "")).strip()
    if explicit:
        return explicit
    name = str(method_config.get("name", "")).strip()
    if name == "graspvla":
        return "graspvla_official"
    if name == "cgn":
        return "cgn_raw_interim"
    if name == "anygrasp":
        return "anygrasp_full_modular"
    return "unknown_method_tier"


def _project_root(runtime_config: dict[str, Any]) -> Path:
    return Path(str(runtime_config.get("project_root", PROJECT_ROOT)))


def _normalize_label(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^a-z0-9\s]+", " ", lowered)
    return " ".join(lowered.split())


def _candidate_labels(task_set: str, object_group: str) -> list[str]:
    if not task_set or not object_group:
        return []
    task_config = load_named_config("tasks", task_set)
    raw_catalog = task_config.get("catalog", {})
    group_items = raw_catalog.get(object_group, [])
    labels = []
    for item in group_items:
        label = str(item.get("label") or item.get("id", "")).strip()
        if label:
            labels.append(label)
    return labels


def current_pose_from_obs(obs: Observation, np_module: Any) -> Any:
    state = obs.proprio.get("state")
    if state is None:
        history = obs.proprio.get("history")
        if isinstance(history, list) and history:
            state = history[-1]
    if state is None:
        raise AdapterExecutionError(
            "Shared modular planning requires proprio state in the observation.",
            failure_stage="observation",
        )
    pose = np_module.asarray(state, dtype=np_module.float32)
    if pose.shape[0] < 6:
        raise AdapterExecutionError(
            "Shared modular planning requires at least 6 end-effector values in proprio state.",
            failure_stage="observation",
        )
    return pose[:6]


def camera_target_in_world(obs: Observation, translation: Any, np_module: Any) -> Any | None:
    matrix = obs.extrinsics_front.get("matrix")
    if matrix is None:
        return None
    extrinsic = np_module.asarray(matrix, dtype=np_module.float32)
    if extrinsic.shape != (4, 4):
        return None
    point = np_module.asarray([translation[0], translation[1], translation[2], 1.0], dtype=np_module.float32)
    return (extrinsic @ point)[:3]


def _chunk_delta_actions(
    np_module: Any,
    start_xyz: Any,
    goal_xyz: Any,
    *,
    chunk_size_m: float,
    gripper: int,
) -> list[Action]:
    delta = np_module.asarray(goal_xyz, dtype=np_module.float32) - np_module.asarray(start_xyz, dtype=np_module.float32)
    max_component = float(np_module.max(np_module.abs(delta)))
    chunks = max(1, int(np_module.ceil(max_component / max(chunk_size_m, 1e-4))))
    step_delta = delta / float(chunks)
    return [
        Action(
            ee_delta=(
                float(step_delta[0]),
                float(step_delta[1]),
                float(step_delta[2]),
                0.0,
                0.0,
                0.0,
            ),
            gripper=gripper,
        )
        for _ in range(chunks)
    ]


def build_shared_pick_plan(
    obs: Observation,
    np_module: Any,
    *,
    translation_cam: Any,
    planner_config: dict[str, Any],
) -> list[Action]:
    target_world = camera_target_in_world(obs, translation_cam, np_module)
    if target_world is None:
        raise AdapterExecutionError(
            "Shared modular planner requires front-camera extrinsics to convert the target into world coordinates.",
            failure_stage="planner_failure",
        )

    current_pose = current_pose_from_obs(obs, np_module)
    current_xyz = current_pose[:3]
    approach_clearance_m = float(planner_config.get("approach_clearance_m", 0.08))
    grasp_offset_m = float(planner_config.get("grasp_offset_m", 0.015))
    lift_height_m = float(planner_config.get("lift_height_m", 0.18))
    chunk_size_m = float(planner_config.get("chunk_size_m", 0.04))
    close_steps = max(int(planner_config.get("close_steps", 2)), 1)

    approach_xyz = target_world.copy()
    approach_xyz[2] = max(float(current_xyz[2]), float(target_world[2]) + approach_clearance_m)
    grasp_xyz = target_world.copy()
    grasp_xyz[2] = max(0.02, float(target_world[2]) + grasp_offset_m)
    lift_xyz = grasp_xyz.copy()
    lift_xyz[2] = grasp_xyz[2] + lift_height_m

    plan: list[Action] = []
    plan.extend(_chunk_delta_actions(np_module, current_xyz, approach_xyz, chunk_size_m=chunk_size_m, gripper=1))
    plan.extend(_chunk_delta_actions(np_module, approach_xyz, grasp_xyz, chunk_size_m=chunk_size_m, gripper=1))
    for _ in range(close_steps):
        plan.append(Action(ee_delta=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), gripper=-1))
    plan.extend(_chunk_delta_actions(np_module, grasp_xyz, lift_xyz, chunk_size_m=chunk_size_m, gripper=-1))
    return plan


def point_cloud_from_mask(obs: Observation, mask: Any, np_module: Any) -> tuple[Any, Any]:
    depth = np_module.asarray(obs.depth_front, dtype=np_module.float32)
    colors = np_module.asarray(obs.rgb_front, dtype=np_module.float32)
    if depth.ndim != 2:
        raise AdapterExecutionError("Front depth frame must be a 2D array.", failure_stage="observation")
    if colors.ndim != 3 or colors.shape[:2] != depth.shape:
        raise AdapterExecutionError(
            "Front RGB frame must match the front depth resolution.",
            failure_stage="observation",
        )

    fx = float(obs.intrinsics_front.get("fx", 0.0))
    fy = float(obs.intrinsics_front.get("fy", 0.0))
    cx = float(obs.intrinsics_front.get("cx", depth.shape[1] / 2))
    cy = float(obs.intrinsics_front.get("cy", depth.shape[0] / 2))
    if fx <= 0 or fy <= 0:
        raise AdapterExecutionError(
            "Camera intrinsics must include positive fx/fy values.",
            failure_stage="observation",
        )

    valid_mask = np_module.asarray(mask, dtype=bool)
    valid_mask &= np_module.isfinite(depth) & (depth > 1e-6)
    if not np_module.any(valid_mask):
        raise AdapterExecutionError(
            "The modular perception mask does not contain any valid depth pixels.",
            failure_stage="segmentation_error",
        )

    ymap, xmap = np_module.indices(depth.shape)
    z = depth
    x = (xmap - cx) / fx * z
    y = (ymap - cy) / fy * z
    points = np_module.stack([x, y, z], axis=-1)[valid_mask].astype(np_module.float32)
    rgb = colors[valid_mask]
    if rgb.max(initial=0.0) > 1.0:
        rgb = rgb / 255.0
    return points, rgb.astype(np_module.float32)


def build_depth_mask_from_bbox(
    depth: Any,
    bbox_xyxy: tuple[int, int, int, int],
    np_module: Any,
    cv2_module: Any,
    *,
    min_pixels: int,
    depth_quantile: float,
    depth_band_m: float,
) -> tuple[Any, dict[str, Any]]:
    h, w = depth.shape
    x1, y1, x2, y2 = bbox_xyxy
    x1 = max(0, min(int(x1), w - 1))
    y1 = max(0, min(int(y1), h - 1))
    x2 = max(x1 + 1, min(int(x2), w))
    y2 = max(y1 + 1, min(int(y2), h))

    region = np_module.zeros_like(depth, dtype=bool)
    region[y1:y2, x1:x2] = True
    valid = region & np_module.isfinite(depth) & (depth > 1e-6)
    if not np_module.any(valid):
        raise AdapterExecutionError(
            "Detector box does not overlap any valid depth pixels.",
            failure_stage="segmentation_error",
        )

    depth_values = depth[valid]
    reference_depth = float(np_module.quantile(depth_values, depth_quantile))
    band = max(depth_band_m, reference_depth * 0.08)
    candidate = valid & (np_module.abs(depth - reference_depth) <= band)
    mask = _largest_component(candidate, cv2_module)
    if int(mask.sum()) < min_pixels:
        candidate = valid & (np_module.abs(depth - reference_depth) <= band * 2.0)
        mask = _largest_component(candidate, cv2_module)
    if int(mask.sum()) < min_pixels:
        mask = _largest_component(valid, cv2_module)
    if int(mask.sum()) < min_pixels:
        raise AdapterExecutionError(
            f"Segmented object mask is too small ({int(mask.sum())} pixels).",
            failure_stage="segmentation_error",
        )

    return mask.astype(bool), {
        "bbox_xyxy": [x1, y1, x2, y2],
        "reference_depth_m": round(reference_depth, 4),
        "depth_band_m": round(band, 4),
        "mask_pixels": int(mask.sum()),
    }


def build_foreground_mask(
    depth: Any,
    np_module: Any,
    cv2_module: Any,
    *,
    min_pixels: int,
    depth_quantile: float,
    depth_band_m: float,
) -> tuple[Any, dict[str, Any]]:
    valid = np_module.isfinite(depth) & (depth > 1e-6)
    if not np_module.any(valid):
        raise AdapterExecutionError(
            "No valid depth pixels are available for foreground segmentation.",
            failure_stage="segmentation_error",
        )
    depth_values = depth[valid]
    reference_depth = float(np_module.quantile(depth_values, depth_quantile))
    band = max(depth_band_m, reference_depth * 0.1)
    candidate = valid & (np_module.abs(depth - reference_depth) <= band)
    mask = _largest_component(candidate, cv2_module)
    if int(mask.sum()) < min_pixels:
        mask = _largest_component(valid, cv2_module)
    if int(mask.sum()) < min_pixels:
        raise AdapterExecutionError(
            f"Foreground segmentation is too small ({int(mask.sum())} pixels).",
            failure_stage="segmentation_error",
        )
    return mask.astype(bool), {
        "reference_depth_m": round(reference_depth, 4),
        "depth_band_m": round(band, 4),
        "mask_pixels": int(mask.sum()),
    }


def _largest_component(mask: Any, cv2_module: Any) -> Any:
    binary = mask.astype("uint8")
    component_count, labels, stats, _ = cv2_module.connectedComponentsWithStats(binary, connectivity=8)
    if component_count <= 1:
        return mask.astype(bool)
    best_label = 0
    best_area = 0
    for label in range(1, component_count):
        area = int(stats[label, cv2_module.CC_STAT_AREA])
        if area > best_area:
            best_area = area
            best_label = label
    return labels == best_label


class GroundingDinoDetector:
    def __init__(self, *, project_root: Path, config: dict[str, Any]) -> None:
        try:
            import numpy as np
            import torch
            from PIL import Image
            from torchvision.ops import box_convert
        except ImportError as exc:
            raise AdapterExecutionError(
                f"GroundingDINO dependencies are unavailable: {exc}",
                failure_stage="dependency_setup",
            ) from exc

        upstream_root = project_root / "third_party" / "upstreams" / "GroundingDINO"
        if not upstream_root.exists():
            raise AdapterExecutionError(
                f"Missing GroundingDINO upstream checkout: {upstream_root}",
                failure_stage="dependency_setup",
            )
        if str(upstream_root) not in sys.path:
            sys.path.insert(0, str(upstream_root))

        config_path = project_root / str(
            config.get("config_relpath", "third_party/upstreams/GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py")
        )
        checkpoint_path = project_root / str(
            config.get("checkpoint_relpath", "third_party/upstreams/GroundingDINO/weights/groundingdino_swint_ogc.pth")
        )
        checkpoint_url = str(
            config.get(
                "checkpoint_url",
                "https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth",
            )
        )
        _ensure_detector_checkpoint(checkpoint_path, checkpoint_url)

        from groundingdino.datasets import transforms as T
        from groundingdino.util.inference import load_model, predict

        preferred_device = str(config.get("device", "cuda")).strip().lower()
        device = "cuda" if preferred_device != "cpu" and torch.cuda.is_available() else "cpu"
        self._np = np
        self._torch = torch
        self._Image = Image
        self._box_convert = box_convert
        self._predict = predict
        self._transform = T.Compose(
            [
                T.RandomResize([800], max_size=1333),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
        self._model = load_model(str(config_path), str(checkpoint_path), device=device)
        self._device = device
        self._box_threshold = float(config.get("box_threshold", 0.3))
        self._text_threshold = float(config.get("text_threshold", 0.25))

    def detect_with_classes(self, image_rgb: Any, classes: list[str]) -> list[DetectionResult]:
        if not classes:
            return []
        caption = ". ".join(classes)
        image_pil = self._Image.fromarray(image_rgb.astype("uint8"), mode="RGB")
        image_tensor, _ = self._transform(image_pil, None)
        boxes, logits, phrases = self._predict(
            model=self._model,
            image=image_tensor,
            caption=caption,
            box_threshold=self._box_threshold,
            text_threshold=self._text_threshold,
            device=self._device,
        )
        if len(boxes) == 0:
            return []
        h, w = image_rgb.shape[:2]
        scaled = boxes * self._torch.tensor([w, h, w, h], dtype=boxes.dtype)
        xyxy = self._box_convert(boxes=scaled, in_fmt="cxcywh", out_fmt="xyxy").cpu().numpy()
        results: list[DetectionResult] = []
        normalized_classes = {_normalize_label(item): item for item in classes}
        for box, score, phrase in zip(xyxy, logits, phrases):
            phrase_norm = _normalize_label(str(phrase))
            matched_label = ""
            for class_norm, class_label in normalized_classes.items():
                if class_norm and class_norm in phrase_norm:
                    matched_label = class_label
                    break
            if not matched_label and len(classes) == 1:
                matched_label = classes[0]
            if not matched_label:
                continue
            x1, y1, x2, y2 = [int(round(float(item))) for item in box.tolist()]
            results.append(
                DetectionResult(
                    bbox_xyxy=(x1, y1, x2, y2),
                    score=float(score),
                    label=matched_label,
                    phrase=str(phrase),
                    prompt=caption,
                )
            )
        results.sort(key=lambda item: item.score, reverse=True)
        return results


def _ensure_detector_checkpoint(checkpoint_path: Path, checkpoint_url: str) -> None:
    if checkpoint_path.exists():
        return
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=checkpoint_path.suffix, dir=checkpoint_path.parent) as handle:
            tmp_path = Path(handle.name)
        urllib.request.urlretrieve(checkpoint_url, tmp_path)
        tmp_path.replace(checkpoint_path)
    except Exception as exc:
        raise AdapterExecutionError(
            f"Unable to download the GroundingDINO checkpoint from {checkpoint_url}: {exc}",
            failure_stage="model_assets",
        ) from exc


class SharedModularPerception:
    def __init__(self, *, method_config: dict[str, Any], runtime_config: dict[str, Any], np_module: Any, cv2_module: Any) -> None:
        self._method_config = method_config
        self._runtime_config = runtime_config
        self._np = np_module
        self._cv2 = cv2_module
        task_set = str(runtime_config.get("task_set", "")).strip()
        self._catalog_labels_by_group: dict[str, list[str]] = {}
        if task_set:
            task_config = load_named_config("tasks", task_set)
            for group_name in task_config.get("catalog", {}).keys():
                self._catalog_labels_by_group[group_name] = _candidate_labels(task_set, group_name)
        self._detector = GroundingDinoDetector(
            project_root=_project_root(runtime_config),
            config=dict(method_config.get("groundingdino", {})),
        )
        self._segmentation_config = dict(method_config.get("segmentation", {}))

    def observe(self, *, task_spec: dict[str, Any], instruction: str, obs: Observation) -> PerceptionResult:
        task_name = str(task_spec.get("task", ""))
        rgb = self._np.asarray(obs.rgb_front, dtype=self._np.uint8)
        depth = self._np.asarray(obs.depth_front, dtype=self._np.float32)

        detection: DetectionResult | None = None
        if task_name == "language_conditioned_single_target_pick":
            target_label = str(task_spec.get("object_label", "")).strip() or instruction
            detections = self._detector.detect_with_classes(rgb, [target_label])
            if not detections:
                raise AdapterExecutionError(
                    f"GroundingDINO failed to localize the requested target: {target_label}",
                    failure_stage="grounding_error",
                )
            detection = detections[0]
            mask, seg_debug = build_depth_mask_from_bbox(
                depth,
                detection.bbox_xyxy,
                self._np,
                self._cv2,
                min_pixels=int(self._segmentation_config.get("min_pixels", 64)),
                depth_quantile=float(self._segmentation_config.get("depth_quantile", 0.2)),
                depth_band_m=float(self._segmentation_config.get("depth_band_m", 0.03)),
            )
        else:
            labels = list(self._catalog_labels_by_group.get(str(task_spec.get("object_group", "")), []))
            detections = self._detector.detect_with_classes(rgb, labels)
            if detections:
                detection = detections[0]
                mask, seg_debug = build_depth_mask_from_bbox(
                    depth,
                    detection.bbox_xyxy,
                    self._np,
                    self._cv2,
                    min_pixels=int(self._segmentation_config.get("min_pixels", 64)),
                    depth_quantile=float(self._segmentation_config.get("depth_quantile", 0.2)),
                    depth_band_m=float(self._segmentation_config.get("depth_band_m", 0.03)),
                )
            else:
                mask, seg_debug = build_foreground_mask(
                    depth,
                    self._np,
                    self._cv2,
                    min_pixels=int(self._segmentation_config.get("min_pixels", 64)),
                    depth_quantile=float(self._segmentation_config.get("fallback_depth_quantile", 0.1)),
                    depth_band_m=float(self._segmentation_config.get("fallback_depth_band_m", 0.04)),
                )
        points, colors = point_cloud_from_mask(obs, mask, self._np)
        segmap = mask.astype("uint8")
        debug = dict(seg_debug)
        if detection is not None:
            debug["detection"] = {
                "bbox_xyxy": list(detection.bbox_xyxy),
                "score": round(detection.score, 4),
                "label": detection.label,
                "phrase": detection.phrase,
            }
        return PerceptionResult(
            points=points,
            colors=colors,
            segmap=segmap,
            mask=mask,
            detection=detection,
            debug=debug,
        )
