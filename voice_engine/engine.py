"""Narration engine.

Primary path imports the existing King Voice 👑 repository (edge-tts prosody
+ FFmpeg emotion DSP) directly from its engine.py. If that repository is not
available — as in a clean GitHub Actions runner — an equivalent built-in
implementation is used. If edge-tts is unreachable, a synthetic audio bed is
generated so the full pipeline remains testable offline.
"""
from __future__ import annotations

import asyncio
import importlib.util
import math
from pathlib import Path
from types import ModuleType
from typing import Any

from common.config import load_settings
from common.logging_setup import get_logger
from common.paths import ROOT, data_path, ensure_dir
from common.utils import chunk_text, iso_now, probe_duration, run_command, write_json

log = get_logger("voice_engine")

VOICE_MAP = {
    "hindi_male": "hi-IN-MadhurNeural",
    "hindi_female": "hi-IN-SwaraNeural",
    "english_male": "en-IN-PrabhatNeural",
    "english_female": "en-IN-NeerjaNeural",
}

EMOTION_PRESETS: dict[str, dict[str, str]] = {
    "neutral": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%",
                "filter": "loudnorm=I=-16:TP=-1.5:LRA=11"},
    "soft": {"rate": "-8%", "pitch": "-2Hz", "volume": "-4%",
             "filter": "equalizer=f=250:width_type=o:width=1:g=1.5,loudnorm=I=-17:TP=-1.5:LRA=10"},
    "dramatic": {"rate": "+12%", "pitch": "+5Hz", "volume": "+18%",
                 "filter": "acompressor=threshold=-20dB:ratio=5:attack=4:release=40,"
                           "equalizer=f=3000:width_type=o:width=1:g=4,loudnorm=I=-13:TP=-1:LRA=8"},
    "strong": {"rate": "+10%", "pitch": "+4Hz", "volume": "+16%",
               "filter": "acompressor=threshold=-18dB:ratio=4:attack=5:release=50,"
                         "equalizer=f=2800:width_type=o:width=1:g=3.5,loudnorm=I=-14:TP=-1:LRA=9"},
    "reverent": {"rate": "-10%", "pitch": "-2Hz", "volume": "+0%",
                 "filter": "aecho=0.8:0.85:50:0.2,loudnorm=I=-16:TP=-1.5:LRA=10"},
    "whisper": {"rate": "-10%", "pitch": "+3Hz", "volume": "-22%",
                "filter": "highpass=f=250,equalizer=f=4500:width_type=o:width=1:g=4,loudnorm=I=-19:TP=-2:LRA=8"},
}


