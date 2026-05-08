from __future__ import annotations

import argparse
import base64
import json
import shlex
from datetime import datetime, timezone

from grasp_benchmark.config import load_cluster_config, load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.shell import ssh_run


def _slurm_wrap_script(cluster_config: dict, inner_script: str) -> str:
    scheduler = cluster_config.get("prepare_scheduler") or cluster_config.get("scheduler", {})
    if str(scheduler.get("type", "")).strip().lower() != "slurm":
        return inner_script

    setup_lines: list[str] = ["set -eo pipefail"]
    for source_file in cluster_config.get("source_files", []):
        quoted_source = shlex.quote(str(source_file))
        setup_lines.append(f"if [ -f {quoted_source} ]; then . {quoted_source}; fi")
    for module_name in cluster_config.get("module_loads", []):
        setup_lines.append(f"module load {shlex.quote(str(module_name))}")

    srun_parts = ["srun", "--wait=0", "--kill-on-bad-exit=1"]
    for flag_name, value in (
        ("-A", scheduler.get("account", "")),
        ("-p", scheduler.get("partition", "")),
    ):
        text = str(value).strip()
        if text:
            srun_parts.extend([flag_name, shlex.quote(text)])
    for option_name, value in (
        ("--gres", scheduler.get("gres", "")),
        ("--cpus-per-task", scheduler.get("cpus_per_task", "")),
        ("--mem", scheduler.get("mem", "")),
        ("--time", scheduler.get("time", "")),
    ):
        text = str(value).strip()
        if text:
            srun_parts.append(f"{option_name}={shlex.quote(text)}")

    encoded = base64.b64encode(inner_script.encode("utf-8")).decode("ascii")
    srun_parts.extend(["bash", "-lc", shlex.quote(f"printf '%s' {encoded} | base64 -d | /bin/bash")])
    return "\n".join([*setup_lines, " ".join(srun_parts), ""])


def _uses_tf212_runtime(method_config: dict) -> bool:
    runtime = method_config.get("legacy_runtime", {})
    return str(runtime.get("profile", "")).strip().lower() == "tf212_cuda118_h100"


def _tf212_bootstrap_lines(env_prefix: str) -> list[str]:
    return [
        f'if [ ! -d "{env_prefix}" ]; then',
        (
            f'  conda create -y -p "{env_prefix}" -c conda-forge '
            'python=3.10 pip "numpy=1.23.5" '
            'gcc_linux-64=11 gxx_linux-64=11 cmake ninja'
        ),
        "else",
        (
            f'  conda install -y -p "{env_prefix}" -c conda-forge '
            'gcc_linux-64=11 gxx_linux-64=11 cmake ninja'
        ),
        "fi",
        f'conda run -p "{env_prefix}" python -m pip install --upgrade "pip<25" "setuptools<70" "wheel<0.46"',
        (
            f'conda run -p "{env_prefix}" python -m pip install '
            '"tensorflow==2.12.0" "tensorflow-estimator==2.12.0" "keras==2.12.0" "numpy==1.23.5" '
            '"nvidia-cudnn-cu11==8.6.0.163"'
        ),
        f'conda run -p "{env_prefix}" python - <<\'PY\'',
        "import pathlib, sys",
        "import nvidia.cudnn",
        "env_lib = pathlib.Path(sys.prefix) / 'lib'",
        "cudnn_lib = pathlib.Path(nvidia.cudnn.__file__).resolve().parent / 'lib'",
        "for src in cudnn_lib.glob('libcudnn*.so*'):",
        "    dst = env_lib / src.name",
        "    if dst.exists() or dst.is_symlink():",
        "        dst.unlink()",
        "    dst.symlink_to(src)",
        "print('CUDNN_SYMLINK_OK', cudnn_lib)",
        "PY",
        (
            f'conda run -p "{env_prefix}" python -m pip install '
            '"opencv-python-headless==4.6.0.66" "pyyaml>=6,<7" "scipy>=1.10,<1.11" '
            '"Pillow>=9,<11" "trimesh>=3.23,<4" "pyrender==0.1.45" "PyOpenGL==3.1.0" '
            '"rtree" "tqdm" "future"'
        ),
    ]


