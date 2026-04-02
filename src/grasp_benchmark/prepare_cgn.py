from __future__ import annotations

import argparse
import base64
import json
from datetime import datetime, timezone

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.shell import ssh_run


def _build_remote_script(cluster_config: dict, method_config: dict, *, bootstrap_legacy_env: bool, compile_tf_ops: bool) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["legacy_env_name"]}'
    cgn_root = f"{remote_root}/third_party/upstreams/contact_graspnet"
    checkpoint_dir = f"{cgn_root}/{method_config['checkpoint_relpath']}"

    bootstrap_lines = []
    if bootstrap_legacy_env:
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
        bootstrap_lines.append(
            f'conda run -p "{env_prefix}" bash -lc \'cd "{cgn_root}" && export CUDA_HOME="${{CUDA_HOME:-/usr/local/cuda}}" && sh compile_pointnet_tfops.sh\''
        )

    bootstrap_block = "\n".join(bootstrap_lines)
    return f"""
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
PY_OUTPUT=$(conda run -p "{env_prefix}" python -c 'import sys; print(sys.version.split()[0])' 2>&1)
PY_STATUS=$?
TF_OUTPUT=$(conda run -p "{env_prefix}" python -c 'import tensorflow as tf; print(tf.__version__)' 2>&1)
TF_STATUS=$?
RUNNER_OUTPUT=$(PYTHONPATH="{remote_root}/src" conda run -p "{env_prefix}" python -c 'import grasp_benchmark.runners.contact_graspnet as runner; print("RUNNER_IMPORT_OK")' 2>&1)
RUNNER_STATUS=$?
set -e
echo "__GB_PY_STATUS__=${{PY_STATUS}}"
printf '__GB_PY_B64__=%s\\n' "$(printf '%s' "$PY_OUTPUT" | base64 -w0)"
echo "__GB_TF_STATUS__=${{TF_STATUS}}"
printf '__GB_TF_B64__=%s\\n' "$(printf '%s' "$TF_OUTPUT" | base64 -w0)"
echo "__GB_RUNNER_STATUS__=${{RUNNER_STATUS}}"
printf '__GB_RUNNER_B64__=%s\\n' "$(printf '%s' "$RUNNER_OUTPUT" | base64 -w0)"
"""


def _decode_b64(value: str) -> str:
    if not value:
        return ""
    return base64.b64decode(value.encode("ascii")).decode("utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and probe the Contact-GraspNet legacy runtime.")
    parser.add_argument("--node", default="em14")
    parser.add_argument("--bootstrap-legacy-env", action="store_true")
    parser.add_argument("--compile-tf-ops", action="store_true")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
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
