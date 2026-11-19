"""Load config/*.json with environment-variable overrides."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from common.paths import CONFIG_DIR
from common.utils import read_json


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def load_settings() -> dict[str, Any]:
    settings: dict[str, Any] = read_json(CONFIG_DIR / "settings.json", {}) or {}

    # Environment overrides let GitHub Secrets control behaviour without edits.
    if os.environ.get("AI_API_KEY"):
        settings.setdefault("ai", {})["api_key"] = os.environ["AI_API_KEY"]
    if os.environ.get("AI_API_BASE"):
        settings.setdefault("ai", {})["api_base"] = os.environ["AI_API_BASE"]
    if os.environ.get("AI_MODEL"):
        settings.setdefault("ai", {})["model"] = os.environ["AI_MODEL"]
    if os.environ.get("IMAGE_API_KEY"):
        settings.setdefault("image", {})["api_key"] = os.environ["IMAGE_API_KEY"]
    if os.environ.get("VOICE_ENGINE"):
        settings.setdefault("voice", {})["engine"] = os.environ["VOICE_ENGINE"]
    if os.environ.get("KINGVOICE_REPO_PATH"):
        settings.setdefault("voice", {})["kingvoice_repo_path"] = os.environ["KINGVOICE_REPO_PATH"]
    if os.environ.get("STORAGE_PROVIDER"):
        settings.setdefault("storage", {})["provider"] = os.environ["STORAGE_PROVIDER"]
    if os.environ.get("YOUTUBE_ENABLED"):
        settings.setdefault("upload", {})["enabled"] = _env_bool(
            os.environ.get("YOUTUBE_ENABLED"), False
        )
    if os.environ.get("NOTIFY_WEBHOOK_URL"):
        settings.setdefault("notifications", {})["webhook_url"] = os.environ["NOTIFY_WEBHOOK_URL"]

    settings.setdefault("ai", {"api_key": "", "api_base": "https://api.openai.com/v1", "model": "gpt-4o-mini"})
    settings.setdefault("image", {"api_key": "", "api_base": "https://api.openai.com/v1", "model": "gpt-image-1"})
    return settings


@lru_cache(maxsize=1)
def load_languages() -> dict[str, Any]:
    return read_json(CONFIG_DIR / "languages.json", {}) or {}


@lru_cache(maxsize=1)
def load_channel() -> dict[str, Any]:
    return read_json(CONFIG_DIR / "channel.json", {}) or {}


def get_setting(path: str, default: Any = None) -> Any:
    """Dot-path lookup, e.g. get_setting('video.width')."""
    node: Any = load_settings()
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node