def _tf_ops_compile_lines(env_prefix: str, cuda_home: str, cgn_root: str, *, h100_runtime: bool) -> list[str]:
    if not h100_runtime:
        return [
            'compile_script="$(mktemp /tmp/gb-cgn-compile.XXXXXX.sh)"',
            f"sed 's#/usr/local/cuda#{cuda_home}#g' \"{cgn_root}/compile_pointnet_tfops.sh\" > \"$compile_script\"",
            'chmod +x "$compile_script"',
            'export compile_script',
            (
                f'conda run -p "{env_prefix}" bash -lc '
                f'\'cd "{cgn_root}" && export CUDA_HOME="{cuda_home}" && '
                f'export PATH="{cuda_home}/bin:$PATH" && '
                f'export LD_LIBRARY_PATH="{cuda_home}/lib64:${{LD_LIBRARY_PATH:-}}" && '
                'bash "$compile_script"\''
            ),
            'rm -f "$compile_script"',
        ]

    return [
        'compile_script="$(mktemp /tmp/gb-cgn-compile-tf212.XXXXXX.sh)"',
        "cat > \"$compile_script\" <<'GB_CGN_COMPILE'",
        "#!/usr/bin/env bash",
        "set -eo pipefail",
        ': "${CUDA_HOME:?CUDA_HOME is required}"',
        'NVCC="${CUDA_HOME}/bin/nvcc"',
        'CXX_BIN="${CXX:-$(command -v x86_64-conda-linux-gnu-g++ || command -v g++)}"',
        'TF_CFLAGS=( $(python -c \'import tensorflow as tf; print(" ".join(tf.sysconfig.get_compile_flags()))\') )',
        'TF_LFLAGS=( $(python -c \'import tensorflow as tf; print(" ".join(tf.sysconfig.get_link_flags()))\') )',
        'CUDA_ARCH_FLAGS=(',
        '  "-gencode=arch=compute_80,code=sm_80"',
        '  "-gencode=arch=compute_86,code=sm_86"',
        '  "-gencode=arch=compute_89,code=sm_89"',
        '  "-gencode=arch=compute_90,code=sm_90"',
        '  "-gencode=arch=compute_90,code=compute_90"',
        ")",
        'export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"',
        'cd pointnet2/tf_ops/sampling',
        'rm -f tf_sampling_g.cu.o tf_sampling_so.so',
        '"${NVCC}" -std=c++17 -O2 -c -o tf_sampling_g.cu.o tf_sampling_g.cu "${CUDA_ARCH_FLAGS[@]}" -DGOOGLE_CUDA=1 -x cu -Xcompiler -fPIC',
        '"${CXX_BIN}" -std=c++17 -O2 -shared -o tf_sampling_so.so tf_sampling.cpp tf_sampling_g.cu.o "${TF_CFLAGS[@]}" -I"${CUDA_HOME}/include" -fPIC -lcudart "${TF_LFLAGS[@]}" -L"${CUDA_HOME}/lib64"',
        'cd ../grouping',
        'rm -f tf_grouping_g.cu.o tf_grouping_so.so',
        '"${NVCC}" -std=c++17 -O2 -c -o tf_grouping_g.cu.o tf_grouping_g.cu "${CUDA_ARCH_FLAGS[@]}" -DGOOGLE_CUDA=1 -x cu -Xcompiler -fPIC',
        '"${CXX_BIN}" -std=c++17 -O2 -shared -o tf_grouping_so.so tf_grouping.cpp tf_grouping_g.cu.o "${TF_CFLAGS[@]}" -I"${CUDA_HOME}/include" -fPIC -lcudart "${TF_LFLAGS[@]}" -L"${CUDA_HOME}/lib64"',
        'cd ../3d_interpolation',
        'rm -f tf_interpolate_so.so',
        '"${CXX_BIN}" -std=c++17 -O2 -shared -o tf_interpolate_so.so tf_interpolate.cpp "${TF_CFLAGS[@]}" -fPIC "${TF_LFLAGS[@]}"',
        "python - <<'PY'",
        "import os, sys",
        "root = os.getcwd()",
        "sys.path.insert(0, os.path.abspath('../sampling'))",
        "sys.path.insert(0, os.path.abspath('../grouping'))",
        "sys.path.insert(0, root)",
        "import tf_sampling, tf_grouping, tf_interpolate",
        "print('TF_OPS_IMPORT_OK')",
        "PY",
        "GB_CGN_COMPILE",
        'chmod +x "$compile_script"',
        'export compile_script',
        (
            f'conda run -p "{env_prefix}" bash -lc '
            f'\'cd "{cgn_root}" && export CUDA_HOME="{cuda_home}" && '
            f'export PATH="{cuda_home}/bin:$PATH" && '
            'export CC="$(command -v x86_64-conda-linux-gnu-gcc || command -v gcc)" && '
            'export CXX="$(command -v x86_64-conda-linux-gnu-g++ || command -v g++)" && '
            f'export LD_LIBRARY_PATH="{cuda_home}/lib64:${{CONDA_PREFIX}}/lib:${{LD_LIBRARY_PATH:-}}" && '
            'bash "$compile_script"\''
        ),
        'rm -f "$compile_script"',
    ]


