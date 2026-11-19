"""Deep research stage: expand a seed topic into bilingual documentary facts."""
from __future__ import annotations

import json
from typing import Any

from common.ai_client import AIClient
from common.config import load_settings
from common.logging_setup import get_logger
from common.utils import iso_now, write_json
from database.manager import Database
from research.knowledge_base import get_topic

log = get_logger("research_engine")

SYSTEM = (
    "You are a meticulous documentary researcher. Return only factual, "
    "well-sourced, concise statements. Never invent dates or events. "
    "Always answer with a JSON object containing a key 'facts' which is a "
    "list of objects with 'en' and 'hi' string keys."
)


class ResearchEngine:
    def __init__(self, db: Database | None = None, ai: AIClient | None = None) -> None:
        self.db = db or Database()
        self.ai = ai or AIClient()
        self.settings = load_settings().get("research", {})

    def research(self, topic: dict[str, Any]) -> dict[str, Any]:
        """Return a research payload with bilingual facts and metadata."""
        seed = get_topic(topic["id"]) or topic
        facts = list(seed.get("facts", []))

        if self.ai.available and self.settings.get("use_ai_when_available", True):
            prompt = (
                f"Topic: {topic['title']['en']}\nCategory: {topic['category']}\n"
                f"Produce {self.settings.get('facts_per_topic', 8)} distinct, "
                "chronologically meaningful facts for a 20-25 minute documentary "
                "in both English and natural Hindi. Include dates where reliable.\n"
                "Seed facts to build on:\n"
                + "\n".join(f"- {f['en']}" for f in facts[:6])
            )
            try:
                result = self.ai.chat_json(SYSTEM, prompt, max_tokens=4000)
                ai_facts = result.get("facts") or []
                cleaned = [
                    {"en": str(f.get("en", "")).strip(), "hi": str(f.get("hi", "")).strip()}
                    for f in ai_facts
                    if isinstance(f, dict) and f.get("en") and f.get("hi")
                ]
                if cleaned:
                    facts = cleaned[: self.settings.get("facts_per_topic", 12)]
                    log.info("AI expanded research to %d facts", len(facts))
            except Exception as exc:  # noqa: BLE001
                log.warning("Research AI failed (%s); using curated facts", exc)

        payload = {
            "topic_id": topic["id"],
            "category": topic["category"],
            "title": topic["title"],
            "tags": topic.get("tags", []),
            "facts": facts,
            "sources_mode": "ai+curated" if self.ai.available else "curated-offline",
            "researched_at": iso_now(),
        }
        self.db.insert("research", topic_id=topic["id"],
                       payload=json.dumps(payload, ensure_ascii=False), created_at=iso_now())

        from common.paths import data_path
        out = data_path("research", f"{topic['id']}.json")
        write_json(out, payload)
        log.info("Research saved: %s (%d facts)", out, len(facts))
        return payload
