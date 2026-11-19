"""Send stage-completion and failure notifications (webhook disabled by default)."""
from __future__ import annotations

import os

import requests

from common.config import load_settings
from common.logging_setup import get_logger

log = get_logger("notifications")


class Notifier:
    def __init__(self) -> None:
        cfg = load_settings().get("notifications", {})
        self.console = bool(cfg.get("console", True))
        self.webhook = os.environ.get("NOTIFY_WEBHOOK_URL", "") or str(cfg.get("webhook_url", ""))

    def send(self, title: str, message: str, level: str = "info") -> None:
        if self.console:
            log.info("[%s] %s — %s", level.upper(), title, message)
        if not self.webhook:
            return
        try:
            requests.post(self.webhook, json={
                "title": title, "message": message, "level": level,
            }, timeout=15).raise_for_status()
        except Exception as exc:  # noqa: BLE001
            log.warning("Webhook notification failed: %s", exc)