def _version_probe_script(remote_root: str, env_prefix: str, method_config: dict) -> str:
    runtime = method_config.get("legacy_runtime", {})
    expected_tf = str(runtime.get("tensorflow_version", "")).strip()
    expected_python = str(runtime.get("python_version", "")).strip()
    lines = [
        f'PY_OUTPUT=$(conda run -p "{env_prefix}" python -c \'import sys; print(sys.version.split()[0])\' 2>&1)',
        "PY_STATUS=$?",
        f'TF_OUTPUT=$(conda run -p "{env_prefix}" python -c \'import tensorflow as tf; print(tf.__version__)\' 2>&1)',
        "TF_STATUS=$?",
        f'RUNNER_OUTPUT=$(PYTHONPATH="{remote_root}/src" conda run -p "{env_prefix}" python -c \'import grasp_benchmark.runners.contact_graspnet as runner; print("RUNNER_IMPORT_OK")\' 2>&1)',
        "RUNNER_STATUS=$?",
    ]
    if expected_python:
        lines.extend(
            [
                f'PY_EXPECTED="{expected_python}"',
                'if [ "$PY_STATUS" -eq 0 ] && ! printf "%s" "$PY_OUTPUT" | grep -q "^${PY_EXPECTED}"; then PY_STATUS=91; PY_OUTPUT="${PY_OUTPUT}\nEXPECTED_PYTHON_PREFIX=${PY_EXPECTED}"; fi',
            ]
        )
    if expected_tf:
        lines.extend(
            [
                f'TF_EXPECTED="{expected_tf}"',
                'if [ "$TF_STATUS" -eq 0 ] && ! printf "%s" "$TF_OUTPUT" | grep -q "^${TF_EXPECTED}$"; then TF_STATUS=92; TF_OUTPUT="${TF_OUTPUT}\nEXPECTED_TENSORFLOW=${TF_EXPECTED}"; fi',
            ]
        )
    return "\n".join(lines)


