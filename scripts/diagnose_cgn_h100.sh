#!/usr/bin/env bash
set -eo pipefail

PROJECT_ROOT="${1:-/projects/cs_yifan16_chi/zlu31/grasp-benchmark}"
ACCOUNT="${ACCOUNT:-cs_yifan16_chi}"
PARTITION="${PARTITION:-batch_gpu2}"
GRES="${GRES:-gpu:1}"
CUDA_HOME_DIR="${CUDA_HOME_DIR:-/cm/shared/apps/cuda11.8/toolkit/11.8.0}"
ENV_PREFIX="${ENV_PREFIX:-/projects/cs_yifan16_chi/zlu31/conda_envs/gb-cgn-tf212}"
RUN_DIR="${RUN_DIR:-${PROJECT_ROOT}/artifacts/debug/cgn_h100_probe/$(date -u +%Y%m%d_%H%M%S)}"

mkdir -p "${RUN_DIR}"
export PROJECT_ROOT
export RUN_DIR
export CUDA_HOME_DIR
export ENV_PREFIX

if [ -f /etc/profile.d/modules.sh ]; then
  . /etc/profile.d/modules.sh
fi
module load slurm/lakeshore/23.02.4 >/dev/null 2>&1 || true

cat > "${RUN_DIR}/tf_probe.py" <<'PY'
import json
import os
import time

started = time.perf_counter()


def log(stage, **fields):
    event = {"stage": stage, "elapsed_s": round(time.perf_counter() - started, 3), **fields}
    print("__PROBE__ " + json.dumps(event, sort_keys=True), flush=True)


