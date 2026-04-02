#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-git@github.com:ZihaoLu001/grasp-benchmark.git}"
REMOTE_ROOT="${2:-/datasets/ss/current/zihao/grasp-benchmark}"

mkdir -p "$(dirname "${REMOTE_ROOT}")"

if [[ -d "${REMOTE_ROOT}/.git" ]]; then
  git -C "${REMOTE_ROOT}" pull --ff-only
else
  git clone "${REPO_URL}" "${REMOTE_ROOT}"
fi

mkdir -p "${REMOTE_ROOT}/third_party" "${REMOTE_ROOT}/artifacts"

