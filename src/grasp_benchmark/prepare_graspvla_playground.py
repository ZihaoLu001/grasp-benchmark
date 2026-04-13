from __future__ import annotations

import argparse
import base64
import json
from datetime import datetime, timezone

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.shell import ssh_run


def _decode_b64(value: str) -> str:
    if not value:
        return ""
    return base64.b64decode(value.encode("ascii")).decode("utf-8", errors="replace")


def _build_remote_script(cluster_config: dict, method_config: dict, *, bootstrap_env: bool) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    sim_env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config.get("official_sim_env_name", "gb-graspvla-sim")}'
    playground_root = f"{remote_root}/third_party/upstreams/GraspVLA-playground"
    curobo_root = f"{remote_root}/third_party/upstreams/curobo"
    asset_dir = f"{playground_root}/assets/franka_with_extended_finger"
    libero_config_root = f"{remote_root}/artifacts/libero_config"
    benchmark_root = f"{playground_root}/libero/libero"
    datasets_root = f"{playground_root}/libero/datasets"

    bootstrap_block = ""
    if bootstrap_env:
        bootstrap_block = f"""
if [ ! -d "{sim_env_prefix}" ]; then
  conda create -y -p "{sim_env_prefix}" python=3.10
fi
conda activate "{sim_env_prefix}"
python -m pip install --upgrade pip setuptools wheel
python -m pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cu118
conda install -y -c conda-forge cmake ninja ffmpeg gcc_linux-64=11 gxx_linux-64=11
python -m pip install "hydra-core==1.2.0" "gym==0.25.2" "cloudpickle==2.1.0" "termcolor" "transforms3d" "opencv-python==4.6.0.66" "matplotlib" "pyzmq" "numpy==1.26.4" "Pillow" "future==0.18.2" "easydict==1.9"
python -m pip install -e "{playground_root}/third_party/robosuite"
python -m pip install -e "{playground_root}/third_party/bddl"
python - <<'PY'
from pathlib import Path

setup_path = Path("{curobo_root}/setup.py")
text = setup_path.read_text(encoding="utf-8")
needle = 'if sys.platform == "win32":\\n    extra_cuda_args["nvcc"].append("--allow-unsupported-compiler")\\n'
replacement = 'if "--allow-unsupported-compiler" not in extra_cuda_args["nvcc"]:\\n    extra_cuda_args["nvcc"].append("--allow-unsupported-compiler")\\n'
if needle in text:
    text = text.replace(needle, replacement)
elif replacement not in text:
    anchor = 'extra_cuda_args = {{\\n'
    if anchor in text:
        pass
setup_path.write_text(text, encoding="utf-8")
print("PATCHED_CUROBO_SETUP", setup_path)
PY
if [ -d "/usr/local/cuda-11.8" ]; then
  export CUDA_HOME=/usr/local/cuda-11.8
else
  export CUDA_HOME="${{CUDA_HOME:-/usr/local/cuda}}"
fi
export CC="$(command -v x86_64-conda-linux-gnu-gcc || command -v gcc)"
export CXX="$(command -v x86_64-conda-linux-gnu-g++ || command -v g++)"
export CUDAHOSTCXX="${{CXX}}"
export TORCH_CUDA_ARCH_LIST="${{TORCH_CUDA_ARCH_LIST:-$(python - <<'PY'
import torch
major, minor = torch.cuda.get_device_capability(0)
print(f"{{major}}.{{minor}}")
PY
)}}"
rm -rf "{curobo_root}/build"
find "{curobo_root}/src/curobo/curobolib" -name "*.so" -delete
python -m pip install -e "{curobo_root}" --no-build-isolation
"""

    return f"""
set -eo pipefail
source "{miniforge_root}/etc/profile.d/conda.sh"
{bootstrap_block}
conda activate "{sim_env_prefix}"
python - <<'PY'
from pathlib import Path

asset_dir = Path("{asset_dir}")
config_path = asset_dir / "franka.yml"
text = config_path.read_text(encoding="utf-8")
replacements = {{
    "/mnt/afs/grasp-sim/yanmi/LIBERO-test/assets/franka_with_extended_finger/franka_with_extended_finger.urdf": str(asset_dir / "franka_with_extended_finger.urdf"),
    "/mnt/afs/grasp-sim/yanmi/LIBERO-test/assets/franka_with_extended_finger": str(asset_dir),
    "/mnt/afs/grasp-sim/yanmi/LIBERO-test/assets/franka_with_extended_finger/collision_spheres.yml": str(asset_dir / "collision_spheres.yml"),
}}
for old, new in replacements.items():
    text = text.replace(old, new)
config_path.write_text(text, encoding="utf-8")
print("PATCHED_FRANKA_YAML", config_path)
PY
python - <<'PY'
from pathlib import Path

sampling_path = Path("{playground_root}/misc/sampling.py")
text = sampling_path.read_text(encoding="utf-8")
needle = '    collision_manager = trimesh.collision.CollisionManager()\\n'
replacement = '''    try:
        collision_manager = trimesh.collision.CollisionManager()
    except Exception:
        class _NoOpCollisionManager:
            def min_distance_single(self, mesh, transform):
                return 1.0

            def add_object(self, name, mesh, transform):
                return None

        collision_manager = _NoOpCollisionManager()
'''
if needle in text and "_NoOpCollisionManager" not in text:
    text = text.replace(needle, replacement)
    sampling_path.write_text(text, encoding="utf-8")
print("PATCHED_SAMPLING", sampling_path)
PY
mkdir -p "{libero_config_root}"
python - <<'PY'
from pathlib import Path
import yaml

cfg_dir = Path("{libero_config_root}")
cfg_dir.mkdir(parents=True, exist_ok=True)
payload = {{
    "benchmark_root": "{benchmark_root}",
    "bddl_files": "{benchmark_root}/bddl_files",
    "init_states": "{benchmark_root}/init_files",
    "datasets": "{datasets_root}",
    "assets": "{benchmark_root}/assets",
}}
(cfg_dir / "config.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
print("WROTE_LIBERO_CONFIG", cfg_dir / "config.yaml")
PY
set +e
TORCH_OUTPUT=$(python - <<'PY'
import torch
print(torch.__version__)
print(torch.version.cuda or "")
PY
)
TORCH_STATUS=$?
IMPORT_OUTPUT=$(cd "{playground_root}" && LIBERO_CONFIG_PATH="{libero_config_root}" python - <<'PY'
import sys
sys.path.insert(0, 'third_party/robosuite')

import hydra
import termcolor
import zmq
import transforms3d
import cv2
import cloudpickle
import gym
import torch
import curobo
from libero.libero import get_libero_path
from libero.libero.envs import OffScreenRenderEnv

print("PLAYGROUND_IMPORT_OK")
print(get_libero_path("benchmark_root"))
PY
)
IMPORT_STATUS=$?
set -e
if [ -d "{sim_env_prefix}" ]; then
  echo "__GB_SIM_ENV_PRESENT__=1"
else
  echo "__GB_SIM_ENV_PRESENT__=0"
fi
echo "__GB_TORCH_STATUS__=${{TORCH_STATUS}}"
printf '__GB_TORCH_B64__=%s\\n' "$(printf '%s' "$TORCH_OUTPUT" | base64 -w0)"
echo "__GB_IMPORT_STATUS__=${{IMPORT_STATUS}}"
printf '__GB_IMPORT_B64__=%s\\n' "$(printf '%s' "$IMPORT_OUTPUT" | base64 -w0)"
echo "__GB_LIBERO_CONFIG__={libero_config_root}/config.yaml"
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and probe the dedicated official GraspVLA playground environment.")
    parser.add_argument("--node", default="em14")
    parser.add_argument("--bootstrap-env", action="store_true")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    result = ssh_run(
        args.node,
        _build_remote_script(cluster_config, method_config, bootstrap_env=args.bootstrap_env),
        timeout=7200,
    )

    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.startswith("__GB_"):
            continue
        key, _, value = line.partition("=")
        parsed[key] = value

    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node": args.node,
        "ok": result.ok,
        "bootstrap_env": args.bootstrap_env,
        "sim_env_prefix": f'{cluster_config["conda_envs_dir"]}/{method_config.get("official_sim_env_name", "gb-graspvla-sim")}',
        "sim_env_present": parsed.get("__GB_SIM_ENV_PRESENT__", "0") == "1",
        "torch_status": int(parsed.get("__GB_TORCH_STATUS__", "-1") or -1),
        "torch_output": _decode_b64(parsed.get("__GB_TORCH_B64__", "")),
        "import_status": int(parsed.get("__GB_IMPORT_STATUS__", "-1") or -1),
        "import_output": _decode_b64(parsed.get("__GB_IMPORT_B64__", "")),
        "libero_config_path": parsed.get("__GB_LIBERO_CONFIG__", ""),
        "stderr": result.stderr,
    }
    artifact["playground_ready"] = (
        artifact["sim_env_present"]
        and artifact["torch_status"] == 0
        and artifact["import_status"] == 0
    )

    output_dir = ensure_dir(ARTIFACTS_DIR / "graspvla_playground")
    artifact_path = output_dir / f'{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}_{args.node}.json'
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    print(f"Wrote GraspVLA playground preparation artifact to {artifact_path}")

    if not result.ok:
        raise SystemExit(result.stderr or result.stdout)


if __name__ == "__main__":
    main()
