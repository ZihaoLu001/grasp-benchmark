from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np


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
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    upstream_root = Path(args.upstream_root).resolve()
    checkpoint_dir = Path(args.checkpoint_dir).resolve()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    sys.path.insert(0, str(upstream_root))
    sys.path.insert(0, str(upstream_root / "contact_graspnet"))

    os.environ.setdefault("CUDA_VISIBLE_DEVICES", str(args.cuda_visible_devices))

    import tensorflow.compat.v1 as tf

    tf.disable_eager_execution()
    physical_devices = tf.config.experimental.list_physical_devices("GPU")
    for device in physical_devices:
        try:
            tf.config.experimental.set_memory_growth(device, True)
        except Exception:
            pass

    import config_utils
    from contact_grasp_estimator import GraspEstimator

    payload = np.load(input_path, allow_pickle=False)
    use_raw_points = "points" in payload.files
    points = payload["points"] if use_raw_points else None
    colors = payload["colors"] if "colors" in payload.files else None
    depth = payload["depth"] if "depth" in payload.files else None
    K = payload["K"] if "K" in payload.files else None
    rgb = payload["rgb"] if "rgb" in payload.files else None
    segmap = payload["segmap"] if "segmap" in payload.files else None

    global_config = config_utils.load_config(str(checkpoint_dir), batch_size=args.forward_passes, arg_configs=[])
    grasp_estimator = GraspEstimator(global_config)
    grasp_estimator.build_network()
    saver = tf.train.Saver(save_relative_paths=True)

    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    config.allow_soft_placement = True
    sess = tf.Session(config=config)
    try:
        grasp_estimator.load_weights(sess, saver, str(checkpoint_dir), mode="test")
        if use_raw_points:
            pc_full = points.astype(np.float32)
            pc_segments = {}
        else:
            pc_full, pc_segments, _ = grasp_estimator.extract_point_clouds(
                depth,
                K,
                segmap=segmap,
                rgb=rgb,
                z_range=[args.z_min, args.z_max],
            )
        pred_grasps_cam, scores, _, _ = grasp_estimator.predict_scene_grasps(
            sess,
            pc_full,
            pc_segments=pc_segments,
            local_regions=(segmap is not None) and not use_raw_points,
            filter_grasps=(segmap is not None) and not use_raw_points,
            forward_passes=args.forward_passes,
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
            for rank_idx in ranking[:top_k]:
                grasp = candidates[int(rank_idx)]
                candidate_payloads.append(
                    {
                        "best_score": float(candidate_scores[int(rank_idx)]),
                        "best_translation": grasp[:3, 3].tolist(),
                        "best_grasp": grasp.tolist(),
                        "proposal_source": "contact_graspnet",
                    }
                )
            result = {
                "ok": True,
                "segment_key": int(best_key),
                "grasp_count": int(len(candidates)),
                "best_score": float(candidate_scores[best_idx]),
                "best_translation": best_grasp[:3, 3].tolist(),
                "best_grasp": best_grasp.tolist(),
                "candidate_grasps": candidate_payloads,
            }
    except Exception as exc:
        result = {
            "ok": False,
            "failure_stage": "grasp_proposal",
            "failure_reason": f"{type(exc).__name__}: {exc}",
        }
    finally:
        sess.close()

    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
