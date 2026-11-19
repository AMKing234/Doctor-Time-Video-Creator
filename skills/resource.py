#!/usr/bin/env python3
"""yt-resource: duration, word-budget, render-time and storage estimator."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from common.utils import read_json


def estimate(script: dict[str, Any], render: dict[str, Any] | None = None) -> dict[str, Any]:
    scenes = script.get("scenes", [])
    words = sum(len(str(s.get("text", "")).split()) for s in scenes)
    spoken_minutes = words / 155.0
    scene_count = len(scenes)
    duration = float(render.get("duration", 0)) if render else spoken_minutes * 60
    render_minutes = round(scene_count * 0.35 + 0.5, 1)
    storage_mb = round(duration * 0.62, 1)
    return {
        "title": script.get("title", "unknown"),
        "language": script.get("language", "unknown"),
        "scene_count": scene_count,
        "word_count": words,
        "spoken_minutes": round(spoken_minutes, 1),
        "actual_duration_seconds": round(duration, 1),
        "estimated_render_minutes": render_minutes,
        "estimated_mp4_mb": storage_mb,
        "recommended_scene_seconds": round(spoken_minutes * 60 / max(1, scene_count), 1),
        "target_minutes_met": 20 <= (duration / 60) <= 25 if duration else None,
        "note": "Estimates assume ~155 wpm narration and CRF 21 at 1920x1080.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="yt-resource estimator")
    parser.add_argument("--script", required=True)
    parser.add_argument("--render", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    script = read_json(args.script, {}) or {}
    render = read_json(args.render, {}) if args.render else None
    result = estimate(script, render)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
