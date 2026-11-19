"""Calculate the next run and the optimal publish slot."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from common.config import load_settings
from common.paths import data_path
from common.utils import read_json


class Scheduler:
    def __init__(self) -> None:
        cfg = load_settings().get("scheduler", {})
        self.cron = str(cfg.get("cron", "0 3 * * *"))
        self.timezone = str(cfg.get("timezone", "Asia/Kolkata"))
        self.max_per_day = int(cfg.get("max_videos_per_day", 1))

    def next_run(self, now: datetime | None = None) -> datetime:
        now = now or datetime.now()
        parts = self.cron.split()
        if len(parts) != 5:
            return now + timedelta(days=1)
        minute, hour, dom, month, dow = parts
        try:
            if hour.isdigit() and minute.isdigit():
                target = now.replace(hour=int(hour), minute=int(minute),
                                     second=0, microsecond=0)
                return target if target > now else target + timedelta(days=1)
        except ValueError:
            pass
        return now + timedelta(days=1)

    def optimal_publish_at(self) -> str | None:
        rec = read_json(data_path("analytics", "optimal_schedule.json"), {}) or {}
        if not rec.get("publish_at"):
            return None
        return f"{rec['publish_at']} ({rec.get('timezone', self.timezone)})"

    def plan(self) -> dict[str, Any]:
        return {
            "cron": self.cron,
            "timezone": self.timezone,
            "next_run": self.next_run().isoformat(timespec="minutes"),
            "max_videos_per_day": self.max_per_day,
            "optimal_publish_slot": self.optimal_publish_at(),
        }
