#!/usr/bin/env bash
set -euo pipefail

MINIFORGE_ROOT="${1:-/datasets/ss/current/zihao/miniforge3}"
REMOTE_ROOT="${2:-/datasets/ss/current/zihao/grasp-benchmark}"
CONDA_ENVS_DIR="${3:-/datasets/ss/current/zihao/conda/envs}"

source "${MINIFORGE_ROOT}/etc/profile.d/conda.sh"

for env_file in "${REMOTE_ROOT}/cluster/gb-core.yml" "${REMOTE_ROOT}/cluster/gb-anygrasp.yml" "${REMOTE_ROOT}/cluster/gb-cgn.yml"; do
  env_name="$(basename "${env_file}" .yml)"
  prefix="${CONDA_ENVS_DIR}/${env_name}"
  if [[ -d "${prefix}" ]]; then
    conda env update -p "${prefix}" -f "${env_file}" --prune
  else
    conda env create -p "${prefix}" -f "${env_file}"
  fi
  conda run -p "${prefix}" python -m pip install -e "${REMOTE_ROOT}"
done
