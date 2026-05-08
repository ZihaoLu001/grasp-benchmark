from __future__ import annotations

import argparse
import base64
import json
import re
from datetime import datetime, timezone

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.shell import ssh_run


def _build_remote_script(cluster_config: dict, method_config: dict) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["env_name"]}'
    remote_root = cluster_config["remote_root"]
    anygrasp_root = f"{remote_root}/third_party/upstreams/anygrasp_sdk"
    return f"""
set -eo pipefail
ADDR2LINE="${{ADDR2LINE:-addr2line}}"
source "{miniforge_root}/etc/profile.d/conda.sh"
conda activate "{env_prefix}"
OPENSSL_COMPAT_DIR=""
for candidate in \
  /usr/local/cuda-11.8/nsight-systems-2022.4.2/host-linux-x64 \
  /usr/local/cuda-11.8/nsight-compute-2022.3.0/host/linux-desktop-glibc_2_11_3-x64 \
  /usr/local/cuda-12.1/nsight-systems-2023.1.2/host-linux-x64 \
  /usr/local/cuda-12.1/nsight-compute-2023.1.1/host/linux-desktop-glibc_2_11_3-x64 \
  /usr/local/cuda-12.3/nsight-systems-2023.3.3/host-linux-x64 \
  /usr/local/cuda-12.3/nsight-compute-2023.3.1/host/linux-desktop-glibc_2_11_3-x64
do
  if [ -f "$candidate/libcrypto.so.1.1" ] && [ -f "$candidate/libssl.so.1.1" ]; then
    OPENSSL_COMPAT_DIR="$candidate"
    break
  fi
done
if [ -n "$OPENSSL_COMPAT_DIR" ]; then
  ln -sf "$OPENSSL_COMPAT_DIR/libcrypto.so.1.1" "$CONDA_PREFIX/lib/libcrypto.so.1.1"
  ln -sf "$OPENSSL_COMPAT_DIR/libssl.so.1.1" "$CONDA_PREFIX/lib/libssl.so.1.1"
fi
SOABI=$(python -c 'import sysconfig; print(sysconfig.get_config_var("SOABI") or "")')
if [ -z "$SOABI" ]; then
  echo "__GB_ERROR__=missing_soabi"
  exit 1
fi
cp -f "{anygrasp_root}/grasp_detection/gsnet_versions/gsnet.${{SOABI}}.so" "{anygrasp_root}/grasp_detection/gsnet.so"
cp -f "{anygrasp_root}/license_registration/lib_cxx_versions/lib_cxx.${{SOABI}}.so" "{anygrasp_root}/grasp_detection/lib_cxx.so"
echo "__GB_SOABI__=${{SOABI}}"
set +e
FEATURE_OUTPUT=$(cd "{anygrasp_root}/license_registration" && LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${{LD_LIBRARY_PATH:-}}" ./license_checker -f 2>&1)
FEATURE_STATUS=$?
set -e
echo "__GB_FEATURE_STATUS__=${{FEATURE_STATUS}}"
printf '__GB_FEATURE_B64__=%s\\n' "$(printf '%s' "$FEATURE_OUTPUT" | base64 -w0)"
set +e
IMPORT_OUTPUT=$(cd "{anygrasp_root}/grasp_detection" && PYTHONPATH=. python -c 'import numpy as np; np.float = getattr(np, "float", float); np.int = getattr(np, "int", int); np.bool = getattr(np, "bool", bool); from gsnet import AnyGrasp; print("ANYGRASP_IMPORT_OK")' 2>&1)
IMPORT_STATUS=$?
set -e
echo "__GB_IMPORT_STATUS__=${{IMPORT_STATUS}}"
printf '__GB_IMPORT_B64__=%s\\n' "$(printf '%s' "$IMPORT_OUTPUT" | base64 -w0)"
if [ -f "{anygrasp_root}/grasp_detection/log/checkpoint_detection.tar" ]; then
  echo "__GB_CHECKPOINT_PRESENT__=1"
else
  echo "__GB_CHECKPOINT_PRESENT__=0"
fi
"""


def _decode_b64(value: str) -> str:
    if not value:
        return ""
    return base64.b64decode(value.encode("ascii")).decode("utf-8", errors="replace")


def _extract_feature_id(output: str) -> str:
    candidates = re.findall(r"\b\d{8,}\b", output)
    return candidates[-1] if candidates else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the AnyGrasp SDK binaries and inspect license state.")
    parser.add_argument("--node", default="lakeshore", help="Remote node to inspect.")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "anygrasp")
    result = ssh_run(args.node, _build_remote_script(cluster_config, method_config), timeout=300)

    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.startswith("__GB_"):
            continue
        key, _, value = line.partition("=")
        parsed[key] = value

    feature_output = _decode_b64(parsed.get("__GB_FEATURE_B64__", ""))
    import_output = _decode_b64(parsed.get("__GB_IMPORT_B64__", ""))
    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node": args.node,
        "ok": result.ok,
        "soabi": parsed.get("__GB_SOABI__", ""),
        "feature_status": int(parsed.get("__GB_FEATURE_STATUS__", "-1") or -1),
        "feature_output": feature_output,
        "feature_id": _extract_feature_id(feature_output),
        "import_status": int(parsed.get("__GB_IMPORT_STATUS__", "-1") or -1),
        "import_output": import_output,
        "checkpoint_present": parsed.get("__GB_CHECKPOINT_PRESENT__", "0") == "1",
        "stderr": result.stderr,
    }
    artifact["license_ready"] = artifact["import_status"] == 0 and "ANYGRASP_IMPORT_OK" in import_output

    output_dir = ensure_dir(ARTIFACTS_DIR / "anygrasp")
    artifact_path = output_dir / f'{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}_{args.node}.json'
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    print(f"Wrote AnyGrasp preparation artifact to {artifact_path}")


if __name__ == "__main__":
    main()
