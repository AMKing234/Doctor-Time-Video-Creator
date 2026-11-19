"""OpenAI-compatible AI client with graceful offline fallback.

When no AI_API_KEY is configured the system still runs end-to-end using the
built-in knowledge base and deterministic script generators (demo mode)."""
from __future__ import annotations

import json
from typing import Any

import requests

from common.config import load_settings
from common.logging_setup import get_logger
from common.utils import retry

log = get_logger("ai_client")


class AIUnavailable(RuntimeError):
    pass


class AIClient:
    def __init__(self) -> None:
        cfg = load_settings().get("ai", {})
        self.api_key = str(cfg.get("api_key") or "").strip()
        self.api_base = str(cfg.get("api_base") or "https://api.openai.com/v1").rstrip("/")
        self.model = str(cfg.get("model") or "gpt-4o-mini")
        self.timeout = int(cfg.get("timeout", 120))

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @retry(attempts=3, delay=2.0, exceptions=(requests.RequestException, ValueError))
    def chat(self, system: str, prompt: str, *, json_mode: bool = False,
             temperature: float = 0.7, max_tokens: int = 3000) -> str:
        if not self.available:
            raise AIUnavailable("AI_API_KEY is not configured; use offline generators.")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = requests.post(
            f"{self.api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def chat_json(self, system: str, prompt: str, **kwargs: Any) -> dict[str, Any]:
        raw = self.chat(system, prompt, json_mode=True, **kwargs)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Some providers ignore response_format; strip code fences.
            cleaned = raw.strip().strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            return json.loads(cleaned)

    def safe_chat(self, system: str, prompt: str, fallback: str, **kwargs: Any) -> str:
        """Use AI when configured, otherwise return the offline fallback."""
        if not self.available:
            log.info("AI offline -> using built-in generator")
            return fallback
        try:
            return self.chat(system, prompt, **kwargs)
        except Exception as exc:  # noqa: BLE001
            log.warning("AI call failed (%s); using offline generator", exc)
            return fallback
