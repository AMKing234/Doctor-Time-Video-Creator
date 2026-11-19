"""Generate 20–25 minute Hindi + English scripts from research payloads.

Every scene carries an emotion tag consumed by the voice engine, and chapter
markers consumed by the SEO engine. Offline mode uses structured narrative
templates; AI mode asks the configured model for polished prose.
"""
from __future__ import annotations

from typing import Any

from common.ai_client import AIClient
from common.config import load_channel, load_languages, load_settings
from common.logging_setup import get_logger
from common.utils import iso_now, slugify, write_json
from database.manager import Database
from common.paths import data_path

log = get_logger("script_engine")

SYSTEM = (
    "You are an award-winning documentary writer. Write vivid, accurate, "
    "spoken-word narration with natural rhythm. Return a JSON object with a "
    "key 'scenes' — a list of objects with 'type' (hook|context|fact|climax|"
    "reflection|outro), 'text' (narration only, no markdown) and 'chapter' "
    "(integer). Do not include timestamps."
)


def _template_scenes(lang: str, research: dict[str, Any], phrases: dict[str, Any],
                     labels: dict[str, str], test_mode: bool) -> list[dict[str, Any]]:
    """Build a complete narration offline from curated facts."""
    facts = research.get("facts", [])
    title = research["title"][lang]
    hook = phrases.get("hook", [""])[0]
    transitions = phrases.get("transition", [""])
    outro_lines = phrases.get("outro", [""])

    scenes: list[dict[str, Any]] = []

    def add(kind: str, text: str, chapter: int) -> None:
        scenes.append({
            "index": len(scenes),
            "type": kind,
            "text": " ".join(text.split()),
            "chapter": chapter,
        })

    if lang == "hi":
        add("hook",
            f"{hook} आज हम {title} की कहानी कह रहे हैं। "
            "ये कोई सूखी तारीख़ों की सूची नहीं — ये इंसानों की सोच, संघर्ष और जिज्ञासा की यात्रा है। "
            "इसे सुनते समय सोचिए कि इन घटनाओं ने आज की दुनिया को कैसे आकार दिया।", 1)
    else:
        add("hook",
            f"{hook} Today we tell the story of {title}. "
            "This is not a dry list of dates — it is a journey of human thought, "
            "struggle and curiosity. As you listen, consider how these events "
            "shaped the world you live in.", 1)

    fact_slice = facts[:3] if test_mode else facts
    for i, fact in enumerate(fact_slice):
        text = fact.get(lang, "")
        chapter = i + 2
        if not text:
            continue
        if lang == "hi":
            add("context",
                f"{transitions[i % len(transitions)]} हर युग की सबसे बड़ी ताक़त वे विचार हैं जो "
                "लोगों के बीच फैलते हैं। इस कहानी के इस हिस्से में हम उस बदलाव के करने वालों को "
                "पास से देखेंगे।", chapter)
            add("fact", f"{text} ये विवरण सिर्फ़ एक तथ्य नहीं, बल्कि एक मोड़ था जिसने "
                "आने वाली पीढ़ियों के लिए रास्ता खोल दिया।", chapter)
            add("climax" if i == len(fact_slice) - 1 else "reflection",
                f"सोचिए कि उस समय के लोगों के पास आज जैसी सुविधाएँ नहीं थीं। फिर भी उन्होंने "
                "कल्पना की, जोखिम उठाया और नया रास्ता बनाया। {text} इसी साहस की एक और परत है।",
                chapter)
        else:
            add("context",
                f"{transitions[i % len(transitions)]} The greatest force in any age is "
                "the spread of ideas among ordinary people. In this part of the story "
                "we look closely at the people who made that change possible.", chapter)
            add("fact", f"{text} This was more than a detail — it was a turning point "
                "that opened a path for generations to come.", chapter)
            add("climax" if i == len(fact_slice) - 1 else "reflection",
                f"Consider this: those people had none of the conveniences we take for "
                "granted. Yet they imagined, they took risks, and they built something new. "
                f"{text} is another layer of that courage.", chapter)

    if lang == "hi":
        add("outro",
            f"{outro_lines[0]} {title} हमें सिखाता है कि इतिहास कोई बंद किताब नहीं — "
            "ये एक जारी सवाल है। अगर ये कहानी आपको पसंद आई तो चैनल को सदस्यता दें और "
            "अगली कहानी तक जिज्ञासु बने रहें।", 999)
    else:
        add("outro",
            f"{outro_lines[0]} {title} teaches us that history is not a closed book — "
            "it is an open question. If you enjoyed this story, subscribe to the channel "
            "and stay curious until the next one.", 999)

    return scenes


