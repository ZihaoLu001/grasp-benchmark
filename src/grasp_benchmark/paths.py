from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
THIRD_PARTY_DIR = PROJECT_ROOT / "third_party"
UPSTREAMS_DIR = THIRD_PARTY_DIR / "upstreams"
CLUSTER_DIR = PROJECT_ROOT / "cluster"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

