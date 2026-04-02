from __future__ import annotations

from typing import Any


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
    lines = [
        "set -euo pipefail",
        f'source "{miniforge_root}/etc/profile.d/conda.sh"',
        f'conda activate "{env_prefix}"',
        f'cd "{remote_root}"',
        "python -m pip install --upgrade pip setuptools wheel",
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
            lines.append(
                f'python -m pip install -r "{remote_root}/third_party/upstreams/GraspVLA-playground/requirements.txt"'
            )
    elif method_name == "anygrasp":
        lines.extend(
            [
                'export SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL=True',
                'python -m pip install scikit-learn torch torchvision',
                f'python -m pip install -r "{remote_root}/third_party/upstreams/anygrasp_sdk/requirements.txt"',
                f'python -m pip install -r "{remote_root}/third_party/upstreams/GroundingDINO/requirements.txt"',
                'export CUDA_VISIBLE_DEVICES=""',
                'export FORCE_CUDA=0',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/GroundingDINO" --no-build-isolation',
                'unset CUDA_VISIBLE_DEVICES',
                'unset FORCE_CUDA',
                'SOABI=$(python -c \'import sysconfig; print(sysconfig.get_config_var("SOABI") or "")\')',
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
                'python -m pip install scikit-learn torch torchvision',
                f'python -m pip install -r "{remote_root}/third_party/upstreams/GroundingDINO/requirements.txt"',
                'export CUDA_VISIBLE_DEVICES=""',
                'export FORCE_CUDA=0',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/GroundingDINO" --no-build-isolation',
                'unset CUDA_VISIBLE_DEVICES',
                'unset FORCE_CUDA',
            ]
        )
        notes.extend(
            [
                "Contact-GraspNet upstream pins a legacy TensorFlow 2.2 / Python 3.7 stack that is not auto-installed here.",
                "You will need a dedicated legacy runtime before full Contact-GraspNet inference can be enabled.",
                "Run python -m grasp_benchmark.prepare_cgn --node <host> --bootstrap-legacy-env to probe or create the legacy runtime.",
            ]
        )
    else:
        raise ValueError(f"Unsupported method for remote install: {method_name}")

    lines.append('echo "INSTALL_OK"')
    return "\n".join(lines) + "\n", notes
