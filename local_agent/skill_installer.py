"""Auto-setup from a 'skill report' (Markdown or JSON).

The report may declare pip modules, system packages and visual asset queries.
Only whitelisted actions are executed — no arbitrary shell commands.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from common.logging_setup import get_logger
from common.utils import run_command
from local_agent import asset_library, bootstrap

log = get_logger("skill_installer")


def parse_report(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    result: dict[str, Any] = {"pip": [], "pkg": [], "assets": [], "notes": []}

    # 1) Prefer a fenced or top-level JSON object.
    json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = json_blocks or ([text] if text.strip().startswith("{") else [])
    for block in candidates:
        try:
            data = json.loads(block)
            for key in result:
                if key in data:
                    value = data[key]
                    result[key].extend(value if isinstance(value, list) else [value])
        except json.JSONDecodeError:
            continue

    # 2) Bullet form: "- pip: requests", "pkg: ffmpeg", "asset: ancient rome".
    for line in text.splitlines():
        match = re.match(r"\s*[-*]?\s*(pip|pkg|asset|note)\s*:\s*(.+?)\s*$", line, re.I)
        if not match:
            continue
        key, value = match.group(1).lower(), match.group(2).strip()
        target = {"note": "notes"}.get(key, {"pip": "pip", "pkg": "pkg", "asset": "assets"}[key])
        if value not in result[target]:
            result[target].append(value)

    return {k: list(dict.fromkeys(v)) for k, v in result.items()}


def apply(report: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Install declared skills locally. Dry-run by default for safety."""
    actions: list[str] = []

    for module in report.get("pip", []):
        actions.append(f"pip install {module}")
        if not dry_run:
            run_command(["python3", "-m", "pip", "install", str(module)], check=False)

    for package in report.get("pkg", []):
        actions.append(f"pkg install -y {package}")
        if not dry_run:
            cmd = ["pkg", "install", "-y", package] if bootstrap._is_termux() else \
                  ["sudo", "apt-get", "install", "-y", package]
            run_command(cmd, check=False)

    for query in report.get("assets", []):
        actions.append(f"fetch assets: {query}")
        if not dry_run:
            try:
                asset_library.fetch(query, 6)
            except Exception as exc:  # noqa: BLE001
                log.warning("Asset fetch failed for '%s': %s", query, exc)

    if not dry_run:
        actions.append("refresh tool report")
        bootstrap.check()

    return {"dry_run": dry_run, "actions": actions, "tools": bootstrap.check()}
