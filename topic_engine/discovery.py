"""Discover, score and select the next documentary topic with no human input."""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from common.config import load_settings
from common.logging_setup import get_logger
from database.manager import Database
from research.knowledge_base import SEED_TOPICS

log = get_logger("topic_engine")


class TopicEngine:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database()
        self.settings = load_settings()
        self.content = self.settings.get("content", {})

    def discover(self) -> list[dict[str, Any]]:
        """Register all seed topics and score them for freshness/interest."""
        discovered: list[dict[str, Any]] = []
        for topic in SEED_TOPICS:
            if topic["category"] not in self.content.get("categories", []):
                continue
            scored = dict(topic)
            scored["score"] = self._score(topic)
            self.db.upsert_topic(scored)
            discovered.append(scored)
        log.info("Discovered %d topics across %d categories",
                 len(discovered), len({t["category"] for t in discovered}))
        return discovered

    def _score(self, topic: dict[str, Any]) -> float:
        """Deterministic interest score; AI can refine this in future versions."""
        base = 0.55
        base += min(len(topic.get("facts", [])) / 100, 0.2)
        base += min(len(topic.get("tags", [])) / 50, 0.1)
        # Slight variance so the engine does not always pick the same topic.
        base += random.uniform(0.0, 0.12)
        return round(min(base, 0.99), 3)

    def select(self, category: str | None = None) -> dict[str, Any] | None:
        """Pick the highest-scoring topic that has not been used recently."""
        candidates = [
            t for t in self.discover()
            if not self.db.is_topic_used(
                t["id"], int(self.content.get("min_freshness_days", 30))
            )
            and (category is None or t["category"] == category)
        ]
        threshold = float(self.content.get("topic_score_threshold", 0.55))
        candidates = [t for t in candidates if t.get("score", 0) >= threshold]
        if not candidates:
            log.warning("No fresh topics left; resetting usage cycle")
            # All topics exhausted -> allow reuse of the oldest one.
            candidates = self.discover()
        if not candidates:
            return None

        chosen = max(candidates, key=lambda t: (t["score"], random.random()))
        log.info("Selected topic: %s (%s)", chosen["id"], chosen["category"])
        return chosen

    def rotate_category(self) -> str:
        """Cycle through configured categories for variety."""
        categories = self.content.get("categories", [])
        if not categories:
            return "world_history"
        used = [r["category"] for r in self.db.records("topics", 200)]
        least_used = min(categories, key=lambda c: used.count(c))
        return least_used
