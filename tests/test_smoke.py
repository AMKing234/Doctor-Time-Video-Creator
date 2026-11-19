"""Fast offline smoke tests — no network, no API keys required."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from common.config import load_settings, load_languages, load_channel
from common.utils import slugify, srt_time, write_json, read_json, retry
from database.manager import Database
from research.knowledge_base import SEED_TOPICS
from script_engine.generator import _template_scenes, _duration_for
from seo_engine.engine import timestamp
from common.paths import ROOT


class ConfigTests(unittest.TestCase):
    def test_configs_load(self):
        self.assertTrue(load_settings())
        self.assertIn("hi", load_languages())
        self.assertIn("en", load_languages())
        self.assertTrue(load_channel()["name"])

    def test_upload_disabled_by_default(self):
        self.assertFalse(load_settings()["upload"]["enabled"])
        self.assertTrue(load_settings()["upload"]["dry_run"])


class UtilTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_srt_time(self):
        self.assertEqual(srt_time(61.25), "00:01:01,250")

    def test_timestamp(self):
        self.assertEqual(timestamp(3725), "1:02:05")

    def test_json_roundtrip(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            write_json(p, {"a": 1})
            self.assertEqual(read_json(p)["a"], 1)

    def test_retry(self):
        calls = {"n": 0}

        @retry(attempts=3, delay=0)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise ValueError("once")
            return 42

        self.assertEqual(flaky(), 42)
        self.assertEqual(calls["n"], 2)


class DatabaseTests(unittest.TestCase):
    def test_topic_history(self):
        with TemporaryDirectory() as d:
            db = Database(Path(d) / "test.db")
            topic = SEED_TOPICS[0]
            db.upsert_topic({
                "id": topic["id"], "category": topic["category"],
                "title": topic["title"], "tags": topic["tags"], "score": 0.8,
            })
            self.assertFalse(db.is_topic_used(topic["id"]))
            db.mark_topic_used(topic["id"])
            self.assertTrue(db.is_topic_used(topic["id"]))
            self.assertGreaterEqual(db.stats()["topics"], 1)

    def test_run_error_tracking(self):
        with TemporaryDirectory() as d:
            from error_handler.handler import ErrorTracker
            db = Database(Path(d) / "test.db")
            tracker = ErrorTracker(db)
            self.assertEqual(tracker.run("unit", lambda: 7), 7)
            with self.assertRaises(Exception):
                tracker.run("unit", lambda: 1 / 0, attempts=1)
            self.assertGreaterEqual(db.stats()["errors"], 1)


class ContentTests(unittest.TestCase):
    def test_every_topic_is_bilingual(self):
        self.assertGreaterEqual(len(SEED_TOPICS), 12)
        for topic in SEED_TOPICS:
            self.assertTrue(topic["title"]["en"] and topic["title"]["hi"])
            self.assertGreaterEqual(len(topic["facts"]), 6)
            for fact in topic["facts"]:
                self.assertTrue(fact["en"] and fact["hi"])

    def test_offline_script_structure(self):
        research = {
            "topic_id": "unit", "title": {"en": "Test Story", "hi": "परीक्षण कहानी"},
            "title_en": "Test Story", "category": "world_history",
            "facts": SEED_TOPICS[0]["facts"][:3], "tags": ["test"],
        }
        for lang in ("hi", "en"):
            scenes = _template_scenes(
                lang, research, {"hook": ["Imagine."], "transition": ["Next."], "outro": ["The end."]},
                {"chapter": "Chapter"}, test_mode=True,
            )
            self.assertGreater(len(scenes), 5)
            self.assertEqual(scenes[0]["type"], "hook")
            self.assertEqual(scenes[-1]["type"], "outro")
            self.assertTrue(all(s["text"].strip() for s in scenes))
            self.assertGreater(_duration_for("word " * 400), 60)


class ControlTests(unittest.TestCase):
    def test_master_and_upload_switches(self):
        from common.control import (
            automation_enabled, set_automation_enabled,
            set_upload_enabled, upload_override,
        )
        set_automation_enabled(False)
        self.assertFalse(automation_enabled())
        set_automation_enabled(True)
        self.assertTrue(automation_enabled())
        set_upload_enabled(True)
        self.assertTrue(upload_override())
        set_upload_enabled(False)
        self.assertFalse(upload_override())


class SkillTests(unittest.TestCase):
    def test_vendored_skills_available(self):
        from skills import youtube_agent
        info = youtube_agent.available()
        self.assertEqual(len(info["skills"]), 11)
        self.assertTrue(info["tools_ready"], info["tools"])

    def test_hook_and_title_tools(self):
        from skills import youtube_agent
        hook = youtube_agent.score_hook("2,600 years ago a stone changed everything")
        self.assertIsInstance(hook, list)
        self.assertIn("verdict", hook[0])
        title = youtube_agent.lint_title("The Great Pyramid: Built for Eternity", "GREAT PYRAMID")
        self.assertIn("score", title[0])

    def test_resource_estimate(self):
        from skills.resource import estimate
        result = estimate({"title": "Unit", "language": "en",
                           "scenes": [{"text": "word " * 100}]})
        self.assertEqual(result["scene_count"], 1)
        self.assertGreater(result["word_count"], 0)
        self.assertGreater(result["spoken_minutes"], 0)

    def test_skill_report_parse(self):
        from local_agent.skill_installer import parse_report
        with TemporaryDirectory() as d:
            p = Path(d) / "report.md"
            p.write_text("# Report\n- pip: Pillow\n- asset: ancient rome\n")
            report = parse_report(p)
            self.assertIn("Pillow", report["pip"])
            self.assertIn("ancient rome", report["assets"])


class FallbackTests(unittest.TestCase):
    def test_local_save_without_files_does_not_crash(self):
        """Regression: read_json(None) used to raise TypeError when files were absent."""
        import local_agent.fallback as fallback
        with TemporaryDirectory() as d:
            original = fallback.ARCHIVE_ROOT
            fallback.ARCHIVE_ROOT = Path(d)
            try:
                result = fallback.local_save("missing_video_xyz", "unit test")
                self.assertFalse(result["youtube_uploaded"])
                self.assertTrue((Path(d) / "missing_video_xyz" / "REPORT.txt").exists())
            finally:
                fallback.ARCHIVE_ROOT = original

    def test_ensure_delivered(self):
        import local_agent.fallback as fallback
        with TemporaryDirectory() as d:
            original = fallback.ARCHIVE_ROOT
            fallback.ARCHIVE_ROOT = Path(d)
            try:
                up = fallback.ensure_delivered({"youtube_id": "abc123"}, "v1")
                self.assertTrue(up["youtube_uploaded"])
                self.assertEqual(up["youtube_id"], "abc123")
                local = fallback.ensure_delivered(None, "v2")
                self.assertIn("archive", local)
            finally:
                fallback.ARCHIVE_ROOT = original


class VaultTests(unittest.TestCase):
    def test_secret_scanner_blocks_credentials(self):
        from local_agent.vault import assert_no_secrets, SecretLeakError
        with self.assertRaises(SecretLeakError):
            assert_no_secrets({"client_secret": "value"})
        with self.assertRaises(SecretLeakError):
            assert_no_secrets({"note": "gho_" + "a" * 30})
        assert_no_secrets({"type": "status_request", "node": "local"})

    def test_bootstrap_essentials(self):
        from local_agent.bootstrap import check
        state = check()
        self.assertIn("essential_missing", state)
        self.assertIn("optional_missing", state)
        self.assertEqual(state["essential_missing"], [])


class LayoutTests(unittest.TestCase):
    def test_structure_exists(self):
        for path in ["main.py", "requirements.txt", "Dockerfile", ".env.example",
                     "config/settings.json", ".github/workflows/main.yml",
                     ".github/workflows/research.yml", ".github/workflows/video-production.yml",
                     ".github/workflows/upload.yml", ".github/workflows/analytics.yml",
                     ".github/workflows/sync.yml", "LOCAL_SETUP.md", "config/local.json",
                     "local_agent/agent.py", "local_agent/vault.py", "local_agent/fallback.py",
                     "skills/youtube_agent.py", "skills/resource.py", "skills/seo_skill.py",
                     "vendor/youtube-agent-skill/LICENSE", ".githooks/pre-commit",
                     "OPTIONAL_TOOLS.md", "scripts/fetch_vendors.sh",
                     "dashboard/studio.html", "dashboard/static/three/three.module.js",
                     "dashboard/static/three/three.core.js",
                     "skills/tool_registry.py"]:
            self.assertTrue((ROOT / path).exists(), path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
