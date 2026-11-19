"""Local visual/thumbnail asset library with free Wikimedia Commons sourcing."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import requests

from common.logging_setup import get_logger
from common.paths import ROOT
from common.utils import read_json, run_command, write_json

log = get_logger("asset_library")
LOCAL_CFG = read_json(ROOT / "config" / "local.json", {}) or {}
ASSET_CFG = LOCAL_CFG.get("assets", {})
ASSETS = ROOT / str(ASSET_CFG.get("dir", "local_agent/assets"))
VISUALS = ASSETS / str(ASSET_CFG.get("visuals", "visuals"))
THUMBS = ASSETS / str(ASSET_CFG.get("thumbnails", "thumbnails"))
BACKGROUNDS = ASSETS / str(ASSET_CFG.get("backgrounds", "backgrounds"))
MUSIC = ASSETS / str(ASSET_CFG.get("music", "music"))
API = str(ASSET_CFG.get("wikimedia_api", "https://commons.wikimedia.org/w/api.php"))
UA = "AI-Documentary-Factory/1.0 (local asset collector; educational use)"


def ensure_dirs() -> None:
    for d in (ASSETS, VISUALS, THUMBS, BACKGROUNDS, MUSIC):
        d.mkdir(parents=True, exist_ok=True)


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def search_commons(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Search Wikimedia Commons for freely licensed historical images."""
    params = {
        "action": "query", "format": "json",
        "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6, "gsrlimit": min(limit, 20),
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1920,
    }
    response = requests.get(API, params=params, headers={"User-Agent": UA}, timeout=45)
    response.raise_for_status()
    pages = (response.json().get("query") or {}).get("pages") or {}
    results = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        results.append({
            "title": page.get("title", ""),
            "url": info.get("url", ""),
            "thumb_url": info.get("thumburl", info.get("url", "")),
            "license": meta.get("LicenseShortName", {}).get("value", "unknown"),
            "artist": _strip_html(meta.get("Artist", {}).get("value", "")),
            "description_url": info.get("descriptionurl", ""),
        })
    return results


def fetch(query: str, limit: int = 8) -> dict[str, Any]:
    """Download images + attribution into the local library."""
    ensure_dirs()
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:40] or "assets"
    folder = VISUALS / slug
    folder.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    try:
        items = search_commons(query, limit)
    except Exception as exc:  # noqa: BLE001
        log.warning("Commons search failed (%s); generating local plates instead", exc)
        items = []

    for i, item in enumerate(items):
        if not item["thumb_url"]:
            continue
        path = folder / f"asset_{i:03d}.jpg"
        try:
            img = requests.get(item["thumb_url"], headers={"User-Agent": UA}, timeout=90)
            img.raise_for_status()
            # Normalise to 1920x1080 so the visual engine can use it directly.
            tmp = folder / f"asset_{i:03d}.raw"
            tmp.write_bytes(img.content)
            run_command([
                "ffmpeg", "-y", "-v", "error", "-i", str(tmp),
                "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p",
                "-frames:v", "1", "-q:v", "2", str(path),
            ])
            tmp.unlink(missing_ok=True)
            records.append({**item, "path": str(path)})
        except Exception as exc:  # noqa: BLE001
            log.warning("Image download failed for %s: %s", item["title"], exc)

    if not records:
        from visual_engine.engine import VisualEngine
        plate = folder / "asset_000.jpg"
        VisualEngine()._make_plate(plate, query.title(), "Local Library", 1)
        records.append({"title": "Generated plate", "path": str(plate),
                        "license": "generated", "artist": "local"})

    attribution = {"query": query, "items": records}
    write_json(folder / "attribution.json", attribution)
    log.info("Asset library: %d images for '%s' -> %s", len(records), query, folder)
    return attribution


def report() -> dict[str, Any]:
    ensure_dirs()
    return {
        "root": str(ASSETS),
        "visuals": len(list(VISUALS.rglob("*.jpg"))),
        "thumbnails": len(list(THUMBS.glob("*.jpg"))),
        "backgrounds": len(list(BACKGROUNDS.glob("*.jpg"))),
        "music": len(list(MUSIC.glob("*.mp3"))),
        "attribution_files": len(list(VISUALS.rglob("attribution.json"))),
    }
