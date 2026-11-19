"""Adapter for the vendored `youtube-agent-skill` pack (MIT, Jake Schincariol).

All 11 skills are available; the six Python tools are called directly with JSON
output so they can run unattended in the local node or in GitHub Actions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common.paths import ROOT
from common.utils import run_command

PACK = ROOT / "vendor" / "youtube-agent-skill" / "skills"

TOOLS = {
    "hookscore": PACK / "yt-script" / "hookscore.py",
    "title": PACK / "yt-package" / "title.py",
    "deadair": PACK / "yt-edit" / "deadair.py",
    "chapters": PACK / "yt-chapters" / "chapters.py",
    "retention": PACK / "yt-retention" / "retention.py",
    "swipe": PACK / "yt-viral" / "swipe.py",
}

SKILLS = [
    "yt-script", "yt-package", "yt-edit", "yt-comment", "yt-plan", "yt-viral",
    "yt-retention", "yt-shorts", "yt-seo", "yt-chapters", "yt-audit",
]


def available() -> dict[str, Any]:
    return {
        "source": "https://github.com/Jakeschincariol/youtube-agent-skill",
        "license": "MIT",
        "skills": SKILLS,
        "tools": {name: str(path) for name, path in TOOLS.items() if path.exists()},
        "tools_ready": all(p.exists() for p in TOOLS.values()),
    }


def run(tool: str, args: list[str], json_mode: bool = True) -> Any:
    script = TOOLS.get(tool)
    if not script or not script.exists():
        raise FileNotFoundError(f"Skill tool not found: {tool}")
    cmd = ["python3", str(script), *args]
    if json_mode:
        cmd.append("--json")
    result = run_command(cmd, check=False)
    output = (result.stdout or "").strip()
    if json_mode and output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output, "returncode": result.returncode}
    return {"output": output, "returncode": result.returncode}


def score_hook(hook: str) -> Any:
    return run("hookscore", ["--hook", hook])


def lint_title(title: str, thumbnail_text: str = "") -> Any:
    return run("title", ["--title", title, "--thumb", thumbnail_text])


def chapters(srt_path: str | Path, target: int = 8) -> Any:
    return run("chapters", [str(srt_path), "--target", str(target)])


def edit_decision_list(srt_path: str | Path) -> Any:
    return run("deadair", [str(srt_path)])


def retention(csv_path: str | Path, srt_path: str | Path | None = None) -> Any:
    args = [str(csv_path)]
    if srt_path:
        args += ["--transcript", str(srt_path)]
    return run("retention", args)


def viral(data_path: str | Path) -> Any:
    return run("swipe", [str(data_path)])