log("start", cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES", ""))
import tensorflow.compat.v1 as tf

tf.disable_eager_execution()
gpus = tf.config.experimental.list_physical_devices("GPU")
log("tensorflow_imported", version=tf.__version__, gpu_count=len(gpus), gpus=[str(gpu) for gpu in gpus])
with tf.device("/GPU:0"):
    a = tf.random.uniform([1024, 1024], dtype=tf.float32)
    b = tf.matmul(a, a)
config = tf.ConfigProto()
config.gpu_options.allow_growth = True
config.allow_soft_placement = True
with tf.Session(config=config) as sess:
    log("matmul_start")
    out = sess.run(b)
    log("matmul_done", shape=list(out.shape), checksum=float(out[:8, :8].sum()))
PY

cat > "${RUN_DIR}/custom_op_probe.py" <<'PY'
import json
import os
import sys
import time

import numpy as np

project_root = os.environ["PROJECT_ROOT"]
cgn_root = os.path.join(project_root, "third_party", "upstreams", "contact_graspnet")
sys.path.insert(0, os.path.join(cgn_root, "pointnet2", "tf_ops", "sampling"))
sys.path.insert(0, os.path.join(cgn_root, "pointnet2", "tf_ops", "grouping"))
sys.path.insert(0, os.path.join(cgn_root, "pointnet2", "utils"))
sys.path.insert(0, os.path.join(cgn_root, "contact_graspnet"))
sys.path.insert(0, cgn_root)

started = time.perf_counter()


def log(stage, **fields):
    event = {"stage": stage, "elapsed_s": round(time.perf_counter() - started, 3), **fields}
    print("__PROBE__ " + json.dumps(event, sort_keys=True), flush=True)


log("start", cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES", ""))
import tensorflow.compat.v1 as tf

tf.disable_eager_execution()
from tf_sampling import farthest_point_sample, gather_point

log("sampling_imported", tensorflow_version=tf.__version__)
for n_points, n_sample in ((2048, 1024), (20000, 2048)):
    tf.reset_default_graph()
    pts = np.random.default_rng(7).random((1, n_points, 3), dtype=np.float32)
    points_pl = tf.placeholder(tf.float32, shape=(1, n_points, 3))
    sampled = gather_point(points_pl, farthest_point_sample(n_sample, points_pl))
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    config.allow_soft_placement = True
    with tf.Session(config=config) as sess:
        log("sampling_start", n_points=n_points, n_sample=n_sample)
        out = sess.run(sampled, feed_dict={points_pl: pts})
        log("sampling_done", n_points=n_points, n_sample=n_sample, shape=list(out.shape), checksum=float(out[0, :8, :].sum()))
PY

cat > "${RUN_DIR}/make_raw_input.py" <<'PY'
import os
from pathlib import Path

import numpy as np

run_dir = Path(os.environ["RUN_DIR"])
rng = np.random.default_rng(11)
points = np.empty((20000, 3), dtype=np.float32)
points[:, 0] = rng.normal(0.0, 0.045, size=points.shape[0])
points[:, 1] = rng.normal(0.0, 0.035, size=points.shape[0])
points[:, 2] = rng.normal(0.72, 0.035, size=points.shape[0])
colors = np.empty((20000, 3), dtype=np.float32)
colors[:, 0] = 0.95
colors[:, 1] = 0.78
colors[:, 2] = 0.18
np.savez(run_dir / "raw_input.npz", points=points, colors=colors)
print(run_dir / "raw_input.npz")
PY

cat > "${RUN_DIR}/run_inside_allocation.sh" <<'SH'
#!/usr/bin/env bash
set -eo pipefail

export PROJECT_ROOT
export RUN_DIR
export CUDA_HOME="${CUDA_HOME_DIR}"
export PATH="${CUDA_HOME}/bin:${PATH}"
export PYTHONPATH="${PROJECT_ROOT}/src"
export PYTHONUNBUFFERED=1
export LD_PRELOAD="${ENV_PREFIX}/lib/libstdc++.so.6"
export CUDNN_LIB="${ENV_PREFIX}/lib/python3.10/site-packages/nvidia/cudnn/lib"
export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${ENV_PREFIX}/lib:${CUDNN_LIB}:/usr/lib64:/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

run_step() {
  local name="$1"
  local limit="$2"
  shift 2
  echo "__STEP_START__ ${name} limit=${limit}"
  set +e
  timeout "${limit}" "$@" >"${RUN_DIR}/${name}.stdout" 2>"${RUN_DIR}/${name}.stderr"
  local status=$?
  set -e
  echo "__STEP_STATUS__ ${name} status=${status}"
  echo "__STEP_STDOUT__ ${name}"
  sed -n '1,220p' "${RUN_DIR}/${name}.stdout" || true
  echo "__STEP_STDERR__ ${name}"
  sed -n '1,220p' "${RUN_DIR}/${name}.stderr" || true
}

echo "__NODE__ $(hostname)"
echo "__CUDA_VISIBLE_DEVICES__ ${CUDA_VISIBLE_DEVICES:-}"
nvidia-smi -L || true
ldd "${PROJECT_ROOT}/third_party/upstreams/contact_graspnet/pointnet2/tf_ops/sampling/tf_sampling_so.so" >"${RUN_DIR}/tf_sampling_so.ldd" 2>&1 || true

run_step tf_matmul 90s "${ENV_PREFIX}/bin/python" "${RUN_DIR}/tf_probe.py"
run_step tf_matmul_force_ptx 120s env CUDA_FORCE_PTX_JIT=1 "${ENV_PREFIX}/bin/python" "${RUN_DIR}/tf_probe.py"
run_step pointnet_sampling 120s "${ENV_PREFIX}/bin/python" "${RUN_DIR}/custom_op_probe.py"
run_step make_raw_input 30s "${ENV_PREFIX}/bin/python" "${RUN_DIR}/make_raw_input.py"
run_step cgn_raw_runner 240s "${ENV_PREFIX}/bin/python" -m grasp_benchmark.runners.contact_graspnet \
  --input "${RUN_DIR}/raw_input.npz" \
  --output "${RUN_DIR}/raw_output.json" \
  --upstream-root "${PROJECT_ROOT}/third_party/upstreams/contact_graspnet" \
  --checkpoint-dir "${PROJECT_ROOT}/third_party/upstreams/contact_graspnet/checkpoints/scene_test_2048_bs3_hor_sigma_001" \
  --forward-passes 1 \
  --top-k 10 \
  --cuda-visible-devices "${CUDA_VISIBLE_DEVICES:-0}" \
  --trace-json "${RUN_DIR}/raw_trace.json"

echo "__RUN_DIR__ ${RUN_DIR}"
SH
chmod +x "${RUN_DIR}/run_inside_allocation.sh"

srun --wait=0 --kill-on-bad-exit=1 \
  -A "${ACCOUNT}" \
  -p "${PARTITION}" \
  --gres="${GRES}" \
  --cpus-per-task=2 \
  --mem=48G \
  --time=00:25:00 \
  bash "${RUN_DIR}/run_inside_allocation.sh" 2>&1 | tee "${RUN_DIR}/allocation.log"

echo "Wrote CGN H100 diagnostic artifacts to ${RUN_DIR}"
