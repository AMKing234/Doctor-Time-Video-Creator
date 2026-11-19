#!/usr/bin/env python3
"""Direct local documentary maker — no scheduler, no cloud, no upload.

Examples
--------
python3 main.py --stage full                 # use curated topic + default duration
python3 main.py --stage research
python3 main.py --stage script
python3 main.py --stage voice
python3 main.py --stage visual
python3 main.py --stage video
python3 main.py --stage seo
python3 main.py --stage skills
python3 main.py --dashboard                  # 3D thumbnail studio
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any

from common.ai_client import AIClient
from common.config import load_settings
from common.logging_setup import get_logger
from common.paths import ROOT, data_path, ensure_dirs
from common.utils import read_json, setup_runtime
from database.manager import Database

log = get_logger("orchestrator")

STAGES = ["research", "script", "voice", "visual", "video", "seo", "skills", "full"]


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
        # A topic can have several regenerated script versions. Use only the
        # newest script per language so voice/visual/render run once each.
        by_lang: dict[str, dict[str, Any]] = {}
        for row in rows:
            language = str(row.get("language", "en"))
            if language not in by_lang:
                by_lang[language] = read_json(row["path"], {}) or {}
        return list(by_lang.values())

    def _load(self, folder: str, topic_id: str, lang: str, name: str) -> dict[str, Any]:
        candidates = glob.glob(str(data_path(folder, f"{topic_id}_{lang}", name)))
        if not candidates:
            raise FileNotFoundError(f"Missing {folder}/{name} for {topic_id}/{lang}")
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

    def research_topic(self, topic: dict[str, Any]) -> dict[str, Any]:
        """Research a caller-supplied topic (used by make_video.py)."""
        from research.engine import ResearchEngine
        return ResearchEngine(self.db, self.ai).research(topic)

    def script(self, research: dict[str, Any] | None = None,
               languages: list[str] | None = None,
               test_mode: bool | None = None) -> list[dict[str, Any]]:
        from script_engine.generator import ScriptEngine

        payload = research or self._latest_research()
        langs = languages or self.settings.get("content", {}).get("languages", ["hi", "en"])
        test = self.test_mode if test_mode is None else test_mode
        engine = ScriptEngine(self.db, self.ai)
        return [engine.generate(payload, lang, test_mode=test) for lang in langs]

    def voice(self) -> list[dict[str, Any]]:
        from voice_engine.engine import VoiceEngine
        engine = VoiceEngine()
        return [engine.generate(s) for s in self._scripts()]

    def visual(self) -> list[dict[str, Any]]:
        from visual_engine.engine import VisualEngine
        engine = VisualEngine()
        return [engine.generate(s) for s in self._scripts()]

    def video(self) -> list[dict[str, Any]]:
        from animation_engine.engine import AnimationEngine
        from video_editor.engine import VideoEditor
        animator, editor = AnimationEngine(), VideoEditor()
        results = []
        for script in self._scripts():
            topic, lang = script["topic_id"], script["language"]
            visual = self._load("visual", topic, lang, "visual_manifest.json")
            audio = self._load("voice", topic, lang, "voice_manifest.json")
            animation = animator.generate(visual, audio)
            results.append(editor.render(script, animation, audio))
        if results:
            self.db.mark_topic_used(results[0]["topic_id"])
        return results

    def seo(self) -> list[dict[str, Any]]:
        from seo_engine.engine import SEOEngine
        from thumbnail_engine.engine import ThumbnailEngine
        seo_engine, thumb = SEOEngine(self.ai, self.db), ThumbnailEngine()
        results = []
        for script in self._scripts():
            topic, lang = script["topic_id"], script["language"]
            render = self._load("videos", topic, lang, "render_manifest.json")
            visual = self._load("visual", topic, lang, "visual_manifest.json")
            package = seo_engine.generate(script, render)
            package["thumbnail"] = thumb.generate(script, visual)["path"]
            results.append(package)
        return results

    def skills_stage(self) -> dict[str, Any]:
        """Run every integrated skill and save the result locally."""
        from skills import youtube_agent
        from skills.resource import estimate
        from skills.seo_skill import enhance
        from local_agent.fallback import ensure_delivered
        from common.utils import write_json

        reports: list[dict[str, Any]] = []

        def safe(fn, *args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        for script in self._scripts():
            topic, lang = script["topic_id"], script["language"]
            video_id = f"{topic}_{lang}"
            render, seo = {}, {}
            try:
                render = self._load("videos", topic, lang, "render_manifest.json")
            except FileNotFoundError:
                pass
            seo_paths = glob.glob(str(data_path("seo", video_id, "seo.json")))
            if seo_paths:
                seo = read_json(seo_paths[0], {}) or {}

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
                "delivery": ensure_delivered(None, video_id, "direct local production"),
            }
            write_json(data_path("skills", video_id, "skills_report.json"), report)
            reports.append(report)

        return {"reports": reports, "skills_used": youtube_agent.available()["skills"]}

    def full(self, research: dict[str, Any] | None = None,
             languages: list[str] | None = None) -> dict[str, Any]:
        payload = research or self.research()
        scripts = self.script(payload, languages=languages)
        self.voice()
        self.visual()
        renders = self.video()
        self.seo()
        skills = self.skills_stage()
        return {
            "topic": payload.get("title", {}).get("en", ""),
            "videos": [r["video_path"] for r in renders],
            "skills": len(skills["skills_used"]),
            "deliveries": [r["delivery"] for r in skills["reports"]],
            "scripts": [{"language": s["language"], "minutes": round(s["estimated_duration"] / 60, 1)}
                        for s in scripts],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Direct Local Documentary Maker")
    parser.add_argument("--stage", choices=STAGES, default="full")
    parser.add_argument("--test", action="store_true", help="short smoke-test run")
    parser.add_argument("--dashboard", action="store_true", help="launch 3D thumbnail studio dashboard")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dashboard:
        from dashboard.app import run_dashboard
        run_dashboard()
        return 0

    pipeline = Pipeline(test_mode=args.test)
    try:
        if args.stage == "full":
            result = pipeline.full()
        else:
            method = "skills_stage" if args.stage == "skills" else args.stage
            result = getattr(pipeline, method)()
        print("\n=== RESULT ===")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str)[:6000])
        return 0
    except Exception as exc:  # noqa: BLE001
        log.exception("Failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
