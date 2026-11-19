"""Runtime ON/OFF switches, controlled from the dashboard or CLI.

Stored in data/control.json (git-ignored) so toggling never dirties the repo.
Environment variables can override for GitHub Actions:
  AUTOMATION_ENABLED=true|false   -> master pipeline switch
  YOUTUBE_ENABLED=true|false      -> upload switch (handled by uploader)
When a value is absent, config defaults apply.
"""
from __future__ import annotations

import os
from typing import Any

from common.paths import data_path
from common.utils import read_json, write_json

CONTROL_FILE = data_path("control.json")


def get_control() -> dict[str, Any]:
    return read_json(CONTROL_FILE, {}) or {}


def _switch(name: str, env_name: str) -> bool | None:
    control = get_control()
    if name in control:
        return bool(control[name])
    env = os.environ.get(env_name, "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True
    if env in {"0", "false", "no", "off"}:
        return False
    return None


def automation_enabled() -> bool:
    """Master switch. Default ON when never configured."""
    value = _switch("automation_enabled", "AUTOMATION_ENABLED")
    return True if value is None else value


def upload_override() -> bool | None:
    """Dashboard-set upload switch, or None to use config/env defaults."""
    control = get_control()
    value = control.get("upload_enabled")
    return bool(value) if value is not None else None


def set_automation_enabled(enabled: bool) -> dict[str, Any]:
    control = get_control()
    control["automation_enabled"] = bool(enabled)
    write_json(CONTROL_FILE, control)
    return control


def set_upload_enabled(enabled: bool) -> dict[str, Any]:
    control = get_control()
    control["upload_enabled"] = bool(enabled)
    write_json(CONTROL_FILE, control)
    return control
