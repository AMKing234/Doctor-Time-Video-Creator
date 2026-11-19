"""Central path resolution. Runtime files live INSIDE the repository folder
but are git-ignored (data/, storage/, logs/)."""
from __future__ import annotations

import os
from pathlib import Path


def get_root() -> Path:
    env = os.environ.get("AUTOMATION_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


ROOT = get_root()
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
STORAGE_DIR = ROOT / "storage"
LOGS_DIR = ROOT / "logs"


def ensure_dir(path: str | Path) -> Path:
    """Create a directory (and parents) and return it as Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_path(*parts: str) -> Path:
    return DATA_DIR.joinpath(*parts)


def storage_path(*parts: str) -> Path:
    return STORAGE_DIR.joinpath(*parts)


def ensure_dirs() -> None:
    for d in (DATA_DIR, STORAGE_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
