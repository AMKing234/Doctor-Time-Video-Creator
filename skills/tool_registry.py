"""Unified registry of every integrated skill / tool repository.

Each entry is vendored under vendor/ (either already cloned by this repo, or
fetchable with scripts/fetch_vendors.sh). Nothing here executes remote code:
the registry only reports presence and exposes integration hooks.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from common.paths import ROOT

VENDOR = ROOT / "vendor"


@dataclass(frozen=True)
class Tool:
    name: str
    repo: str
    folder: str
    kind: str
    purpose: str
    integration: str
    license: str = "see vendored LICENSE"
    runtime: str = "local"
    entry: str = ""


TOOLS: tuple[Tool, ...] = (
    Tool("youtube-agent-skill", "Jakeschincariol/youtube-agent-skill", "youtube-agent-skill",
         "content", "11 YouTube skills: script, SEO, package, edit, chapters, retention, shorts, audit",
         "wired into skills.youtube_agent + full pipeline", "MIT", "python",
         "skills/youtube_agent.py"),
    Tool("three.js", "mrdoob/three.js", "three.js",
         "visual", "3D WebGL/WebGPU rendering library",
         "powers the browser 3D thumbnail studio", "MIT", "browser",
         "dashboard/studio.html"),
    Tool("pixelfx", "patch-gg/pixelfx", "pixelfx",
         "visual", "244 pixel-art effects and animations with a generating skill",
         "optional thumbnail/sprite effect source", "see LICENSE", "browser",
         "vendor/pixelfx/src"),
    Tool("mcp-for-blender", "ahujasid/mcp-for-blender", "mcp-for-blender",
         "visual", "MCP server that drives Blender 3D from an LLM",
         "optional 3D scene renderer (needs Blender installed)", "MIT", "python+mcp",
         "vendor/mcp-for-blender"),
    Tool("react-three-rapier", "pmndrs/react-three-rapier", "react-three-rapier",
         "visual", "Physics for React Three Fiber",
         "optional animated 3D intro physics", "MIT", "browser",
         "vendor/react-three-rapier"),
    Tool("react-postprocessing", "pmndrs/react-postprocessing", "react-postprocessing",
         "visual", "Post-processing effects for React Three Fiber",
         "optional cinematic bloom / grade in 3D studio", "MIT", "browser",
         "vendor/react-postprocessing"),
    Tool("lemo-opuscar", "lemomo-ai/lemo-opuscar", "lemo-opuscar",
         "visual", "99 code-only film styles with example shorts",
         "cinematic look/style reference library", "see LICENSE", "reference",
         "vendor/lemo-opuscar"),
    Tool("librosa", "librosa/librosa", "librosa",
         "audio", "Python library for audio analysis and beat tracking",
         "music beat-sync for cuts and transitions", "ISC", "python",
         "vendor/librosa"),
    Tool("video-shotcraft", "Vincentwei1021/video-shotcraft", "video-shotcraft",
         "video", "Shot-crafting / shot-planning toolkit",
         "shot-list enhancement for the script engine", "see LICENSE", "python",
         "vendor/video-shotcraft"),
    Tool("ClaudeAnimationBase", "JohnHeibel/ClaudeAnimationBase", "ClaudeAnimationBase",
         "video", "Animation base for code-driven motion",
         "optional motion templates for visuals", "see LICENSE", "reference",
         "vendor/ClaudeAnimationBase"),
    Tool("opus-video-prompts", "joeseesun/opus-video-prompts", "opus-video-prompts",
         "content", "Curated video generation prompts",
         "visual prompt library for image generation", "see LICENSE", "reference",
         "vendor/opus-video-prompts"),
    Tool("awesome-opus5-5-videos", "yihui-dev/awesome-opus5-5-videos", "awesome-opus5-5-videos",
         "content", "Curated list of notable generated videos",
         "style/trend reference", "see LICENSE", "reference",
         "vendor/awesome-opus5-5-videos"),
)


def present(tool: Tool) -> bool:
    return (VENDOR / tool.folder).exists()


def report() -> dict[str, Any]:
    tools = []
    for tool in TOOLS:
        item = asdict(tool)
        item["present"] = present(tool)
        item["path"] = str(VENDOR / tool.folder)
        tools.append(item)
    return {
        "count": len(tools),
        "installed": sum(1 for t in tools if t["present"]),
        "by_kind": {k: sum(1 for t in tools if t["kind"] == k)
                    for k in sorted({t["kind"] for t in tools})},
        "tools": tools,
    }


def fetch_script() -> str:
    lines = ["#!/usr/bin/env bash", "# Fetch every optional vendored tool repository.",
             "set -euo pipefail", 'cd "$(dirname "$0")/.."', "mkdir -p vendor", ""]
    for tool in TOOLS:
        lines.append(f'[ -d "vendor/{tool.folder}" ] || git clone --depth 1 '
                     f'https://github.com/{tool.repo}.git "vendor/{tool.folder}"')
    lines.append('echo "All optional tools present in vendor/."')
    return "\n".join(lines) + "\n"
