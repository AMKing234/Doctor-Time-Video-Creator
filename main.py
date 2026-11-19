#!/usr/bin/env python3
"""AI Documentary Factory — command line orchestrator.

Examples
--------
python main.py --stage full --test          # end-to-end local smoke run
python main.py --stage research
python main.py --stage script
python main.py --stage voice
python main.py --stage visual
python main.py --stage video
python main.py --stage seo
python main.py --stage upload               # DRY RUN unless explicitly enabled
python main.py --stage analytics
python main.py --dashboard
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path
from typing import Any

from common.ai_client import AIClient
from common.config import load_settings
from common.control import automation_enabled, set_automation_enabled, set_upload_enabled
from common.logging_setup import get_logger
from common.paths import ROOT, data_path, ensure_dirs
from common.utils import read_json, setup_runtime
from database.manager import Database

log = get_logger("orchestrator")

STAGES = ["research", "script", "voice", "visual", "video", "seo",
          "upload", "analytics", "skills", "full"]


class Pipeline:
    def __init__(self, test_mode: bool = False) -> None:
        setup_runtime()
        self.test_mode = test_mode
        self.db = Database()
        self.ai = AIClient()
        self.settings = load_settings()

    # -- helpers ----------------------------------------------------------
    def _latest_research(self) -> dict[str, Any]:
        files = sorted(glob.glob(str(data_path("research", "*.json"))),
                       key=lambda p: Path(p).stat().st_mtime, reverse=True)
        if not files:
            from topic_engine.discovery import TopicEngine
            from research.engine import ResearchEngine
            topic = TopicEngine(self.db).select()
            if not topic:
                raise RuntimeError("No topic could be selected")
            return ResearchEngine(self.db, self.ai).research(topic)
        return read_json(files[0], {}) or {}

    def _scripts(self, topic_id: str | None = None) -> list[dict[str, Any]]:
        rows = self.db.records("scripts", 50)
        if topic_id:
            rows = [r for r in rows if r["topic_id"] == topic_id]
        if not rows:
            return []
        newest_topic = rows[0]["topic_id"]
        rows = [r for r in rows if r["topic_id"] == newest_topic]
        return [read_json(r["path"], {}) for r in rows]

    def _load(self, folder: str, topic_id: str, lang: str, name: str) -> dict[str, Any]:
        candidates = glob.glob(str(data_path(folder, f"{topic_id}_{lang}", name)))
        if not candidates:
            raise FileNotFoundError(f"Missing {folder}/{name} for {topic_id}/{lang}; run earlier stage first")
        return read_json(candidates[0], {}) or {}

    # -- stages -----------------------------------------------------------
    def research(self) -> dict[str, Any]:
        from topic_engine.discovery import TopicEngine
        from research.engine import ResearchEngine
        from error_handler.handler import ErrorTracker

        def work() -> dict[str, Any]:
            topic = TopicEngine(self.db).select()
            if not topic:
                raise RuntimeError("No topic selected")
            return ResearchEngine(self.db, self.ai).research(topic)
        return ErrorTracker(self.db).run("research", work)

    def script(self) -> list[dict[str, Any]]:
        from script_engine.generator import ScriptEngine
        from error_handler.handler import ErrorTracker
        research = self._latest_research()

        def work() -> list[dict[str, Any]]:
            engine = ScriptEngine(self.db, self.ai)
            return [engine.generate(research, lang, test_mode=self.test_mode)
                    for lang in self.settings.get("content", {}).get("languages", ["hi", "en"])]
        return ErrorTracker(self.db).run("script", work)

    def voice(self) -> list[dict[str, Any]]:
        from voice_engine.engine import VoiceEngine
        from error_handler.handler import ErrorTracker
        engine = VoiceEngine()

        def work() -> list[dict[str, Any]]:
            return [engine.generate(s) for s in self._scripts()]
        return ErrorTracker(self.db).run("voice", work)

    def visual(self) -> list[dict[str, Any]]:
        from visual_engine.engine import VisualEngine
        from error_handler.handler import ErrorTracker
        engine = VisualEngine()

        def work() -> list[dict[str, Any]]:
            return [engine.generate(s) for s in self._scripts()]
        return ErrorTracker(self.db).run("visual", work)

    def video(self) -> list[dict[str, Any]]:
        from animation_engine.engine import AnimationEngine
        from video_editor.engine import VideoEditor
        from error_handler.handler import ErrorTracker
        animator, editor = AnimationEngine(), VideoEditor()

        def work() -> list[dict[str, Any]]:
            results = []
            for script in self._scripts():
                topic, lang = script["topic_id"], script["language"]
                visual = self._load("visual", topic, lang, "visual_manifest.json")
                audio = self._load("voice", topic, lang, "voice_manifest.json")
                animation = animator.generate(visual, audio)
                results.append(editor.render(script, animation, audio))
            self.db.mark_topic_used(results[0]["topic_id"] if results else "")
            return results
        return ErrorTracker(self.db).run("video", work)

    def seo(self) -> list[dict[str, Any]]:
        from seo_engine.engine import SEOEngine
        from thumbnail_engine.engine import ThumbnailEngine
        from error_handler.handler import ErrorTracker
        seo_engine, thumb = SEOEngine(self.ai, self.db), ThumbnailEngine()

        def work() -> list[dict[str, Any]]:
            results = []
            for script in self._scripts():
                topic, lang = script["topic_id"], script["language"]
                render = self._load("videos", topic, lang, "render_manifest.json")
                visual = self._load("visual", topic, lang, "visual_manifest.json")
                package = seo_engine.generate(script, render)
                package["thumbnail"] = thumb.generate(script, visual)["path"]
                results.append(package)
            return results
        return ErrorTracker(self.db).run("seo", work)

    def archive(self) -> list[dict[str, Any]]:
        from storage.store import AssetStore
        store = AssetStore()
        archived = []
        for script in self._scripts():
            topic, lang = script["topic_id"], script["language"]
            render = self._load("videos", topic, lang, "render_manifest.json")
            files = {
                f"{topic}/{lang}/video.mp4": render["video_path"],
                f"{topic}/{lang}/captions.srt": render["subtitle_path"],
            }
            seo_files = glob.glob(str(data_path("seo", f"{topic}_{lang}", "seo.json")))
            thumb_files = glob.glob(str(data_path("thumbnails", f"{topic}_{lang}", "thumbnail.jpg")))
            if seo_files:
                files[f"{topic}/{lang}/seo.json"] = seo_files[0]
            if thumb_files:
                files[f"{topic}/{lang}/thumbnail.jpg"] = thumb_files[0]
            archived.extend(store.put_many(files))
        return archived

    def upload(self) -> list[dict[str, Any]]:
        from youtube_uploader.uploader import YouTubeUploader
        from scheduler.scheduler import Scheduler
        from error_handler.handler import ErrorTracker
        uploader = YouTubeUploader(self.db)
        slot = Scheduler().optimal_publish_at()

        def work() -> list[dict[str, Any]]:
            results = []
            rows = [r for r in self.db.records("videos", 50)]
            for row in rows:
                seo_files = glob.glob(str(data_path("seo", f"{row['topic_id']}_{row['language']}", "seo.json")))
                if not seo_files:
                    continue
                seo = read_json(seo_files[0], {}) or {}
                render_files = glob.glob(str(data_path("videos", f"{row['topic_id']}_{row['language']}", "render_manifest.json")))
                if not render_files:
                    continue
                render = read_json(render_files[0], {}) or {}
                thumb_files = glob.glob(str(data_path("thumbnails", f"{row['topic_id']}_{row['language']}", "thumbnail.jpg")))
                thumbnail = {"path": thumb_files[0]} if thumb_files else None
                results.append(uploader.upload(seo, render, thumbnail, slot))
            return results
        return ErrorTracker(self.db).run("upload", work, attempts=2)

    def skills_stage(self, uploads: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Run every integrated skill and guarantee local delivery if not uploaded."""
        from skills import youtube_agent
        from skills.resource import estimate
        from skills.seo_skill import enhance
        from local_agent.fallback import ensure_delivered
        from common.utils import write_json

        reports: list[dict[str, Any]] = []
        uploads = uploads or []

        def safe(fn, *args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        for script in self._scripts():
            topic, lang = script["topic_id"], script["language"]
            video_id = f"{topic}_{lang}"
            out_dir = data_path("skills", video_id)
            render = {}
            seo = {}
            try:
                render = self._load("videos", topic, lang, "render_manifest.json")
            except FileNotFoundError:
                pass
            seo_paths = glob.glob(str(data_path("seo", video_id, "seo.json")))
            if seo_paths:
                seo = read_json(seo_paths[0], {}) or {}

            upload_result = next((u for u in uploads if u.get("video_id") == video_id), None)
            report = {
                "video_id": video_id,
                "skills": youtube_agent.available(),
                "hook_score": safe(youtube_agent.score_hook,
                                   script["scenes"][0]["text"] if script.get("scenes") else ""),
                "title_thumbnail_lint": safe(youtube_agent.lint_title,
                                             seo.get("title", script.get("title", "")),
                                             seo.get("title", "")[:28].upper()),
                "resource": safe(estimate, script, render or None),
                "seo": safe(enhance, seo or {"topic_id": topic, "language": lang}, script)
                if seo else {"skipped": True},
                "chapters": safe(youtube_agent.chapters, render.get("subtitle_path", ""))
                if render.get("subtitle_path") else {"skipped": True},
                "edit_decision_list": safe(youtube_agent.edit_decision_list,
                                           render.get("subtitle_path", ""))
                if render.get("subtitle_path") else {"skipped": True},
                "delivery": ensure_delivered(upload_result, video_id,
                                             "upload not performed; saved locally"),
            }
            write_json(out_dir / "skills_report.json", report)
            reports.append(report)

        result = {"reports": reports, "skills_used": youtube_agent.available()["skills"]}
        log.info("Skills stage complete: %d videos, %d skills", len(reports), len(result["skills_used"]))
        return result

    def analytics(self) -> dict[str, Any]:
        from analytics_engine.engine import AnalyticsEngine
        from error_handler.handler import ErrorTracker
        return ErrorTracker(self.db).run("analytics", AnalyticsEngine(self.db).collect)

    def full(self) -> dict[str, Any]:
        self.research()
        self.script()
        self.voice()
        self.visual()
        renders = self.video()
        self.seo()
        archived = self.archive()
        uploads = self.upload()
        skills = self.skills_stage(uploads)
        report = self.analytics()
        return {
            "videos": [r["video_path"] for r in renders],
            "archived": [a["uri"] for a in archived],
            "uploads": [u["mode"] for u in uploads],
            "skills": len(skills["skills_used"]),
            "deliveries": [r["delivery"] for r in skills["reports"]],
            "best_hour": report["recommendation"]["best_hour_ist"],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI YouTube Documentary Factory")
    parser.add_argument("--stage", choices=STAGES, default="full")
    parser.add_argument("--test", action="store_true", help="short smoke-test run")
    parser.add_argument("--dashboard", action="store_true", help="launch monitoring dashboard")
    parser.add_argument("--automation", choices=["on", "off"], help="set master automation switch and exit")
    parser.add_argument("--upload", choices=["on", "off"], help="set YouTube upload switch and exit")
    parser.add_argument("--topic-category", default=None, help="restrict research to a category")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dashboard:
        from dashboard.app import run_dashboard
        run_dashboard()
        return 0

    if args.automation:
        state = args.automation == "on"
        set_automation_enabled(state)
        print(f"Master automation: {'ON' if state else 'OFF'}")
        return 0

    if args.upload:
        state = args.upload == "on"
        set_upload_enabled(state)
        print(f"YouTube upload: {'ON (live)' if state else 'OFF (dry-run)'}")
        return 0

    if not automation_enabled():
        print("Automation is OFF. Turn it ON from the dashboard or run:")
        print("  python main.py --automation on")
        return 0

    pipeline = Pipeline(test_mode=args.test)
    from notifications.notifier import Notifier
    notifier = Notifier()
    notifier.send("Pipeline started", f"Stage: {args.stage} | root: {ROOT}", "info")
    try:
        if args.stage == "full":
            result = pipeline.full()
        else:
            method = "skills_stage" if args.stage == "skills" else args.stage
            result = getattr(pipeline, method)()
        print("\n=== STAGE RESULT ===")
        if isinstance(result, (dict, list)):
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2)[:6000])
        else:
            print(result)
        notifier.send("Pipeline finished", f"Stage {args.stage} completed", "success")
        return 0
    except Exception as exc:  # noqa: BLE001
        log.exception("Pipeline failed: %s", exc)
        notifier.send("Pipeline failed", str(exc), "error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
