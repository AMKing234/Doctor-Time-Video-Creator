#!/usr/bin/env python3
"""yt-seo-local: full SEO package + title/thumbnail pair lint."""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from common.paths import data_path
from common.utils import read_json, write_json
from skills import youtube_agent


def target_queries(seo: dict[str, Any], script: dict[str, Any]) -> list[str]:
    title = seo.get("title", "").replace("|", "").strip()
    category = str(script.get("category", "history")).replace("_", " ")
    return list(dict.fromkeys([title.lower(), f"{category} documentary",
                               f"{category} explained", f"{title.lower()} history"]))[:4]


def enhance(seo: dict[str, Any], script: dict[str, Any]) -> dict[str, Any]:
    thumb_text = " ".join(seo.get("title", "").split()[:4]).upper()
    lint = youtube_agent.lint_title(seo.get("title", ""), thumb_text)
    enhanced = dict(seo)
    enhanced["title_thumbnail_lint"] = lint
    enhanced["target_queries"] = target_queries(seo, script)
    enhanced["seo_skills_used"] = ["yt-seo", "yt-package", "yt-chapters"]
    out = data_path("seo", f"{seo.get('topic_id', 'unknown')}_{seo.get('language', 'en')}", "seo.json")
    if out.exists():
        write_json(out, enhanced)
    return enhanced


def main() -> None:
    parser = argparse.ArgumentParser(description="yt-seo-local")
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    seo_paths = glob.glob(str(data_path("seo", args.video_id, "seo.json")))
    if not seo_paths:
        raise SystemExit(f"No SEO package for {args.video_id}")
    seo = read_json(seo_paths[0], {}) or {}
    topic, lang = seo.get("topic_id", ""), seo.get("language", "en")
    script_paths = glob.glob(str(data_path("scripts", f"*_{lang}.json")))
    script = read_json(script_paths[0], {}) if script_paths else {}
    result = enhance(seo, script)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result["title"])


if __name__ == "__main__":
    main()
