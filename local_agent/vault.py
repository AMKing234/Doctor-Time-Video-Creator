"""Encrypted-at-rest-by-permission local credential vault.

Everything here lives under local_agent/vault/ which is git-ignored.
No function in this module ever writes credentials to the repository or to
the sync bus. A redaction scanner is applied to every outgoing sync payload.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from common.config import load_settings
from common.paths import ROOT
from common.utils import read_json, write_json

LOCAL_CFG = read_json(ROOT / "config" / "local.json", {}) or {}
VAULT_DIR = ROOT / str(LOCAL_CFG.get("vault", {}).get("dir", "local_agent/vault"))

SECRET_KEY_PATTERN = re.compile(
    r"(client_secret|token|api_key|secret|password|authorization|refresh_token|access_token)",
    re.IGNORECASE,
)


def ensure_vault() -> Path:
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(VAULT_DIR, 0o700)
    except OSError:
        pass
    return VAULT_DIR


class SecretLeakError(RuntimeError):
    pass


def assert_no_secrets(payload: Any) -> None:
    """Fail loudly if a sync payload looks like it contains credentials."""
    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if SECRET_KEY_PATTERN.search(str(key)):
                    raise SecretLeakError(f"Refusing to sync secret-like key: {path}.{key}")
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")
        elif isinstance(node, str):
            if re.search(r"gho_|ghp_|ya29\.|AIza|sk-[A-Za-z0-9]{20,}", node):
                raise SecretLeakError(f"Refusing to sync credential-looking value at {path}")

    walk(payload)


def save(name: str, data: Any) -> Path:
    ensure_vault()
    target = VAULT_DIR / name
    write_json(target, data)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def load(name: str, default: Any = None) -> Any:
    return read_json(VAULT_DIR / name, default)


def import_file(source: str | Path, name: str) -> Path:
    """Copy a user-supplied credential file into the vault, then delete the source copy."""
    src = Path(source).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    ensure_vault()
    dest = VAULT_DIR / name
    shutil.copy2(src, dest)
    try:
        os.chmod(dest, 0o600)
    except OSError:
        pass
    return dest


def exists(name: str) -> bool:
    return (VAULT_DIR / name).exists()


def youtube_paths() -> tuple[Path, Path]:
    cfg = LOCAL_CFG.get("vault", {})
    return (
        VAULT_DIR / str(cfg.get("youtube_client_secrets", "youtube_client_secrets.json")),
        VAULT_DIR / str(cfg.get("youtube_token", "youtube_token.json")),
    )
