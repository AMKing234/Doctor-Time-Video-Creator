#!/usr/bin/env python3
"""Local node control centre.

All YouTube credentials stay on this device in local_agent/vault/.
The cloud node only receives non-secret manifests through the sync branch.
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

from common.config import load_settings
from common.control import (
    automation_enabled, set_automation_enabled, set_upload_enabled, upload_override,
)
from common.paths import data_path
from common.utils import iso_now, read_json
from database.manager import Database
from local_agent import asset_library, bootstrap, skill_installer, sync, youtube_setup
from skills import tool_registry


def _print(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def full_status() -> dict[str, Any]:
    upload = upload_override()
    if upload is None:
        upload = bool(load_settings().get("upload", {}).get("enabled", False))
    return {
        "node": "local",
        "automation": "ON" if automation_enabled() else "OFF",
        "youtube_upload": "ON" if upload else "OFF (dry-run)",
        "tools": bootstrap.check(),
        "assets": asset_library.report(),
        "youtube": youtube_setup.status(),
        "sync": sync.status(),
        "tools_registry": tool_registry.report(),
        "database": Database().stats(),
    }


def upload_local(video_id: str, publish_at: str | None = None) -> dict[str, Any]:
    """Upload a rendered video from the local machine using the local vault."""
    if not automation_enabled():
        return {"status": "skipped", "reason": "master automation is OFF"}
    if upload_override() is not True:
        return {"status": "skipped", "reason": "YouTube upload switch is OFF (dry-run)"}

    seo_paths = glob.glob(str(data_path("seo", f"*_{video_id.split('_')[-1]}", "seo.json")))
    seo_paths += glob.glob(str(data_path("seo", video_id, "seo.json")))
    if not seo_paths:
        raise FileNotFoundError(f"No SEO package found for {video_id}")
    seo = read_json(seo_paths[0], {}) or {}

    render_paths = glob.glob(str(data_path("videos", video_id, "render_manifest.json")))
    if not render_paths:
        raise FileNotFoundError(f"No render manifest found for {video_id}")
    render = read_json(render_paths[0], {}) or {}

    thumb = glob.glob(str(data_path("thumbnails", video_id, "thumbnail.jpg")))
    return youtube_setup.upload(
        render["video_path"], seo,
        thumbnail_path=thumb[0] if thumb else None,
        publish_at=publish_at,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local node for AI Documentary Factory")
    p.add_argument("--status", action="store_true", help="full local status")
    p.add_argument("--on", action="store_true", help="turn master automation ON")
    p.add_argument("--off", action="store_true", help="turn master automation OFF")
    p.add_argument("--upload-on", action="store_true", help="turn local YouTube upload ON")
    p.add_argument("--upload-off", action="store_true", help="turn YouTube upload OFF (dry-run)")
    p.add_argument("--setup-youtube", metavar="CLIENT_SECRETS_JSON",
                   help="import local OAuth client secrets, connect and verify")
    p.add_argument("--verify-youtube", action="store_true")
    p.add_argument("--tools-check", action="store_true")
    p.add_argument("--tools-install", action="store_true")
    p.add_argument("--assets-fetch", metavar="QUERY")
    p.add_argument("--asset-report", action="store_true")
    p.add_argument("--apply-skill-report", metavar="PATH")
    p.add_argument("--apply", action="store_true", help="actually apply the skill report")
    p.add_argument("--sync-status", action="store_true")
    p.add_argument("--sync-push", metavar="TYPE", help="queue a non-secret message (e.g. status_request)")
    p.add_argument("--sync-pull", action="store_true")
    p.add_argument("--run-local", metavar="STAGE", help="run a pipeline stage locally")
    p.add_argument("--test", action="store_true", help="short local smoke run")
    p.add_argument("--upload-video", metavar="VIDEO_ID")
    p.add_argument("--publish-at", default=None)
    p.add_argument("--skills-list", action="store_true", help="list all integrated skills/tools")
    p.add_argument("--tools-registry", action="store_true", help="show all vendored tools and fetch script")
    p.add_argument("--skills-run", action="store_true", help="run all skills on latest production")
    p.add_argument("--local-save", metavar="VIDEO_ID", help="save assets + REPORT.txt locally")
    p.add_argument("--seo-skill", metavar="VIDEO_ID", help="run full SEO skill on a video")
    p.add_argument("--resource", metavar="SCRIPT_JSON", help="estimate duration/resources")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.on:
        set_automation_enabled(True); print("Automation ON")
    if args.off:
        set_automation_enabled(False); print("Automation OFF")
    if args.upload_on:
        set_upload_enabled(True); print("YouTube upload ON (live)")
    if args.upload_off:
        set_upload_enabled(False); print("YouTube upload OFF (dry-run)")

    if args.setup_youtube:
        _print(youtube_setup.setup(args.setup_youtube))
    if args.verify_youtube:
        _print(youtube_setup.status())
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

    if args.sync_status:
        _print(sync.status())
    if args.sync_push:
        _print(sync.push({"type": args.sync_push, "node": "local",
                          "created_at": iso_now()}, name=args.sync_push))
    if args.sync_pull:
        _print({"received": sync.pull()})

    if args.run_local:
        from main import Pipeline, STAGES
        if args.run_local not in STAGES:
            print(f"Unknown stage: {args.run_local}. Choose from {STAGES}")
            return 1
        if not automation_enabled():
            print("Automation is OFF. Run with --on first.")
            return 0
        method = "skills_stage" if args.run_local == "skills" else args.run_local
        result = getattr(Pipeline(test_mode=args.test), method)()
        _print(result)

    if args.upload_video:
        _print(upload_local(args.upload_video, args.publish_at))

    if args.skills_list:
        from skills import youtube_agent
        _print(youtube_agent.available())

    if args.tools_registry:
        _print(tool_registry.report())

    if args.skills_run:
        from main import Pipeline
        _print(Pipeline().skills_stage())

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
