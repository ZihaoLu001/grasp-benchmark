from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grasp_benchmark.paths import PROJECT_ROOT
from grasp_benchmark.shell import run_command


SYNC_METADATA_FILENAME = ".grasp-benchmark-sync.json"


def sync_metadata_path(project_root: Path = PROJECT_ROOT) -> Path:
    return project_root / SYNC_METADATA_FILENAME


def git_commit(project_root: Path = PROJECT_ROOT) -> str | None:
    result = run_command(["git", "-C", str(project_root), "rev-parse", "HEAD"])
    return result.stdout.strip() if result.ok else None


def git_branch(project_root: Path = PROJECT_ROOT) -> str | None:
    result = run_command(["git", "-C", str(project_root), "rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip() if result.ok else None


def load_sync_metadata(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    path = sync_metadata_path(project_root)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def resolve_commit(project_root: Path = PROJECT_ROOT) -> str:
    commit = git_commit(project_root)
    if commit:
        return commit
    return str(load_sync_metadata(project_root).get("commit", "unknown"))


def build_sync_metadata(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    return {
        "repository": "ZihaoLu001/grasp-benchmark",
        "commit": git_commit(project_root) or "unknown",
        "branch": git_branch(project_root) or "unknown",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "sync_source": "git_archive",
    }
