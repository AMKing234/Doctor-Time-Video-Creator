"""Collect and verify every tool needed for local video production.

Design goal: one failed optional dependency (e.g. cryptography on Termux) must
never block the essential pipeline. Modules are grouped and installed one at a
time, with Termux-native `pkg` fallbacks where pip wheels cannot build.
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any

from common.config import load_settings
from common.paths import ROOT
from common.utils import read_json, run_command

LOCAL_CFG = read_json(ROOT / "config" / "local.json", {}) or {}

# Essential = the local pipeline cannot render without these.
# Optional  = enhancements (thumbnails via PIL, S3 backup) that degrade gracefully.
ESSENTIAL_MODULES = ["requests", "edge_tts", "flask"]
OPTIONAL_MODULES = ["PIL", "boto3"]

# Termux-native package names for modules that fail to build with pip on Android.
TERMUX_PKG_FOR_MODULE = {
    "PIL": "python-pillow",
    "boto3": "python-boto3",
}


def _is_termux() -> bool:
    return "com.termux" in str(ROOT)


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def check() -> dict[str, Any]:
    """Report which commands, modules and fonts are available."""
    tools = LOCAL_CFG.get("tools", {})
    commands = {name: bool(shutil.which(name)) for name in tools.get("commands", [])}
    modules = {name: _has(name) for name in tools.get("python_modules", [])}
    fonts = [p for p in tools.get("fonts", []) if Path(p).exists()]

    essential_missing = [m for m in ESSENTIAL_MODULES if not _has(m)]
    optional_missing = [m for m in OPTIONAL_MODULES if not _has(m)]
    cmds_missing = [c for c, ok in commands.items() if not ok]

    return {
        "commands": commands,
        "python_modules": modules,
        "fonts": fonts,
        "essential_missing": essential_missing + cmds_missing + ([] if fonts else ["font"]),
        "optional_missing": optional_missing,
        # Ready means the core local pipeline works, not that every extra is installed.
        "all_ready": not essential_missing and not cmds_missing and bool(fonts),
        "optional_ready": not optional_missing,
        "termux": _is_termux(),
    }


def _install_command(command: str) -> str:
    if _is_termux():
        result = run_command(["pkg", "install", "-y", command], check=False)
    else:
        result = run_command(["sudo", "apt-get", "install", "-y", command], check=False)
    return "ok" if result.returncode == 0 else (result.stderr or "")[-300:]


def _install_module(module: str) -> str:
    """Install a single module, preferring pip, then a Termux-native package."""
    pip_name = {"PIL": "Pillow"}.get(module, module)

    result = run_command(
        ["python3", "-m", "pip", "install", "--disable-pip-version-check", pip_name],
        check=False,
    )
    if result.returncode == 0 and _has(module):
        return "pip"

    pkg_name = TERMUX_PKG_FOR_MODULE.get(module)
    if _is_termux() and pkg_name:
        status = _install_command(pkg_name)
        if _has(module):
            return f"pkg:{pkg_name}"
        return f"failed (pip + {pkg_name}: {status})"

    return "failed: " + (result.stderr or "")[-300:]


def install() -> dict[str, Any]:
    """Install missing commands and modules independently; never fail wholesale."""
    actions: dict[str, str] = {}

    for command, ok in check()["commands"].items():
        if not ok:
            actions[f"cmd:{command}"] = _install_command(command)

    for module in ESSENTIAL_MODULES + OPTIONAL_MODULES:
        if not _has(module):
            actions[f"pip:{module}"] = _install_module(module)

    report = check()
    report["actions"] = actions
    return report
