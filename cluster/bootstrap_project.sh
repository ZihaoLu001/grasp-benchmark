#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-git@github.com:ZihaoLu001/grasp-benchmark.git}"
REMOTE_ROOT="${2:-/datasets/ss/current/zihao/grasp-benchmark}"
MINIFORGE_ROOT="${3:-/datasets/ss/current/zihao/miniforge3}"
CONDA_ENVS_DIR="${4:-/datasets/ss/current/zihao/conda/envs}"
CONDA_PKGS_DIR="${5:-/datasets/ss/current/zihao/conda/pkgs}"

tmp_dir="$(mktemp -d /tmp/grasp-benchmark-bootstrap.XXXXXX)"
trap 'rm -rf "${tmp_dir}"' EXIT

cat > "${tmp_dir}/install_miniforge.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
MINIFORGE_ROOT="${1}"
CONDA_ENVS_DIR="${2}"
CONDA_PKGS_DIR="${3}"
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
cat > "${MINIFORGE_ROOT}/.condarc" <<CONDARC
channels:
  - conda-forge
channel_priority: flexible
envs_dirs:
  - ${CONDA_ENVS_DIR}
pkgs_dirs:
  - ${CONDA_PKGS_DIR}
auto_activate_base: false
CONDARC
EOF

bash "${tmp_dir}/install_miniforge.sh" "${MINIFORGE_ROOT}" "${CONDA_ENVS_DIR}" "${CONDA_PKGS_DIR}"

if [[ -d "${REMOTE_ROOT}/.git" ]]; then
  git -C "${REMOTE_ROOT}" pull --ff-only
else
  git clone "${REPO_URL}" "${REMOTE_ROOT}"
fi

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

echo "BOOTSTRAP_OK"
