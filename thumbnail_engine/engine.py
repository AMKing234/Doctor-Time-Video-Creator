"""Generate a high-contrast 1280x720 YouTube thumbnail from a generated visual."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.config import load_channel, load_settings
from common.logging_setup import get_logger
from common.paths import data_path, ensure_dir
from common.utils import run_command
from visual_engine.engine import escape_drawtext, find_font


class ThumbnailEngine:
    def __init__(self) -> None:
        self.branding = load_channel().get("branding", {})
        self.accent = str(self.branding.get("accent_color", "#D4AF37")).lstrip("#")
        self.font = find_font()

    def generate(self, script: dict[str, Any], visual_manifest: dict[str, Any]) -> dict[str, Any]:
        out_dir = ensure_dir(data_path("thumbnails", f"{script['topic_id']}_{script['language']}"))
        out = out_dir / "thumbnail.jpg"
        first = visual_manifest["visuals"][0]["path"]
        title = script.get("title_en", script.get("title", "DOCUMENTARY"))
        words = title.split()
        line1 = " ".join(words[: max(2, len(words) // 2)])
        line2 = " ".join(words[max(2, len(words) // 2):]) or words[-1]

        filters = [
            "scale=1280:720:force_original_aspect_ratio=increase",
            "crop=1280:720",
            "eq=contrast=1.18:saturation=1.15:brightness=-0.05",
            "vignette=PI/4",
            f"drawbox=x=0:y=0:w=1280:h=10:color=0x{self.accent}:t=fill",
            f"drawbox=x=0:y=710:w=1280:h=10:color=0x{self.accent}:t=fill",
        ]
        if self.font:
            font = self.font.replace(":", "\\:")
            filters += [
                f"drawtext=fontfile='{font}':text='{escape_drawtext(line1.upper())}':"
                f"fontsize=74:fontcolor=white:box=1:boxcolor=black@0.72:boxborderw=24:"
                f"x=(w-tw)/2:y=h*0.30",
                f"drawtext=fontfile='{font}':text='{escape_drawtext(line2.upper())}':"
                f"fontsize=74:fontcolor=0x{self.accent}:box=1:boxcolor=black@0.72:boxborderw=24:"
                f"x=(w-tw)/2:y=h*0.52",
                f"drawtext=fontfile='{font}':text='{escape_drawtext(self.branding.get('logo_text', 'CHRONICLE'))}':"
                f"fontsize=28:fontcolor=white@0.85:x=40:y=640",
                f"drawtext=fontfile='{font}':text='DOCUMENTARY':fontsize=28:"
                f"fontcolor=0x{self.accent}:x=w-tw-40:y=640",
            ]

        run_command([
            "ffmpeg", "-y", "-v", "error", "-i", first,
            "-vf", ",".join(filters), "-frames:v", "1", "-q:v", "2", str(out),
        ])
        log = get_logger("thumbnail_engine")
        log.info("Thumbnail created: %s", out)
        return {
            "topic_id": script["topic_id"],
            "language": script["language"],
            "path": str(out),
            "title_line_1": line1,
            "title_line_2": line2,
        }
