from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.remote_setup import build_method_install_script
from grasp_benchmark.shell import ssh_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Install method-specific dependencies on a remote cluster node.")
    parser.add_argument("--method", required=True, choices=["graspvla", "anygrasp", "cgn"])
    parser.add_argument("--node", default="", help="Remote node override.")
    parser.add_argument(
        "--include-playground",
        action="store_true",
        help="Also install GraspVLA playground Python requirements when method=graspvla.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the remote install script without executing it.")
    args = parser.parse_args()

    cluster_config = load_named_config("cluster", "default")
    method_config = load_named_config("methods", args.method)
    node = args.node or method_config.get("preferred_nodes", [cluster_config["default_graspvla_node"]])[0]
    script, notes = build_method_install_script(
        cluster_config=cluster_config,
        method_config=method_config,
        method_name=args.method,
        include_playground=args.include_playground,
    )

    if args.dry_run:
        print(script)
        return

    result = ssh_run(node, script, timeout=3600)
    artifact_dir = ARTIFACTS_DIR / "install"
    ensure_dir(artifact_dir)
    artifact_path = artifact_dir / f'{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}_{args.method}_{node}.json'
    artifact_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "method": args.method,
                "node": node,
                "ok": result.ok,
                "notes": notes,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if not result.ok:
        raise SystemExit(result.stderr or result.stdout)

    print(result.stdout.strip() or f"Installed {args.method} dependencies on {node}")
    if notes:
        for note in notes:
            print(f"NOTE: {note}")
    print(f"Wrote install record to {artifact_path}")


if __name__ == "__main__":
    main()
