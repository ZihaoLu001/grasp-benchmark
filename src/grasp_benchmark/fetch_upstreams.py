from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from grasp_benchmark.methods import UPSTREAMS, UPSTREAMS_BY_NAME
from grasp_benchmark.paths import ARTIFACTS_DIR, ensure_dir
from grasp_benchmark.shell import run_command


def _clone_or_update(destination: Path, url: str, update: bool, shallow: bool) -> tuple[bool, str]:
    if destination.exists():
        if not update:
            return True, "exists"
        result = run_command(["git", "-C", str(destination), "pull", "--ff-only"])
        return result.ok, (result.stdout + result.stderr).strip()

    ensure_dir(destination.parent)
    args = ["git", "clone"]
    if shallow:
        args.extend(["--depth", "1"])
    args.extend([url, str(destination)])
    result = run_command(args)
    return result.ok, (result.stdout + result.stderr).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Clone or update required upstream repositories.")
    parser.add_argument("--update", action="store_true", help="Update existing upstream clones.")
    parser.add_argument("--no-shallow", action="store_true", help="Clone full history instead of depth=1.")
    parser.add_argument("--only", default="", help="Comma-separated subset of upstream names.")
    args = parser.parse_args()

    requested = {item.strip() for item in args.only.split(",") if item.strip()}
    selected = [UPSTREAMS_BY_NAME[name] for name in requested] if requested else list(UPSTREAMS)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [],
    }
    for spec in selected:
        ok, message = _clone_or_update(
            destination=spec.local_dir,
            url=spec.url,
            update=args.update,
            shallow=not args.no_shallow,
        )
        manifest["items"].append(
            {
                "name": spec.name,
                "url": spec.url,
                "path": str(spec.local_dir),
                "ok": ok,
                "message": message,
            }
        )
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {spec.name}: {spec.local_dir}")

    artifact = ARTIFACTS_DIR / "upstreams" / "manifest.json"
    ensure_dir(artifact.parent)
    artifact.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote upstream manifest to {artifact}")


if __name__ == "__main__":
    main()

