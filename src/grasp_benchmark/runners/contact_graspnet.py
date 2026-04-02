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

    import tensorflow.compat.v1 as tf

    tf.disable_eager_execution()
    physical_devices = tf.config.experimental.list_physical_devices("GPU")
    if physical_devices:
        try:
            tf.config.experimental.set_memory_growth(physical_devices[0], True)
        except Exception:
            pass

    import config_utils
    from contact_grasp_estimator import GraspEstimator

    payload = np.load(input_path, allow_pickle=False)
    depth = payload["depth"]
    K = payload["K"]
    rgb = payload["rgb"] if "rgb" in payload.files else None

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
        pc_full, _, _ = grasp_estimator.extract_point_clouds(
            depth,
            K,
            segmap=None,
            rgb=rgb,
            z_range=[args.z_min, args.z_max],
        )
        pred_grasps_cam, scores, _, _ = grasp_estimator.predict_scene_grasps(
            sess,
            pc_full,
            pc_segments={},
            local_regions=False,
            filter_grasps=False,
            forward_passes=args.forward_passes,
        )
        candidates = pred_grasps_cam.get(-1, np.array([]))
        candidate_scores = scores.get(-1, np.array([]))
        if len(candidates) == 0 or len(candidate_scores) == 0:
            result = {
                "ok": False,
                "failure_stage": "grasp_proposal",
                "failure_reason": "Contact-GraspNet returned zero grasp proposals.",
            }
        else:
            best_idx = int(np.argmax(candidate_scores))
            best_grasp = candidates[best_idx]
            result = {
                "ok": True,
                "grasp_count": int(len(candidates)),
                "best_score": float(candidate_scores[best_idx]),
                "best_translation": best_grasp[:3, 3].tolist(),
                "best_grasp": best_grasp.tolist(),
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
