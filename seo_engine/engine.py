"""Build a complete YouTube metadata package for each rendered video."""
from __future__ import annotations

import re
from typing import Any

from common.ai_client import AIClient
from common.config import load_channel, load_settings
from common.logging_setup import get_logger
from common.paths import data_path, ensure_dir
from common.utils import iso_now, write_json
from database.manager import Database

log = get_logger("seo_engine")


def timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class SEOEngine:
    def __init__(self, ai: AIClient | None = None, db: Database | None = None) -> None:
        self.ai = ai or AIClient()
        self.db = db or Database()
        self.channel = load_channel()
        self.upload_defaults = self.channel.get("upload_defaults", {})

    def generate(self, script: dict[str, Any], render: dict[str, Any]) -> dict[str, Any]:
        raw_title = script["title"]
        suffix = str(self.upload_defaults.get("title_suffix", ""))
        title = (raw_title + suffix)[:100]

        tags = list(dict.fromkeys(
            self.channel.get("default_tags", [])
            + script.get("tags", [])
            + [script.get("category", "history").replace("_", " ")]
        ))[:18]

        hashtags = ["#" + re.sub(r"[^a-z0-9]", "", t.lower()) for t in tags[:6]]
        hashtags = [h for h in hashtags if len(h) > 1]

        chapters = [
            {"time": timestamp(c["start"]), "seconds": c["start"], "title": c["title"]}
            for c in script.get("chapters", [])
        ]
        chapter_block = "\n".join(f"{c['time']} {c['title']}" for c in chapters)

        description = (
            f"{raw_title}\n\n"
            f"Explore {raw_title} in this cinematic documentary, narrated in "
            f"{'Hindi' if script['language'] == 'hi' else 'English'}. "
            f"Researched with care and built for curious minds.\n\n"
            f"{'⏱ CHAPTERS' if script['language'] == 'hi' else 'CHAPTERS'}\n"
            f"{chapter_block or '00:00 Introduction'}\n\n"
            f"{' '.join(hashtags)}\n\n"
            f"{self.upload_defaults.get('description_footer', '')}"
        ).strip()

        if self.ai.available:
            try:
                improved = self.ai.safe_chat(
                    "You are a YouTube SEO expert. Return plain text only.",
                    f"Rewrite this YouTube title to be compelling but under 100 chars "
                    f"and clickable without clickbait: {raw_title}",
                    title,
                    max_tokens=120,
                )
                if 10 < len(improved) <= 100 and "\n" not in improved:
                    title = improved + (suffix if suffix not in improved else "")
                    title = title[:100]
            except Exception as exc:  # noqa: BLE001
                log.warning("SEO AI skipped: %s", exc)

        seo = {
            "topic_id": script["topic_id"],
            "language": script["language"],
            "video_id": f"{script['topic_id']}_{script['language']}",
            "title": title,
            "description": description,
            "tags": tags,
            "hashtags": hashtags,
            "chapters": chapters,
            "category_id": self.channel.get("default_category_id", "27"),
            "privacy": str(load_settings().get("upload", {}).get("privacy", "private")),
            "thumbnail": None,
            "duration": render.get("duration", 0),
            "generated_at": iso_now(),
        }

        out_dir = ensure_dir(data_path("seo", f"{script['topic_id']}_{script['language']}"))
        write_json(out_dir / "seo.json", seo)
        (out_dir / "description.txt").write_text(description, encoding="utf-8")
        self.db.insert("videos", id=seo["video_id"], topic_id=script["topic_id"],
                       language=script["language"], title=title,
                       video_path=render["video_path"], duration=render["duration"],
                       status="rendered", created_at=seo["generated_at"])
        log.info("SEO package ready: %s", out_dir)
        return seo
