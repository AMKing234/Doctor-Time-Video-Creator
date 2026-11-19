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

    def test_direct_mode_has_no_upload_config(self):
        self.assertNotIn("upload", load_settings())


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


class DirectMakerTests(unittest.TestCase):
    def test_timeline_parsing(self):
        from make_video import _timeline_facts, _scale_facts, _category
        facts = _timeline_facts("1. Road building\n- Trade networks\n* Imperial postal system\nLegacy")
        self.assertEqual(len(facts), 4)
        self.assertEqual(facts[0]["en"], "Road building")
        self.assertTrue(all(f["hi"] == f["en"] for f in facts))
        self.assertEqual(_category("Rome roads", "roman empire"), "ancient")
        self.assertEqual(len(_scale_facts(facts, 22, False)), 24)
        self.assertEqual(len(_scale_facts(facts, 22, True)), 3)

    def test_dashboard_routes(self):
        from dashboard.app import create_app
        client = create_app().test_client()
        for url in ("/", "/studio", "/static-three/three.module.js",
                    "/api/tools", "/api/stats", "/api/videos", "/api/make/status"):
            self.assertEqual(client.get(url).status_code, 200, url)
        self.assertEqual(client.get("/favicon.ico").status_code, 204)
        self.assertIn("VIDEO BANAO", client.get("/").get_data(as_text=True))
        self.assertEqual(client.post("/api/make", json={}).status_code, 400)


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
                local = fallback.ensure_delivered(None, "v2")
                self.assertFalse(local["youtube_uploaded"])
                self.assertIn("archive", local)
                self.assertTrue((Path(d) / "v2" / "REPORT.txt").exists())
            finally:
                fallback.ARCHIVE_ROOT = original


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_essentials(self):
        from local_agent.bootstrap import check
        state = check()
        self.assertIn("essential_missing", state)
        self.assertIn("optional_missing", state)
        self.assertEqual(state["essential_missing"], [])


class LayoutTests(unittest.TestCase):
    def test_structure_exists(self):
        for path in ["make_video.py", "main.py", "requirements.txt", "Dockerfile", ".env.example",
                     "config/settings.json", "config/local.json", "DIRECT_MODE.md",
                     "local_agent/agent.py", "local_agent/fallback.py",
                     "skills/youtube_agent.py", "skills/resource.py", "skills/seo_skill.py",
                     "vendor/youtube-agent-skill/LICENSE", ".githooks/pre-commit",
                     "OPTIONAL_TOOLS.md", "scripts/fetch_vendors.sh",
                     "dashboard/studio.html", "dashboard/static/three/three.module.js",
                     "dashboard/static/three/three.core.js",
                     "skills/tool_registry.py"]:
            self.assertTrue((ROOT / path).exists(), path)
            self.assertFalse(path.startswith(".github/"), path)

    def test_automation_and_upload_files_removed(self):
        for path in [".github", "scheduler", "youtube_uploader", "analytics_engine",
                     "notifications", "common/control.py", "local_agent/vault.py",
                     "local_agent/sync.py", "local_agent/cloud_worker.py",
                     "local_agent/youtube_setup.py", "LOCAL_SETUP.md"]:
            self.assertFalse((ROOT / path).exists(), path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
