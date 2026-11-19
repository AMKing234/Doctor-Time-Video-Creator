#!/usr/bin/env python3
"""Local utility CLI for the direct documentary maker.

No scheduler, no cloud sync, no YouTube credentials — everything runs here.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any

# Allow `python3 local_agent/agent.py ...` from any working directory.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from common.paths import data_path
from common.utils import read_json
from database.manager import Database
from local_agent import asset_library, bootstrap, skill_installer
from skills import tool_registry


def _print(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def full_status() -> dict[str, Any]:
    return {
        "node": "local-termux",
        "mode": "direct (no scheduler, no upload)",
        "tools": bootstrap.check(),
        "assets": asset_library.report(),
        "tools_registry": tool_registry.report(),
        "database": Database().stats(),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local utilities — AI Documentary Factory")
    p.add_argument("--status", action="store_true", help="full local status")
    p.add_argument("--tools-check", action="store_true")
    p.add_argument("--tools-install", action="store_true")
    p.add_argument("--assets-fetch", metavar="QUERY")
    p.add_argument("--asset-report", action="store_true")
    p.add_argument("--apply-skill-report", metavar="PATH")
    p.add_argument("--apply", action="store_true", help="actually apply the skill report")
    p.add_argument("--skills-list", action="store_true", help="list all integrated skills/tools")
    p.add_argument("--tools-registry", action="store_true", help="show all vendored tools")
    p.add_argument("--local-save", metavar="VIDEO_ID", help="save assets + REPORT.txt locally")
    p.add_argument("--seo-skill", metavar="VIDEO_ID", help="run full SEO skill on a video")
    p.add_argument("--resource", metavar="SCRIPT_JSON", help="estimate duration/resources")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.tools_check:
        _print(bootstrap.check())
    if args.tools_install:
        _print(bootstrap.install())
    if args.assets_fetch:
        _print(asset_library.fetch(args.assets_fetch))
    if args.asset_report:
        _print(asset_library.report())
    if args.apply_skill_report:
        report = skill_installer.parse_report(args.apply_skill_report)
        _print({"report": report, "result": skill_installer.apply(report, dry_run=not args.apply)})
    if args.skills_list:
        from skills import youtube_agent
        _print(youtube_agent.available())
    if args.tools_registry:
        _print(tool_registry.report())
    if args.local_save:
        from local_agent.fallback import local_save
        _print(local_save(args.local_save, "manual local save requested"))
    if args.seo_skill:
        from skills.seo_skill import enhance
        paths = glob.glob(str(data_path("seo", args.seo_skill, "seo.json")))
        if not paths:
            raise SystemExit(f"No SEO package for {args.seo_skill}")
        seo = read_json(paths[0], {}) or {}
        scripts = glob.glob(str(data_path("scripts", f"*_{seo.get('language', 'en')}.json")))
        script = read_json(scripts[0], {}) if scripts else {}
        _print(enhance(seo, script))
    if args.resource:
        from skills.resource import estimate
        _print(estimate(read_json(args.resource, {}) or {}))

    if args.status or not any(vars(args).values()):
        _print(full_status())
    return 0


if __name__ == "__main__":
    sys.exit(main())
