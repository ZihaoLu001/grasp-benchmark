from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from grasp_benchmark.paths import CONFIGS_DIR


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}, got {type(data)!r}")
    return data


def resolve_config_path(category: str, name: str) -> Path:
    return CONFIGS_DIR / category / f"{name}.yaml"


def load_named_config(category: str, name: str) -> dict[str, Any]:
    path = resolve_config_path(category, name)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return load_yaml(path)

