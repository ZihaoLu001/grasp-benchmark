#!/usr/bin/env bash
set -euo pipefail

MINIFORGE_ROOT="${1:-/datasets/ss/current/zihao/miniforge3}"
CONDA_ENVS_DIR="${2:-/datasets/ss/current/zihao/conda/envs}"
CONDA_PKGS_DIR="${3:-/datasets/ss/current/zihao/conda/pkgs}"
INSTALLER_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"

mkdir -p "${CONDA_ENVS_DIR}" "${CONDA_PKGS_DIR}"

if [[ ! -x "${MINIFORGE_ROOT}/bin/conda" ]]; then
  tmp_installer="$(mktemp /tmp/miniforge.XXXXXX.sh)"
  if command -v curl >/dev/null 2>&1; then
    curl -L "${INSTALLER_URL}" -o "${tmp_installer}"
  else
    wget -O "${tmp_installer}" "${INSTALLER_URL}"
  fi
  bash "${tmp_installer}" -b -p "${MINIFORGE_ROOT}"
  rm -f "${tmp_installer}"
fi

cat > "${MINIFORGE_ROOT}/.condarc" <<EOF
channels:
  - conda-forge
channel_priority: flexible
envs_dirs:
  - ${CONDA_ENVS_DIR}
pkgs_dirs:
  - ${CONDA_PKGS_DIR}
auto_activate_base: false
EOF

"${MINIFORGE_ROOT}/bin/conda" info --base

