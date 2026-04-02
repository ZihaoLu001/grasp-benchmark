from __future__ import annotations

import argparse
import json

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.shell import ssh_run


def _build_remote_launch_script(
    cluster_config: dict,
    method_config: dict,
    model_path: str,
    port: int,
    compile_model: bool,
) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    remote_root = cluster_config["remote_root"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["env_name"]}'
    upstream_dir = f"{remote_root}/third_party/upstreams/GraspVLA"
    log_dir = f"{remote_root}/artifacts/server"
    compile_flag = "--compile" if compile_model else ""
    return "\n".join(
        [
            "set -e",
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


def _build_download_script(cluster_config: dict, method_config: dict) -> str:
    miniforge_root = cluster_config["miniforge_root"]
    cache_dir = method_config["model_cache_dir"]
    hf_repo = method_config["hf_repo"]
    env_prefix = f'{cluster_config["conda_envs_dir"]}/{method_config["env_name"]}'
    return "\n".join(
        [
            "set -e",
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


def _discover_remote_model(host: str, method_config: dict) -> str | None:
    cache_dir = method_config["model_cache_dir"]
    model_glob = method_config["model_glob"]
    script = "\n".join(
        [
            "set -e",
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


def _check_remote_port(host: str, port: int) -> bool:
    script = "\n".join(
        [
            "python3 - <<'PY'",
            "import socket",
            "sock = socket.socket()",
            "sock.settimeout(2.0)",
            "try:",
            f"    sock.connect(('127.0.0.1', {port}))",
            "except OSError:",
            "    print('DOWN')",
            "else:",
            "    print('UP')",
            "finally:",
            "    sock.close()",
            "PY",
        ]
    )
    result = ssh_run(host, script)
    return result.ok and "UP" in result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch or validate the remote GraspVLA model server.")
    parser.add_argument("--node", default="", help="Cluster node alias. Defaults to the cluster config default.")
    parser.add_argument("--port", type=int, default=0, help="Server port override.")
    parser.add_argument("--model-path", default="", help="Remote model path override.")
    parser.add_argument("--download-model", action="store_true", help="Download the model snapshot before launching.")
    parser.add_argument("--dry-run", action="store_true", help="Print the remote launch script without executing it.")
    parser.add_argument("--foreground", action="store_true", help="Reserved flag for future foreground mode.")
    args = parser.parse_args()

    if args.foreground:
        raise SystemExit("Foreground mode is not implemented yet.")

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", "graspvla")
    node = args.node or cluster_config["default_graspvla_node"]
    port = args.port or method_config["server"]["port"]

    if args.download_model:
        download_script = _build_download_script(cluster_config, method_config)
        if args.dry_run:
            print(download_script)
        else:
            download_result = ssh_run(node, download_script, timeout=1800)
            if not download_result.ok:
                raise SystemExit(download_result.stderr or download_result.stdout)

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
    health_ok = _check_remote_port(node, port)
    artifact = ARTIFACTS_DIR / "server" / f"graspvla_{node}_{port}.json"
    ensure_dir(artifact.parent)
    artifact.write_text(
        json.dumps(
            {
                "node": node,
                "port": port,
                "pid": pid,
                "model_path": model_path,
                "healthy": health_ok,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Launched GraspVLA on {node}:{port} with pid {pid}")
    print(f"Health check: {'UP' if health_ok else 'DOWN'}")
    print(f"Wrote launch record to {artifact}")


if __name__ == "__main__":
    main()
