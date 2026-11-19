"""Generate one 1920x1080 visual per narration scene.

Two providers:
  1. IMAGE_API_KEY set -> OpenAI-compatible image generation (cinematic stills).
  2. No key -> deterministic FFmpeg "cinematic plate" with gradient, vignette,
     category label, English title and scene index (no Pillow/GPU required).
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import requests

from common.config import load_channel, load_settings
from common.logging_setup import get_logger
from common.paths import data_path, ensure_dir
from common.utils import iso_now, retry, run_command, write_json

log = get_logger("visual_engine")

FONT_CANDIDATES = [
    "/data/user/0/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def find_font() -> str | None:
    env = os.environ.get("FONT_PATH", "").strip()
    if env and Path(env).exists():
        return env
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def escape_drawtext(text: str) -> str:
    """Escape FFmpeg drawtext special characters."""
    return (
        str(text).replace("\\", "\\\\").replace(":", "\\:")
        .replace("'", "\\'").replace("%", "\\%").replace("\n", " ")
    )


class VisualEngine:
    def __init__(self) -> None:
        cfg = load_settings()
        self.video = cfg.get("video", {})
        self.width = int(self.video.get("width", 1920))
        self.height = int(self.video.get("height", 1080))
        image_cfg = cfg.get("image", {})
        self.api_key = str(image_cfg.get("api_key") or "").strip()
        self.api_base = str(image_cfg.get("api_base") or "https://api.openai.com/v1").rstrip("/")
        self.model = str(image_cfg.get("model") or "gpt-image-1")
        self.font = find_font()
        self.channel = load_channel()
        self.accent = str(self.channel.get("branding", {}).get("accent_color", "#D4AF37")).lstrip("#")

    def _plate_filter(self, title: str, category: str, scene_no: int) -> str:
        w, h = self.width, self.height
        parts = [
            f"gradients=s={w}x{h}:c0=0x0A0E1A:c1=0x18294A:"
            f"x0=0:y0={h}:x1={w}:y1=0:nb_colors=2:d=1",
            f"drawbox=x={w // 18}:y={h // 14}:w={w - 2 * (w // 18)}:h=6:"
            f"color=0x{self.accent}@0.55:t=fill",
            "vignette=PI/4",
        ]
        if self.font:
            font = self.font.replace(":", "\\:")
            parts += [
                f"drawtext=fontfile='{font}':text='{escape_drawtext(category.upper())}':"
                f"fontsize=30:fontcolor=0x{self.accent}:x=90:y=80",
                f"drawtext=fontfile='{font}':text='{escape_drawtext(title)}':"
                f"fontsize=62:fontcolor=white:x=(w-tw)/2:y=h*0.44:"
                f"box=1:boxcolor=black@0.35:boxborderw=20",
                f"drawtext=fontfile='{font}':text='SCENE {scene_no:03d}':"
                f"fontsize=28:fontcolor=white@0.7:x=w-tw-90:y=h-100",
            ]
        parts.append("format=yuv420p")
        return ",".join(parts)

    def _make_plate(self, out: Path, title: str, category: str, scene_no: int) -> Path:
        run_command([
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", self._plate_filter(title, category, scene_no),
            "-frames:v", "1", "-q:v", "2", str(out),
        ])
        return out

    @retry(attempts=3, delay=2.0, exceptions=(requests.RequestException, ValueError, KeyError))
    def _make_ai_image(self, out: Path, prompt: str) -> Path:
        response = requests.post(
            f"{self.api_base}/images/generations",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": self.model,
                "prompt": f"Cinematic historically plausible documentary still, "
                          f"wide 16:9, dramatic golden-hour light, ultra detailed, "
                          f"no text, no watermark: {prompt}",
                "n": 1, "size": "1792x1024", "response_format": "b64_json",
            },
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()["data"][0]
        raw = out.with_suffix(".raw.png")
        if data.get("b64_json"):
            raw.write_bytes(base64.b64decode(data["b64_json"]))
        else:
            img = requests.get(data["url"], timeout=120)
            img.raise_for_status()
            raw.write_bytes(img.content)
        run_command([
            "ffmpeg", "-y", "-v", "error", "-i", str(raw),
            "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                   f"crop={self.width}:{self.height},vignette=PI/5,format=yuv420p",
            "-frames:v", "1", "-q:v", "2", str(out),
        ])
        raw.unlink(missing_ok=True)
        return out

    def generate(self, script: dict[str, Any]) -> dict[str, Any]:
        out_dir = ensure_dir(data_path("visual", f"{script['topic_id']}_{script['language']}"))
        title = script.get("title_en", script.get("title", "Documentary"))
        category = script.get("category", "history").replace("_", " ").title()
        visuals: list[dict[str, Any]] = []
        used_ai = 0

        for scene in script["scenes"]:
            path = out_dir / f"visual_{scene['index']:03d}.jpg"
            prompt = f"{title}. Scene {scene['index'] + 1}: {scene['text'][:240]}"
            provider = "ffmpeg-plate"
            if self.api_key:
                try:
                    self._make_ai_image(path, prompt)
                    provider = "ai"
                    used_ai += 1
                except Exception as exc:  # noqa: BLE001
                    log.warning("Image AI failed on scene %d (%s); using plate", scene["index"], exc)
            if not path.exists():
                self._make_plate(path, title, category, scene["index"] + 1)

            visuals.append({
                "index": scene["index"],
                "path": str(path),
                "provider": provider,
            })

        manifest = {
            "topic_id": script["topic_id"],
            "language": script["language"],
            "width": self.width,
            "height": self.height,
            "font": self.font,
            "ai_scenes": used_ai,
            "visuals": visuals,
            "created_at": iso_now(),
        }
        write_json(out_dir / "visual_manifest.json", manifest)
        log.info("Visuals ready: %d frames (%d AI, %d plates)",
                 len(visuals), used_ai, len(visuals) - used_ai)
        return manifest
