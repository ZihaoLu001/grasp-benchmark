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
                'unset CUDA_HOME',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/GroundingDINO" --no-build-isolation',
            ]
        )
        notes.extend(
            [
                "AnyGrasp still needs MinkowskiEngine to be built against the target CUDA toolkit.",
                "AnyGrasp inference also requires a license registration step before the SDK binary will run.",
            ]
        )
    elif method_name == "cgn":
        lines.extend(
            [
                'export SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL=True',
                'python -m pip install scikit-learn torch torchvision',
                f'python -m pip install -r "{remote_root}/third_party/upstreams/GroundingDINO/requirements.txt"',
                'unset CUDA_HOME',
                f'python -m pip install -e "{remote_root}/third_party/upstreams/GroundingDINO" --no-build-isolation',
            ]
        )
        notes.extend(
            [
                "Contact-GraspNet upstream pins a legacy TensorFlow 2.2 / Python 3.7 stack that is not auto-installed here.",
                "You will need a dedicated legacy runtime before full Contact-GraspNet inference can be enabled.",
            ]
        )
    else:
        raise ValueError(f"Unsupported method for remote install: {method_name}")

    lines.append('echo "INSTALL_OK"')
    return "\n".join(lines) + "\n", notes
