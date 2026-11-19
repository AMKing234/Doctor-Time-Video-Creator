"""Archive every produced video locally with a full REPORT.txt.

Direct local mode: nothing is uploaded, no credential is used. No data is lost.
"""
from __future__ import annotations

import glob
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.logging_setup import get_logger
from common.paths import ROOT, data_path
from common.utils import iso_now, read_json, write_json

log = get_logger("local_fallback")
ARCHIVE_ROOT = ROOT / "local_agent" / "assets" / "archive"


def _first(pattern: str) -> str | None:
    matches = sorted(glob.glob(pattern))
    return matches[0] if matches else None


def _read_first(pattern: str, default: Any = None) -> Any:
    """read_json on the first match of a glob; safe when nothing matched."""
    path = _first(pattern)
    return read_json(path, default) if path else default


def local_save(video_id: str, reason: str = "direct local production") -> dict[str, Any]:
    """Copy all produced assets into a local archive and write REPORT.txt."""
    dest = ARCHIVE_ROOT / video_id
    (dest / "visuals").mkdir(parents=True, exist_ok=True)
    (dest / "audio").mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    def copy(src: str | None, subdir: str = "") -> None:
        if not src or not Path(src).exists():
            return
        target = dest / subdir / Path(src).name
        shutil.copy2(src, target)
        try:
            copied.append(str(target.relative_to(ROOT)))
        except ValueError:
            copied.append(str(target))

    base = f"{video_id}"
    render = _read_first(str(data_path("videos", base, "render_manifest.json")), {}) or {}
    seo = _read_first(str(data_path("seo", base, "seo.json")), {}) or {}
    visual = _read_first(str(data_path("visual", base, "visual_manifest.json")), {}) or {}
    voice = _read_first(str(data_path("voice", base, "voice_manifest.json")), {}) or {}

    copy(render.get("video_path"))
    copy(render.get("subtitle_path"))
    copy(render.get("music_path"))
    copy(_first(str(data_path("thumbnails", base, "thumbnail.jpg"))))
    copy(_first(str(data_path("seo", base, "seo.json"))))
    copy(_first(str(data_path("seo", base, "description.txt"))))
    copy(_first(str(data_path("scripts", "*.json"))))
    copy(voice.get("merged_audio"), "audio")

    for item in visual.get("visuals", []):
        copy(item.get("path"), "visuals")

    chapters = "\n".join(
        f"  {c['time']}  {c['title']}" for c in seo.get("chapters", [])
    ) or "  (none)"

    report_txt = f"""LOCAL DELIVERY REPORT
=====================
Generated: {iso_now()}
Video ID : {video_id}
Reason   : {reason}
Status   : Saved locally — NOT uploaded to YouTube

TITLE
-----
{seo.get('title', 'unknown')}

LANGUAGE / DURATION
-------------------
Language : {seo.get('language', 'unknown')}
Duration : {render.get('duration', 0)} seconds
Resolution: {render.get('resolution', '1920x1080')}

FILES COPIED
------------
{chr(10).join('  - ' + p for p in copied) or '  (none)'}

CHAPTERS
--------
{chapters}

TAGS
----
{', '.join(seo.get('tags', [])) or '(none)'}

HASHTAGS
--------
{' '.join(seo.get('hashtags', [])) or '(none)'}

DESCRIPTION
-----------
{seo.get('description', '(not generated)')}

NOTE
----
This is a direct local production. Nothing was uploaded and no credentials
are used or stored. The full video, audio, visuals, captions, SEO and this
report are saved under local_agent/assets/archive/{video_id}/.
"""
    report_path = dest / "REPORT.txt"
    report_path.write_text(report_txt, encoding="utf-8")
    manifest = {
        "video_id": video_id,
        "reason": reason,
        "saved_at": iso_now(),
        "archive": str(dest),
        "report": str(report_path),
        "files": copied,
        "youtube_uploaded": False,
    }
    write_json(dest / "report.json", manifest)
    log.info("Local fallback saved %d files + report: %s", len(copied), report_path)
    return manifest


def ensure_delivered(upload_result: dict[str, Any] | None = None,
                     video_id: str = "", reason: str = "direct local production") -> dict[str, Any]:
    """Guarantee delivery: archive locally with a REPORT.txt."""
    return local_save(video_id, reason)
