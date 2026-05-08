from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np


def _raw_point_segments(points: np.ndarray, segment_ids: np.ndarray | None) -> dict[int, np.ndarray]:
    pc_full = np.asarray(points, dtype=np.float32)
    if pc_full.ndim != 2 or pc_full.shape[1] < 3 or pc_full.shape[0] == 0:
        return {}
    if segment_ids is None:
        return {1: pc_full[:, :3]}
    ids = np.asarray(segment_ids).reshape(-1)
    if ids.shape[0] != pc_full.shape[0]:
        return {1: pc_full[:, :3]}
    segments: dict[int, np.ndarray] = {}
    for raw_id in sorted(set(int(item) for item in ids.tolist() if int(item) > 0)):
        segment = pc_full[ids == raw_id, :3]
        if segment.size:
            segments[int(raw_id)] = segment.astype(np.float32)
    return segments or {1: pc_full[:, :3]}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Headless Contact-GraspNet inference helper.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--upstream-root", required=True)
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--forward-passes", type=int, default=1)
    parser.add_argument("--z-min", type=float, default=0.2)
    parser.add_argument("--z-max", type=float, default=1.1)
    parser.add_argument("--top-k", type=int, default=1)
    parser.add_argument("--cuda-visible-devices", default="0")
    parser.add_argument("--trace-json", default="", help="Optional path for stage timing diagnostics.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    upstream_root = Path(args.upstream_root).resolve()
    checkpoint_dir = Path(args.checkpoint_dir).resolve()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    trace_path = Path(args.trace_json).resolve() if args.trace_json else None
    started_at = time.perf_counter()
    trace_events: list[dict[str, object]] = []

    def trace(stage: str, **fields: object) -> None:
        event = {"stage": stage, "elapsed_s": round(time.perf_counter() - started_at, 3), **fields}
        trace_events.append(event)
        print("__CGN_TRACE__ " + json.dumps(event, sort_keys=True), file=sys.stderr, flush=True)

    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    sys.path.insert(0, str(upstream_root))
    sys.path.insert(0, str(upstream_root / "contact_graspnet"))

    os.environ.setdefault("CUDA_VISIBLE_DEVICES", str(args.cuda_visible_devices))
    trace(
        "start",
        cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        upstream_root=str(upstream_root),
        checkpoint_dir=str(checkpoint_dir),
    )

    import tensorflow.compat.v1 as tf

    tf.disable_eager_execution()
    physical_devices = tf.config.experimental.list_physical_devices("GPU")
    for device in physical_devices:
        try:
            tf.config.experimental.set_memory_growth(device, True)
        except Exception:
            pass
    trace("tensorflow_imported", gpu_count=len(physical_devices), gpus=[str(device) for device in physical_devices])

    import config_utils
    from contact_grasp_estimator import GraspEstimator
    trace("upstream_imported")

    payload = np.load(input_path, allow_pickle=False)
    use_raw_points = "points" in payload.files
    points = payload["points"] if use_raw_points else None
    colors = payload["colors"] if "colors" in payload.files else None
    segment_ids = payload["segment_ids"] if "segment_ids" in payload.files else None
    depth = payload["depth"] if "depth" in payload.files else None
    K = payload["K"] if "K" in payload.files else None
    rgb = payload["rgb"] if "rgb" in payload.files else None
    segmap = payload["segmap"] if "segmap" in payload.files else None
    trace(
        "input_loaded",
        files=list(payload.files),
        input_contract="raw_points_segment_ids" if use_raw_points else "official_depth_k_segmap",
        use_raw_points=use_raw_points,
        points_shape=list(points.shape) if points is not None else None,
        segment_ids_shape=list(segment_ids.shape) if segment_ids is not None else None,
        depth_shape=list(depth.shape) if depth is not None else None,
        K_shape=list(K.shape) if K is not None else None,
        segmap_shape=list(segmap.shape) if segmap is not None else None,
        has_rgb=rgb is not None,
    )

    global_config = config_utils.load_config(str(checkpoint_dir), batch_size=args.forward_passes, arg_configs=[])
    trace(
        "config_loaded",
        raw_num_points=global_config.get("DATA", {}).get("raw_num_points"),
        num_point=global_config.get("DATA", {}).get("num_point"),
    )
    grasp_estimator = GraspEstimator(global_config)
    grasp_estimator.build_network()
    trace("network_built")
    saver = tf.train.Saver(save_relative_paths=True)

    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    config.allow_soft_placement = True
    sess = tf.Session(config=config)
    trace("session_created")
    try:
        grasp_estimator.load_weights(sess, saver, str(checkpoint_dir), mode="test")
        trace("weights_loaded")
        if use_raw_points:
            pc_full = points.astype(np.float32)
            pc_segments = _raw_point_segments(pc_full, segment_ids)
        else:
            pc_full, pc_segments, _ = grasp_estimator.extract_point_clouds(
                depth,
                K,
                segmap=segmap,
                rgb=rgb,
                z_range=[args.z_min, args.z_max],
            )
        trace(
            "point_cloud_ready",
            pc_full_shape=list(pc_full.shape),
            segment_shapes={str(key): list(value.shape) for key, value in pc_segments.items()},
        )
        trace(
            "predict_scene_grasps_start",
            local_regions=bool(pc_segments),
            filter_grasps=bool(pc_segments),
            forward_passes=args.forward_passes,
        )
        pred_grasps_cam, scores, contact_pts, gripper_openings = grasp_estimator.predict_scene_grasps(
            sess,
            pc_full,
            pc_segments=pc_segments,
            local_regions=bool(pc_segments),
            filter_grasps=bool(pc_segments),
            forward_passes=args.forward_passes,
        )
        trace(
            "predict_scene_grasps_done",
            grasp_counts={str(key): int(len(value)) for key, value in pred_grasps_cam.items()},
            score_counts={str(key): int(len(value)) for key, value in scores.items()},
        )
        best_key = -1
        best_score = None
        for key, candidate_scores in scores.items():
            if len(candidate_scores) == 0:
                continue
            score = float(np.max(candidate_scores))
            if best_score is None or score > best_score:
                best_score = score
                best_key = key
        candidates = pred_grasps_cam.get(best_key, np.array([]))
        candidate_scores = scores.get(best_key, np.array([]))
        if len(candidates) == 0 or len(candidate_scores) == 0:
            result = {
                "ok": False,
                "failure_stage": "grasp_proposal",
                "failure_reason": "Contact-GraspNet returned zero grasp proposals.",
            }
        else:
            ranking = np.argsort(candidate_scores)[::-1]
            best_idx = int(ranking[0])
            best_grasp = candidates[best_idx]
            top_k = max(int(args.top_k), 1)
            candidate_payloads = []
            candidate_contact_pts = np.asarray(contact_pts.get(best_key, np.array([])))
            if candidate_contact_pts.ndim == 1 and candidate_contact_pts.size == 3:
                candidate_contact_pts = candidate_contact_pts.reshape(1, 3)
            candidate_openings = np.asarray(gripper_openings.get(best_key, np.array([]))).reshape(-1)
            for rank_idx in ranking[:top_k]:
                grasp = candidates[int(rank_idx)]
                candidate = {
                    "best_score": float(candidate_scores[int(rank_idx)]),
                    "best_translation": grasp[:3, 3].tolist(),
                    "best_grasp": grasp.tolist(),
                    "proposal_source": "contact_graspnet",
                    "approach_axis_cam": grasp[:3, 2].tolist(),
                    "base_axis_cam": grasp[:3, 0].tolist(),
                }
                if len(candidate_contact_pts) > int(rank_idx):
                    candidate["contact_point_cam"] = candidate_contact_pts[int(rank_idx)].tolist()
                if len(candidate_openings) > int(rank_idx):
                    candidate["gripper_opening_m"] = float(candidate_openings[int(rank_idx)])
                candidate_payloads.append(candidate)
            result = {
                "ok": True,
                "segment_key": int(best_key),
                "grasp_count": int(len(candidates)),
                "best_score": float(candidate_scores[best_idx]),
                "best_translation": best_grasp[:3, 3].tolist(),
                "best_grasp": best_grasp.tolist(),
                "approach_axis_cam": best_grasp[:3, 2].tolist(),
                "base_axis_cam": best_grasp[:3, 0].tolist(),
                "candidate_grasps": candidate_payloads,
            }
            if len(candidate_contact_pts) > best_idx:
                result["contact_point_cam"] = candidate_contact_pts[best_idx].tolist()
            if len(candidate_openings) > best_idx:
                result["gripper_opening_m"] = float(candidate_openings[best_idx])
    except Exception as exc:
        result = {
            "ok": False,
            "failure_stage": "grasp_proposal",
            "failure_reason": f"{type(exc).__name__}: {exc}",
        }
        trace("exception", error_type=type(exc).__name__, error=str(exc))
    finally:
        sess.close()
        trace("session_closed")

    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    trace("output_written", ok=bool(result.get("ok")))
    if trace_path is not None:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(json.dumps(trace_events, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