def _load_kingvoice(path_hint: str) -> ModuleType | None:
    candidates = [Path(path_hint), ROOT.parent / "kingvoice", ROOT / "kingvoice"]
    for base in candidates:
        engine_file = base / "engine.py" if base else None
        if engine_file and engine_file.exists():
            try:
                spec = importlib.util.spec_from_file_location("kingvoice_engine", engine_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    log.info("King Voice 👑 repository integrated: %s", engine_file)
                    return module
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not import King Voice (%s): %s", engine_file, exc)
    return None


async def _synth_edge(text: str, voice: str, emotion: str, out_wav: Path,
                      preset: dict[str, str]) -> None:
    import edge_tts  # imported lazily so offline mode needs no install
    raw = str(out_wav) + ".raw.mp3"
    communicate = edge_tts.Communicate(
        text=text, voice=voice,
        rate=preset["rate"], pitch=preset["pitch"], volume=preset["volume"],
    )
    # Bound the network call so a blocked TTS endpoint cannot stall the pipeline.
    await asyncio.wait_for(communicate.save(raw), timeout=25)
    try:
        run_command([
            "ffmpeg", "-y", "-v", "error", "-i", raw,
            "-af", preset["filter"], "-ar", "44100", "-ac", "1",
            "-c:a", "pcm_s16le", str(out_wav),
        ])
    finally:
        Path(raw).unlink(missing_ok=True)


def _synth_synthetic(text: str, out_wav: Path) -> None:
    """Offline placeholder audio, length matched to the narration."""
    words = max(1, len(text.split()))
    duration = max(2.0, words / 2.6)
    run_command([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
        "-i", f"sine=frequency=110:sample_rate=44100:duration={duration:.2f}",
        "-af", f"volume=0.012,afade=t=in:st=0:d=0.15,afade=t=out:st={max(0.2, duration-0.2):.2f}:d=0.2",
        "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(out_wav),
    ])


class VoiceEngine:
    def __init__(self) -> None:
        cfg = load_settings().get("voice", {})
        self.engine_name = str(cfg.get("engine", "auto"))
        self.pause_ms = int(cfg.get("pause_between_scenes_ms", 320))
        self.kingvoice = _load_kingvoice(str(cfg.get("kingvoice_repo_path", "../kingvoice")))
        self.use_kingvoice = bool(self.kingvoice) and self.engine_name in {"auto", "kingvoice"}

    def _voice_key(self, language: str) -> str:
        cfg = load_settings().get("voice", {})
        return str(cfg.get(f"voice_{language}", "english_male"))

    def generate(self, script: dict[str, Any]) -> dict[str, Any]:
        language = script.get("language", "en")
        voice_key = self._voice_key(language)
        voice_id = VOICE_MAP.get(voice_key, VOICE_MAP["english_male"])
        run_dir = ensure_dir(data_path("voice", f"{script['topic_id']}_{language}"))

        scenes: list[dict[str, Any]] = []
        synthetic_used = False

        for scene in script["scenes"]:
            out_wav = run_dir / f"scene_{scene['index']:03d}.wav"
            emotion = scene.get("emotion", "neutral")
            preset = (self.kingvoice.EMOTION_PRESETS.get(emotion, self.kingvoice.EMOTION_PRESETS["neutral"])
                      if self.use_kingvoice else EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["neutral"]))
            # Keep preset values as plain strings for both integrations.
            preset = {k: str(v) for k, v in preset.items()}

            ok = False
            if self.use_kingvoice:
                try:
                    async def _call_kingvoice(coroutine_text: str = scene["text"],
                                              coroutine_emotion: str = emotion) -> None:
                        await asyncio.wait_for(
                            self.kingvoice.synthesize_chunk(
                                coroutine_text, voice_id, coroutine_emotion, str(out_wav)
                            ),
                            timeout=30,
                        )

                    asyncio.run(_call_kingvoice())
                    ok = out_wav.exists()
                except Exception as exc:  # noqa: BLE001
                    log.warning("King Voice synthesis failed on scene %d: %s", scene["index"], exc)

            if not ok:
                try:
                    asyncio.run(_synth_edge(scene["text"], voice_id, emotion, out_wav, preset))
                    ok = out_wav.exists()
                except Exception as exc:  # noqa: BLE001
                    log.warning("edge-tts unavailable on scene %d (%s); using synthetic bed",
                                scene["index"], exc)
                    _synth_synthetic(scene["text"], out_wav)
                    synthetic_used = True

            scenes.append({
                "index": scene["index"],
                "type": scene.get("type"),
                "emotion": emotion,
                "audio": str(out_wav),
                "duration": round(probe_duration(out_wav), 3),
                "text": scene["text"],
            })

        merged = self._merge_track(scenes, run_dir)
        manifest = {
            "topic_id": script["topic_id"],
            "language": language,
            "voice_key": voice_key,
            "voice_id": voice_id,
            "engine": "kingvoice" if self.use_kingvoice else "builtin-edge-tts",
            "synthetic": synthetic_used,
            "scene_count": len(scenes),
            "pause_ms": self.pause_ms,
            "scenes": scenes,
            "merged_audio": str(merged),
            "duration": round(probe_duration(merged), 2),
            "generated_at": iso_now(),
        }
        write_json(run_dir / "voice_manifest.json", manifest)
        log.info("Narration ready: %d scenes, %.1fs, engine=%s, synthetic=%s",
                 len(scenes), manifest["duration"], manifest["engine"], synthetic_used)
        return manifest

    def _merge_track(self, scenes: list[dict[str, Any]], run_dir: Path) -> Path:
        """Concatenate scene audio with natural pauses into narration.wav."""
        silence = run_dir / "pause.wav"
        run_command([
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", f"{self.pause_ms / 1000:.3f}",
            "-c:a", "pcm_s16le", str(silence),
        ])

        list_file = run_dir / "concat.txt"
        lines: list[str] = []
        for scene in scenes:
            lines.append(f"file '{scene['audio']}'")
            # A pause after every scene keeps the merged track exactly aligned
            # with the animated scene clips (each clip = audio length + pause).
            lines.append(f"file '{silence}'")
        list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        merged = run_dir / "narration.wav"
        run_command([
            "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-ar", "44100", "-ac", "1",
            "-c:a", "pcm_s16le", str(merged),
        ])
        return merged