def _build_remote_script(cluster_config: dict, method_config: dict, *, bootstrap_legacy_env: bool, compile_tf_ops: bool) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["legacy_env_name"]}'
    cuda_home = str(cluster_config.get("cuda_home", "/usr/local/cuda")).rstrip("/")
    cgn_root = f"{remote_root}/third_party/upstreams/contact_graspnet"
    checkpoint_dir = f"{cgn_root}/{method_config['checkpoint_relpath']}"
    h100_runtime = _uses_tf212_runtime(method_config)

    bootstrap_lines = []
    if bootstrap_legacy_env:
        if h100_runtime:
            bootstrap_lines.extend(_tf212_bootstrap_lines(env_prefix))
        else:
            bootstrap_lines.extend(
                [
                    f'if [ -d "{env_prefix}" ]; then',
                    f'  conda env update -p "{env_prefix}" -f "{cgn_root}/contact_graspnet_env.yml" --prune',
                    "else",
                    f'  conda env create -p "{env_prefix}" -f "{cgn_root}/contact_graspnet_env.yml"',
                    "fi",
                ]
            )
    if compile_tf_ops:
        bootstrap_lines.extend(_tf_ops_compile_lines(env_prefix, cuda_home, cgn_root, h100_runtime=h100_runtime))

    bootstrap_block = "\n".join(bootstrap_lines)
    inner_script = f"""
set -euo pipefail
source "{miniforge_root}/etc/profile.d/conda.sh"
{bootstrap_block}
if [ -d "{env_prefix}" ]; then
  echo "__GB_LEGACY_ENV_PRESENT__=1"
else
  echo "__GB_LEGACY_ENV_PRESENT__=0"
fi
if [ -d "{checkpoint_dir}" ] && find "{checkpoint_dir}" -mindepth 1 -print -quit | grep -q .; then
  echo "__GB_CKPT_READY__=1"
else
  echo "__GB_CKPT_READY__=0"
fi
set +e
{_version_probe_script(remote_root, env_prefix, method_config)}
set -e
echo "__GB_PY_STATUS__=${{PY_STATUS}}"
printf '__GB_PY_B64__=%s\\n' "$(printf '%s' "$PY_OUTPUT" | base64 -w0)"
echo "__GB_TF_STATUS__=${{TF_STATUS}}"
printf '__GB_TF_B64__=%s\\n' "$(printf '%s' "$TF_OUTPUT" | base64 -w0)"
echo "__GB_RUNNER_STATUS__=${{RUNNER_STATUS}}"
printf '__GB_RUNNER_B64__=%s\\n' "$(printf '%s' "$RUNNER_OUTPUT" | base64 -w0)"
"""
    return _slurm_wrap_script(cluster_config, inner_script)


def _decode_b64(value: str) -> str:
    if not value:
        return ""
    return base64.b64decode(value.encode("ascii")).decode("utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and probe the Contact-GraspNet legacy runtime.")
    parser.add_argument("--node", default="lakeshore")
    parser.add_argument(
        "--cluster-config",
        default="",
        help="Cluster config name under configs/cluster. Defaults to GRASP_BENCHMARK_CLUSTER_CONFIG or default.",
    )
    parser.add_argument("--bootstrap-legacy-env", action="store_true")
    parser.add_argument("--compile-tf-ops", action="store_true")
    args = parser.parse_args()

    cluster_config = load_cluster_config(args.cluster_config)
    method_config = load_named_config("methods", "cgn")
    result = ssh_run(
        args.node,
        _build_remote_script(
            cluster_config,
            method_config,
            bootstrap_legacy_env=args.bootstrap_legacy_env,
            compile_tf_ops=args.compile_tf_ops,
        ),
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
        "bootstrap_legacy_env": args.bootstrap_legacy_env,
        "compile_tf_ops": args.compile_tf_ops,
        "legacy_env_prefix": f'{cluster_config["conda_envs_dir"]}/{method_config["legacy_env_name"]}',
        "legacy_env_present": parsed.get("__GB_LEGACY_ENV_PRESENT__", "0") == "1",
        "checkpoint_ready": parsed.get("__GB_CKPT_READY__", "0") == "1",
        "python_status": int(parsed.get("__GB_PY_STATUS__", "-1") or -1),
        "python_output": _decode_b64(parsed.get("__GB_PY_B64__", "")),
        "tensorflow_status": int(parsed.get("__GB_TF_STATUS__", "-1") or -1),
        "tensorflow_output": _decode_b64(parsed.get("__GB_TF_B64__", "")),
        "runner_status": int(parsed.get("__GB_RUNNER_STATUS__", "-1") or -1),
        "runner_output": _decode_b64(parsed.get("__GB_RUNNER_B64__", "")),
        "stderr": result.stderr,
    }
    artifact["legacy_runtime_ready"] = (
        artifact["legacy_env_present"]
        and artifact["python_status"] == 0
        and artifact["tensorflow_status"] == 0
        and artifact["runner_status"] == 0
    )

    output_dir = ensure_dir(ARTIFACTS_DIR / "cgn")
    artifact_path = output_dir / f'{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}_{args.node}.json'
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    print(f"Wrote Contact-GraspNet preparation artifact to {artifact_path}")

    if not result.ok:
        raise SystemExit(result.stderr or result.stdout)


if __name__ == "__main__":
    main()
