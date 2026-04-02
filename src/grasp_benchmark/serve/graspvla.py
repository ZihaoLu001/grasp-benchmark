from __future__ import annotations

import argparse
import json
from typing import Any

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, PROJECT_ROOT, ensure_dir
from grasp_benchmark.provenance import resolve_commit
from grasp_benchmark.remote_setup import build_method_install_script
from grasp_benchmark.shell import ssh_run


def _env_prefix(cluster_config: dict[str, Any], method_config: dict[str, Any]) -> str:
    return f'{cluster_config["conda_envs_dir"]}/{method_config["env_name"]}'


def _build_remote_launch_script(
    cluster_config: dict[str, Any],
    method_config: dict[str, Any],
    model_path: str,
    port: int,
    compile_model: bool,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = _env_prefix(cluster_config, method_config)
    upstream_dir = f"{remote_root}/third_party/upstreams/GraspVLA"
    log_dir = f"{remote_root}/artifacts/server"
    compile_flag = "--compile" if compile_model else ""
    return "\n".join(
        [
            "set -euo pipefail",
            f'mkdir -p "{log_dir}"',
            f'source "{miniforge_root}/etc/profile.d/conda.sh"',
            f'conda activate "{env_prefix}"',
            f'cd "{upstream_dir}"',
            (
                f'nohup python -u -m vla_network.scripts.serve '
                f'--path "{model_path}" --port {port} {compile_flag} '
                f'> "{log_dir}/graspvla_{port}.log" 2>&1 & echo $!'
            ),
        ]
    ) + "\n"


def _build_download_script(cluster_config: dict[str, Any], method_config: dict[str, Any]) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    cache_dir = method_config["model_cache_dir"]
    hf_repo = method_config["hf_repo"]
    env_prefix = _env_prefix(cluster_config, method_config)
    return "\n".join(
        [
            "set -euo pipefail",
            f'mkdir -p "{cache_dir}"',
            f'source "{miniforge_root}/etc/profile.d/conda.sh"',
            f'conda activate "{env_prefix}"',
            "python - <<'PY'",
            "from huggingface_hub import snapshot_download",
            f"snapshot_download(repo_id='{hf_repo}', local_dir='{cache_dir}', local_dir_use_symlinks=False)",
            "print('DOWNLOAD_OK')",
            "PY",
        ]
    ) + "\n"


def _discover_remote_model(host: str, method_config: dict[str, Any]) -> str | None:
    cache_dir = method_config["model_cache_dir"]
    model_glob = method_config["model_glob"]
    script = "\n".join(
        [
            "set -euo pipefail",
            "python3 - <<'PY'",
            "from pathlib import Path",
            f"matches = sorted(Path('{cache_dir}').rglob('{model_glob}'))",
            "print(matches[0] if matches else '')",
            "PY",
        ]
    )
    result = ssh_run(host, script)
    if not result.ok or not result.stdout.strip():
        return None
    return result.stdout.strip().splitlines()[-1]


def _build_validate_script(
    cluster_config: dict[str, Any],
    method_config: dict[str, Any],
    port: int,
    timeout_s: int,
    retries: int,
    retry_sleep_s: int,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    env_prefix = _env_prefix(cluster_config, method_config)
    return "\n".join(
        [
            "set -euo pipefail",
            f'source "{miniforge_root}/etc/profile.d/conda.sh"',
            f'conda activate "{env_prefix}"',
            "python - <<'PY'",
            "import json",
            "import sys",
            "import time",
            "import numpy as np",
            "import zmq",
            f"port = {port}",
            f"timeout_s = {timeout_s}",
            f"retries = {retries}",
            f"retry_sleep_s = {retry_sleep_s}",
            "last_error = ''",
            "for attempt in range(1, retries + 1):",
            "    context = zmq.Context()",
            "    socket = context.socket(zmq.REQ)",
            "    socket.setsockopt(zmq.RCVTIMEO, timeout_s * 1000)",
            "    socket.setsockopt(zmq.SNDTIMEO, timeout_s * 1000)",
            "    socket.setsockopt(zmq.LINGER, 0)",
            "    try:",
            "        socket.connect(f'tcp://127.0.0.1:{port}')",
            "        mock_image = np.zeros((256, 256, 3), dtype=np.uint8)",
            "        mock_proprio = [np.concatenate([np.zeros(6, dtype=np.float32), np.ones(1, dtype=np.float32)]) for _ in range(4)]",
            "        request = {",
            "            'front_view_image': [mock_image],",
            "            'side_view_image': [mock_image],",
            "            'proprio_array': mock_proprio,",
            "            'text': 'Validation test instruction',",
            "        }",
            "        socket.send_pyobj(request)",
            "        response = socket.recv_pyobj()",
            "        if not isinstance(response, dict) or not response.get('result'):",
            "            raise RuntimeError(f'Unexpected response payload: {type(response)!r}')",
            "        first_action = [float(value) for value in response['result'][0]]",
            "        print(json.dumps({'ok': True, 'attempt': attempt, 'first_action': first_action}))",
            "        sys.exit(0)",
            "    except Exception as exc:",
            "        last_error = str(exc)",
            "        if attempt < retries:",
            "            time.sleep(retry_sleep_s)",
            "    finally:",
            "        socket.close()",
            "        context.term()",
            "print(json.dumps({'ok': False, 'attempts': retries, 'error': last_error}))",
            "sys.exit(1)",
            "PY",
        ]
    ) + "\n"


def _validate_remote_server(
    host: str,
    cluster_config: dict[str, Any],
    method_config: dict[str, Any],
    port: int,
    timeout_s: int,
    retries: int,
    retry_sleep_s: int,
) -> tuple[bool, dict[str, Any]]:
    script = _build_validate_script(
        cluster_config=cluster_config,
        method_config=method_config,
        port=port,
        timeout_s=timeout_s,
        retries=retries,
        retry_sleep_s=retry_sleep_s,
    )
    result = ssh_run(host, script, timeout=max(timeout_s * retries + retry_sleep_s * retries + 30, 60))
    last_line = ""
    for line in reversed(result.stdout.splitlines()):
        if line.strip():
            last_line = line.strip()
            break
    payload: dict[str, Any] = {}
    if last_line.startswith("{"):
        payload = json.loads(last_line)
    elif result.stderr.strip():
        payload = {"ok": False, "error": result.stderr.strip()}
    return result.ok, payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch or validate the remote GraspVLA model server.")
    parser.add_argument("--node", default="", help="Cluster node alias. Defaults to the cluster config default.")
    parser.add_argument("--port", type=int, default=0, help="Server port override.")
    parser.add_argument("--model-path", default="", help="Remote model path override.")
    parser.add_argument("--download-model", action="store_true", help="Download the model snapshot before launching.")
    parser.add_argument("--install-deps", action="store_true", help="Install GraspVLA Python dependencies on the node.")
    parser.add_argument("--include-playground", action="store_true", help="Also install playground Python requirements.")
    parser.add_argument("--dry-run", action="store_true", help="Print the remote launch script without executing it.")
    parser.add_argument("--foreground", action="store_true", help="Reserved flag for future foreground mode.")
    parser.add_argument("--skip-validate", action="store_true", help="Skip mock inference validation after launch.")
    parser.add_argument("--validate-timeout", type=int, default=5, help="Per-attempt timeout for validation inference.")
    parser.add_argument("--validate-retries", type=int, default=36, help="How many validation attempts to make.")
    parser.add_argument("--validate-retry-sleep", type=int, default=10, help="Sleep between validation attempts.")
    args = parser.parse_args()

    if args.foreground:
        raise SystemExit("Foreground mode is not implemented yet.")

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    node = args.node or cluster_config["default_graspvla_node"]
    port = args.port or method_config["server"]["port"]

    if args.install_deps:
        install_script, _notes = build_method_install_script(
            cluster_config=cluster_config,
            method_config=method_config,
            method_name="graspvla",
            include_playground=args.include_playground,
        )
        if args.dry_run:
            print(install_script)
        else:
            install_result = ssh_run(node, install_script, timeout=3600)
            if not install_result.ok:
                raise SystemExit(install_result.stderr or install_result.stdout)

    if args.download_model:
        download_script = _build_download_script(cluster_config, method_config)
        if args.dry_run:
            print(download_script)
        else:
            download_result = ssh_run(node, download_script, timeout=1800)
            if not download_result.ok:
                raise SystemExit(download_result.stderr or download_result.stdout)

    if args.dry_run and not args.model_path:
        print("# Pass --model-path to print the exact launch command, or rerun without --dry-run after downloading.")
        return

    model_path = args.model_path or _discover_remote_model(node, method_config)
    if not model_path:
        raise SystemExit(
            "Could not find a remote GraspVLA model. Pass --model-path or rerun with --download-model."
        )

    launch_script = _build_remote_launch_script(
        cluster_config=cluster_config,
        method_config=method_config,
        model_path=model_path,
        port=port,
        compile_model=bool(method_config["server"].get("compile", True)),
    )
    if args.dry_run:
        print(launch_script)
        return

    result = ssh_run(node, launch_script, timeout=60)
    if not result.ok:
        raise SystemExit(result.stderr or result.stdout)

    pid = result.stdout.strip().splitlines()[-1]
    validation_ok = False
    validation_payload: dict[str, Any] = {}
    if not args.skip_validate:
        validation_ok, validation_payload = _validate_remote_server(
            host=node,
            cluster_config=cluster_config,
            method_config=method_config,
            port=port,
            timeout_s=args.validate_timeout,
            retries=args.validate_retries,
            retry_sleep_s=args.validate_retry_sleep,
        )
        if not validation_ok:
            raise SystemExit(json.dumps(validation_payload, indent=2))

    artifact = ARTIFACTS_DIR / "server" / f"graspvla_{node}_{port}.json"
    ensure_dir(artifact.parent)
    artifact.write_text(
        json.dumps(
            {
                "node": node,
                "port": port,
                "pid": pid,
                "model_path": model_path,
                "validated": validation_ok,
                "validation": validation_payload,
                "commit": resolve_commit(PROJECT_ROOT),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Launched GraspVLA on {node}:{port} with pid {pid}")
    if validation_payload:
        print(json.dumps(validation_payload, indent=2))
    print(f"Wrote launch record to {artifact}")


if __name__ == "__main__":
    main()
