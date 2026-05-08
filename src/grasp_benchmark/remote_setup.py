from __future__ import annotations

from typing import Any

CLUSTER_CUROBO_CUDA_ARCH_LIST = "7.5;8.0;8.9;9.0"


def _env_prefix(cluster_config: dict[str, Any], method_config: dict[str, Any]) -> str:
    return f'{cluster_config["conda_envs_dir"]}/{method_config["env_name"]}'


def build_method_install_script(
    cluster_config: dict[str, Any],
    method_config: dict[str, Any],
    method_name: str,
    *,
    include_playground: bool = False,
) -> tuple[str, list[str]]:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = _env_prefix(cluster_config, method_config)
    cuda_home = str(cluster_config.get("cuda_home", "/usr/local/cuda")).rstrip("/")
    arch_export = f'export TORCH_CUDA_ARCH_LIST="${{TORCH_CUDA_ARCH_LIST:-{CLUSTER_CUROBO_CUDA_ARCH_LIST}}}"'
    cuda_export = (
        f'export CUDA_HOME="{cuda_home}"; '
        f'export PATH="{cuda_home}/bin:$PATH"; '
        f'export LD_LIBRARY_PATH="{cuda_home}/lib64:${{LD_LIBRARY_PATH:-}}"'
    )
    source_block = [
        f'if [ -f "{source_file}" ]; then . "{source_file}" >/dev/null 2>&1 || true; fi'
        for source_file in cluster_config.get("source_files", [])
    ]
    module_block = [
        f'if command -v module >/dev/null 2>&1; then module load "{module_name}" >/dev/null 2>&1 || true; fi'
        for module_name in cluster_config.get("module_loads", [])
    ]
    lines = [
        "set -eo pipefail",
        *source_block,
        *module_block,
        f'source "{miniforge_root}/etc/profile.d/conda.sh"',
        f'conda activate "{env_prefix}"',
        f'cd "{remote_root}"',
        'python -m pip install --upgrade "pip<25" "setuptools<82" "wheel<0.46"',
    ]
    notes: list[str] = []

    if method_name == "graspvla":
        lines.extend(
            [
                f'python -m pip install -r "{remote_root}/third_party/upstreams/GraspVLA/requirements.txt"',
                'python -m pip install "einops>=0.4"',
                'python -m pip install "huggingface_hub>=0.30,<1.0"',
            ]
        )
        if include_playground:
            lines.extend(
                [
                    'conda install -y -c conda-forge ffmpeg',
                    'python -m pip install "hydra-core==1.2.0" "gym==0.25.2" "cloudpickle==2.1.0"',
                ]
            )
            notes.append(
                "For full official playground or LIBERO simulation, use the dedicated sim environment via "
                "python -m grasp_benchmark.prepare_graspvla_playground --node <host> --bootstrap-env."
            )
    elif method_name == "anygrasp":
        lines.extend(
            [
                'export SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL=True',
                'conda install -y -c conda-forge cmake ninja ffmpeg gcc_linux-64=11 gxx_linux-64=11',
                'python -m pip uninstall -y torch torchvision torchaudio opencv-python opencv-python-headless numpy || true',
                'python -m pip install "numpy<2" "opencv-python==4.6.0.66"',
                'python -m pip install "torch==2.2.2" "torchvision==0.17.2" "torchaudio==2.2.2" --index-url https://download.pytorch.org/whl/cu118',
                'python -m pip install "transformers==4.41.2" "numba" "termcolor"',
                'python -m pip install "hydra-core==1.2.0" "gym==0.25.2" "cloudpickle==2.1.0" "transforms3d" "opencv-python==4.6.0.66" "matplotlib" "pyzmq" "Pillow" "future==0.18.2" "easydict==1.9" "mujoco==3.6.0" "h5py"',
                f'python -m pip install -r "{remote_root}/third_party/upstreams/anygrasp_sdk/requirements.txt"',
                f'python -m pip install -r "{remote_root}/third_party/upstreams/GroundingDINO/requirements.txt"',
                'python -m pip install "numpy<2" "opencv-python==4.6.0.66" "transformers==4.41.2" "numba" "termcolor"',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/GraspVLA-playground/third_party/robosuite"',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/GraspVLA-playground/third_party/bddl"',
                cuda_export,
                'export CC="$(command -v x86_64-conda-linux-gnu-gcc || command -v gcc)"',
                'export CXX="$(command -v x86_64-conda-linux-gnu-g++ || command -v g++)"',
                'export CUDAHOSTCXX="${CXX}"',
                arch_export,
                f'rm -rf "{remote_root}/third_party/upstreams/curobo/build"',
                f'find "{remote_root}/third_party/upstreams/curobo/src/curobo/curobolib" -name "*.so" -delete',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/curobo" --no-build-isolation',
                'conda install -y -c anaconda openblas-devel',
                f'mkdir -p "{remote_root}/third_party/upstreams/anygrasp_sdk/dependencies"',
                f'if [ ! -d "{remote_root}/third_party/upstreams/anygrasp_sdk/dependencies/MinkowskiEngine/.git" ]; then rm -rf "{remote_root}/third_party/upstreams/anygrasp_sdk/dependencies/MinkowskiEngine"; git clone https://github.com/chenxi-wang/MinkowskiEngine.git "{remote_root}/third_party/upstreams/anygrasp_sdk/dependencies/MinkowskiEngine"; fi',
                'export MAX_JOBS="${MAX_JOBS:-2}"',
                f'if ! python -c \'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("MinkowskiEngine") else 1)\'; then cd "{remote_root}/third_party/upstreams/anygrasp_sdk/dependencies/MinkowskiEngine" && rm -rf build && python setup.py install --blas_include_dirs=${{CONDA_PREFIX}}/include --blas_library_dirs=${{CONDA_PREFIX}}/lib --blas=openblas; fi',
                f'if ! python -c \'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("pointnet2") else 1)\'; then cd "{remote_root}/third_party/upstreams/anygrasp_sdk/pointnet2" && rm -rf build && python setup.py install; fi',
                'SOABI=$(python -c \'import sysconfig; print(sysconfig.get_config_var("SOABI") or "")\')',
                'OPENSSL_COMPAT_DIR=""',
                'for candidate in /usr/local/cuda-11.8/nsight-systems-2022.4.2/host-linux-x64 /usr/local/cuda-11.8/nsight-compute-2022.3.0/host/linux-desktop-glibc_2_11_3-x64 /usr/local/cuda-12.1/nsight-systems-2023.1.2/host-linux-x64 /usr/local/cuda-12.1/nsight-compute-2023.1.1/host/linux-desktop-glibc_2_11_3-x64 /usr/local/cuda-12.3/nsight-systems-2023.3.3/host-linux-x64 /usr/local/cuda-12.3/nsight-compute-2023.3.1/host/linux-desktop-glibc_2_11_3-x64; do if [ -f "$candidate/libcrypto.so.1.1" ] && [ -f "$candidate/libssl.so.1.1" ]; then OPENSSL_COMPAT_DIR="$candidate"; break; fi; done',
                'if [ -n "$OPENSSL_COMPAT_DIR" ]; then ln -sf "$OPENSSL_COMPAT_DIR/libcrypto.so.1.1" "$CONDA_PREFIX/lib/libcrypto.so.1.1"; ln -sf "$OPENSSL_COMPAT_DIR/libssl.so.1.1" "$CONDA_PREFIX/lib/libssl.so.1.1"; fi',
                f'cp -f "{remote_root}/third_party/upstreams/anygrasp_sdk/grasp_detection/gsnet_versions/gsnet.${{SOABI}}.so" "{remote_root}/third_party/upstreams/anygrasp_sdk/grasp_detection/gsnet.so"',
                f'cp -f "{remote_root}/third_party/upstreams/anygrasp_sdk/license_registration/lib_cxx_versions/lib_cxx.${{SOABI}}.so" "{remote_root}/third_party/upstreams/anygrasp_sdk/grasp_detection/lib_cxx.so"',
            ]
        )
        notes.extend(
            [
                "AnyGrasp still needs MinkowskiEngine to be built against the target CUDA toolkit.",
                "AnyGrasp inference also requires a license registration step before the SDK binary will run.",
                "Run python -m grasp_benchmark.prepare_anygrasp --node <host> to capture the machine feature id and current license state.",
            ]
        )
    elif method_name == "cgn":
        lines.extend(
            [
                'export SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL=True',
                'python -m pip install scikit-learn',
                'python -m pip install "torch==2.2.2" "torchvision==0.17.2" "torchaudio==2.2.2" --index-url https://download.pytorch.org/whl/cu118',
                'conda install -y -c conda-forge cmake ninja ffmpeg gcc_linux-64=11 gxx_linux-64=11',
                'python -m pip install "hydra-core==1.2.0" "gym==0.25.2" "cloudpickle==2.1.0" "termcolor" "transforms3d" "opencv-python==4.6.0.66" "matplotlib" "pyzmq" "numpy==1.26.4" "Pillow" "future==0.18.2" "easydict==1.9" "numba" "mujoco==3.6.0" "h5py"',
                'python -m pip install "transformers==4.41.2"',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/GraspVLA-playground/third_party/robosuite"',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/GraspVLA-playground/third_party/bddl"',
                cuda_export,
                'export CC="$(command -v x86_64-conda-linux-gnu-gcc || command -v gcc)"',
                'export CXX="$(command -v x86_64-conda-linux-gnu-g++ || command -v g++)"',
                'export CUDAHOSTCXX="${CXX}"',
                arch_export,
                f'rm -rf "{remote_root}/third_party/upstreams/curobo/build"',
                f'find "{remote_root}/third_party/upstreams/curobo/src/curobo/curobolib" -name "*.so" -delete',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/curobo" --no-build-isolation',
                f'python -m pip install -r "{remote_root}/third_party/upstreams/GroundingDINO/requirements.txt"',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/GroundingDINO" --no-build-isolation',
                'python -m pip install "transformers==4.41.2"',
            ]
        )
        notes.extend(
            [
                "Contact-GraspNet proposal inference uses a dedicated TensorFlow runtime; on Lakeshore this is gb-cgn-tf212 for H100/CUDA 11.8.",
                "The shared Track A simulation lane also needs the GraspVLA playground + curobo stack inside gb-cgn.",
                "Run python -m grasp_benchmark.prepare_cgn --node <host> --cluster-config lakeshore --bootstrap-legacy-env --compile-tf-ops to prepare Contact-GraspNet proposal inference.",
            ]
        )
    else:
        raise ValueError(f"Unsupported method for remote install: {method_name}")

    lines.append('echo "INSTALL_OK"')
    return "\n".join(lines) + "\n", notes
