#!/usr/bin/env python3
"""Direct documentary maker: topic + timeline + minutes -> finished local MP4.

No scheduler, no cloud sync, no YouTube upload. Everything is produced on this
device and archived with a REPORT.txt.

Examples
--------
python3 make_video.py --topic "All Roads Lead to Rome" \
    --timeline "Route building|Trade networks|Imperial roads|Legacy" --minutes 8

python3 make_video.py --topic "The Silk Road" --timeline-file timeline.txt --minutes 22
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Callable

from common.logging_setup import get_logger
from common.utils import setup_runtime, slugify

log = get_logger("make_video")

# Category hints used to pick a visual palette when the caller does not specify one.
_CATEGORY_HINTS = {
    "ancient": ("rome", "egypt", "greece", "mesopotamia", "indus", "pharaoh", "pyramid", "athens"),
    "medieval": ("medieval", "crusade", "castle", "knight", "mughal", "ottoman"),
    "islamic_history": ("islam", "quran", "prophet", "caliph", "hadith", "muslim"),
    "modern": ("world war", "industrial", "revolution", "冷战", "modern", "technology"),
    "stone_age": ("stone age", "cave", "hunter", "neanderthal", "ice age"),
}


def _category(topic: str, timeline: str) -> str:
    text = (topic + " " + timeline).lower()
    for cat, hints in _CATEGORY_HINTS.items():
        if any(h in text for h in hints):
            return cat
    return "world_history"


def _timeline_facts(timeline: str) -> list[dict[str, str]]:
    """Turn each timeline line into a bilingual research fact.

    The user may write the timeline in Hindi, English, or both. offline mode
    keeps the supplied text verbatim in both slots so nothing is lost.
    """
    facts: list[dict[str, str]] = []
    for raw in timeline.splitlines():
        line = raw.strip().lstrip("-*•").strip()
        # Strip leading "1." / "1)" numbering.
        for sep in (".", ")"):
            if len(line) > 2 and line[0].isdigit() and sep in line[:4]:
                line = line.split(sep, 1)[1].strip()
        if "|||" in line:
            en, hi = (part.strip() for part in line.split("|||", 1))
            if en or hi:
                facts.append({"en": en or hi, "hi": hi or en})
        elif len(line) >= 3:
            facts.append({"en": line, "hi": line})
    return facts


def _scale_facts(facts: list[dict[str, str]], minutes: float,
                 test_mode: bool) -> list[dict[str, str]]:
    """Expand the caller's timeline to roughly fill the requested minutes.

    ~55 seconds of narration per fact in offline template mode. Extra passes
    repeat the supplied beats with chapter labels; they never invent new
    historical claims, they only re-tell the beats the caller approved.
    """
    if not facts:
        facts = [{"en": "The story begins with a single decisive moment.",
                  "hi": "कहानी एक निर्णायक पल से शुरू होती है।"}]
    if test_mode:
        return facts[:3]
    needed = math.ceil(minutes * 60 / 55)
    # Within ~15% of the target beat count is close enough; expanding further
    # would only pad the documentary with repeated lines.
    if len(facts) >= needed * 0.85:
        return facts
    expanded = list(facts)
    passes = 0
    while len(expanded) < needed:
        passes += 1
        for i, fact in enumerate(facts):
            if len(expanded) >= needed:
                break
            expanded.append({
                "en": f"Part {passes + 1} — {fact['en']}",
                "hi": f"भाग {passes + 1} — {fact['hi']}",
            })
    return expanded


def make_video(topic: str, timeline: str, minutes: float,
               languages: list[str] | None = None,
               test_mode: bool = False,
               progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Produce the requested video(s) fully locally and archive them."""
    from common.paths import data_path
    from common.utils import iso_now, write_json
    from main import Pipeline

    def say(msg: str) -> None:
        log.info(msg)
        if progress:
            progress(msg)

    topic = topic.strip()
    if not topic:
        raise ValueError("topic must not be empty")
    minutes = max(0.2, float(minutes))
    langs = languages or ["hi", "en"]
    topic_id = slugify(topic)[:70]

    facts = _scale_facts(_timeline_facts(timeline), minutes, test_mode)
    payload = {
        "topic_id": topic_id,
        "category": _category(topic, timeline),
        "title": {"en": topic, "hi": topic},
        "tags": [topic_id.replace("_", " ")],
        "facts": facts,
        "sources_mode": "caller-timeline",
        "requested_minutes": minutes,
        "researched_at": iso_now(),
    }
    write_json(data_path("research", f"{topic_id}.json"), payload)

    pipe = Pipeline(test_mode=test_mode)
    pipe.db.insert("research", topic_id=topic_id, payload=str(payload), created_at=iso_now())

    say(f"Research ready: {len(facts)} timeline beats ({topic_id})")
    scripts = [pipe.script(payload, languages=[lang], test_mode=test_mode)[0] for lang in langs]
    for s in scripts:
        say(f"Script ready: {s['language']} — {s['estimated_duration']/60:.1f} min, "
            f"{s['scene_count']} scenes")

    say("Generating voices (King Voice → edge-tts → synthetic fallback)…")
    pipe.voice()
    say("Generating visuals (Wikimedia → FFmpeg cinematic plates)…")
    pipe.visual()
    say("Rendering Full HD video with subtitles…")
    renders = pipe.video()
    say("Building SEO package + thumbnail…")
    pipe.seo()
    say("Running all integrated skills and archiving locally…")
    pipe.skills_stage()

    result = {
        "topic": topic,
        "timeline_beats": len(facts),
        "requested_minutes": minutes,
        "videos": [r["video_path"] for r in renders],
        "scripts": [{"language": s["language"],
                     "minutes": round(s["estimated_duration"] / 60, 1)}
                    for s in scripts],
        "archives": [str(Path(f"local_agent/assets/archive/{topic_id}_{lang}"))
                     for lang in langs],
        "uploaded": False,
        "status": "video ready",
    }
    write_json(data_path("make_video", f"{topic_id}.json"), result)
    say("VIDEO BAN GAYA — local archives + REPORT.txt tayyar hain.")
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Direct local documentary maker")
    p.add_argument("--topic", required=True, help="video ka topic")
    p.add_argument("--timeline", default="", help="'|' se alag kiye gaye timeline points")
    p.add_argument("--timeline-file", help="txt file: ek timeline point per line")
    p.add_argument("--minutes", type=float, default=8.0, help="target duration in minutes")
    p.add_argument("--lang", action="append", choices=["hi", "en"],
                   help="languages (repeatable); default: hi + en")
    p.add_argument("--test", action="store_true", help="short smoke render")
    return p


def main(argv: list[str] | None = None) -> int:
    import json

    setup_runtime()
    args = build_parser().parse_args(argv)
    timeline = args.timeline
    if args.timeline_file:
        timeline = Path(args.timeline_file).read_text(encoding="utf-8")
    try:
        result = make_video(args.topic, timeline, args.minutes,
                            languages=args.lang, test_mode=args.test,
                            progress=lambda m: print(f"[make_video] {m}", flush=True))
        print("\n=== VIDEO BAN GAYA ===")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001
        log.exception("Video production failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
