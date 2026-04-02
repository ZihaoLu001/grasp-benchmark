#!/usr/bin/env bash
set -euo pipefail

MINIFORGE_ROOT="${1:-/datasets/ss/current/zihao/miniforge3}"
REMOTE_ROOT="${2:-/datasets/ss/current/zihao/grasp-benchmark}"

source "${MINIFORGE_ROOT}/etc/profile.d/conda.sh"

for env_file in "${REMOTE_ROOT}/cluster/gb-core.yml" "${REMOTE_ROOT}/cluster/gb-anygrasp.yml" "${REMOTE_ROOT}/cluster/gb-cgn.yml"; do
  env_name="$(basename "${env_file}" .yml)"
  if conda env list | awk '{print $1}' | grep -qx "${env_name}"; then
    conda env update -n "${env_name}" -f "${env_file}" --prune
  else
    conda env create -f "${env_file}"
  fi
  conda run -n "${env_name}" python -m pip install -e "${REMOTE_ROOT}"
done