def _duration_for(text: str, minimum: float = 6.0) -> float:
    """Approximate narration time at ~155 words/minute, with a floor."""
    words = max(1, len(text.split()))
    return round(max(minimum, words / 2.6), 1)


class ScriptEngine:
    def __init__(self, db: Database | None = None, ai: AIClient | None = None) -> None:
        self.db = db or Database()
        self.ai = ai or AIClient()
        self.langs = load_languages()
        self.channel = load_channel()
        self.settings = load_settings()

    def generate(self, research: dict[str, Any], language: str,
                 test_mode: bool = False) -> dict[str, Any]:
        lang_cfg = self.langs.get(language, self.langs.get("en", {}))
        phrases = lang_cfg.get("phrases", {})
        labels = lang_cfg.get("labels", {})
        emotion_map = lang_cfg.get("emotion_map", {})

        scenes = _template_scenes(language, research, phrases, labels, test_mode)

        if self.ai.available and not test_mode:
            prompt = (
                f"Write a {self.settings.get('video', {}).get('target_duration_minutes', 22)} "
                f"minute {'Hindi' if language == 'hi' else 'English'} documentary narration "
                f"about: {research['title']['en']}\n\nFacts:\n"
                + "\n".join(f"- {f[language]}" for f in research.get("facts", []))
                + "\n\nUse the scene structure from the system prompt. Cover every fact, "
                  "add vivid context and a strong closing. Output only JSON."
            )
            try:
                result = self.ai.chat_json(SYSTEM, prompt, max_tokens=8000, temperature=0.8)
                ai_scenes = result.get("scenes") or []
                cleaned = [
                    {"index": i, "type": str(s.get("type", "fact")),
                     "text": " ".join(str(s.get("text", "")).split()),
                     "chapter": int(s.get("chapter", i // 4 + 1))}
                    for i, s in enumerate(ai_scenes)
                    if isinstance(s, dict) and s.get("text")
                ]
                if len(cleaned) >= len(scenes):
                    scenes = cleaned
                    log.info("AI wrote %d narration scenes (%s)", len(scenes), language)
            except Exception as exc:  # noqa: BLE001
                log.warning("Script AI failed (%s); using templates", exc)

        # Attach emotion + duration, then build chapter timestamps.
        elapsed = 0.0
        chapters: list[dict[str, Any]] = []
        seen_chapters: set[int] = set()
        for scene in scenes:
            scene["emotion"] = emotion_map.get(scene["type"], "neutral")
            scene["duration"] = _duration_for(scene["text"])
            scene["start"] = round(elapsed, 1)
            elapsed += scene["duration"]
            scene["end"] = round(elapsed, 1)
            ch = scene["chapter"]
            if ch not in seen_chapters:
                seen_chapters.add(ch)
                chapters.append({
                    "number": ch,
                    "start": round(scene["start"], 1),
                    "title": f"{labels.get('chapter', 'Chapter')} {ch}",
                })

        script = {
            "topic_id": research["topic_id"],
            "language": language,
            "title": research["title"][language],
            "title_en": research["title"]["en"],
            "category": research["category"],
            "tags": research.get("tags", []),
            "estimated_duration": round(elapsed, 1),
            "scene_count": len(scenes),
            "scenes": scenes,
            "chapters": chapters,
            "generated_at": iso_now(),
            "mode": "ai" if self.ai.available else "offline",
        }

        filename = f"{slugify(research['title']['en'])}_{language}.json"
        out = data_path("scripts", filename)
        write_json(out, script)
        self.db.insert("scripts", topic_id=research["topic_id"], language=language,
                       path=str(out), scene_count=len(scenes), created_at=iso_now())
        log.info("Script ready: %s | %d scenes | %.1f min | %s",
                 language, len(scenes), elapsed / 60, out)
        return script
