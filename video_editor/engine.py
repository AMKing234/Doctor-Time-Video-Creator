"""Assemble the final 1920x1080 documentary with narration, music and captions."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.config import load_settings
from common.logging_setup import get_logger
from common.paths import data_path, ensure_dir
from common.utils import iso_now, probe_duration, run_command, write_json, write_srt

log = get_logger("video_editor")


def _split_caption(text: str, per_cue: int = 16) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + per_cue]) for i in range(0, len(words), per_cue)] or [text]


class VideoEditor:
    def __init__(self) -> None:
        self.video_cfg = load_settings().get("video", {})
        self.music_volume = float(self.video_cfg.get("background_music_volume", 0.12))
        self.narration_volume = float(self.video_cfg.get("narration_volume", 1.0))

    def _concat_clips(self, clips: list[dict[str, Any]], out: Path) -> Path:
        list_file = out.with_suffix(".concat.txt")
        list_file.write_text(
            "\n".join(f"file '{c['path']}'" for c in clips) + "\n", encoding="utf-8"
        )
        run_command([
            "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(out),
        ])
        list_file.unlink(missing_ok=True)
        return out

    def _music_bed(self, duration: float, out: Path) -> Path:
        run_command([
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i",
            f"anoisesrc=color=brown:amplitude=0.35:sample_rate=44100:duration={duration:.2f}",
            "-f", "lavfi", "-i",
            f"sine=frequency=110:sample_rate=44100:duration={duration:.2f}",
            "-f", "lavfi", "-i",
            f"sine=frequency=164.81:sample_rate=44100:duration={duration:.2f}",
            "-filter_complex",
            "[0:a]lowpass=f=600,volume=0.5[n];"
            "[1:a]volume=0.09[s1];[2:a]volume=0.05[s2];"
            "[n][s1][s2]amix=inputs=3:duration=first[m]",
            "-map", "[m]", "-c:a", "aac", "-b:a", "128k", str(out),
        ])
        return out

    def _subtitles(self, script: dict[str, Any], audio: dict[str, Any],
                   out: Path) -> Path:
        audio_by_index = {s["index"]: s for s in audio["scenes"]}
        pause = audio.get("pause_ms", 320) / 1000.0
        cues: list[tuple[float, float, str]] = []
        cursor = 0.0
        for scene in script["scenes"]:
            a = audio_by_index.get(scene["index"])
            spoken = float(a["duration"]) if a else 6.0
            chunks = _split_caption(scene["text"])
            per = spoken / len(chunks)
            for i, chunk in enumerate(chunks):
                cues.append((cursor + i * per, cursor + (i + 1) * per, chunk))
            cursor += spoken + pause
        return write_srt(out, cues)

    def render(self, script: dict[str, Any], animation: dict[str, Any],
               audio: dict[str, Any]) -> dict[str, Any]:
        out_dir = ensure_dir(data_path("videos", f"{script['topic_id']}_{script['language']}"))
        silent = out_dir / "silent.mp4"
        self._concat_clips(animation["clips"], silent)

        duration = probe_duration(silent)
        if duration <= 0:
            raise RuntimeError("Concatenated video has zero duration")

        music = self._music_bed(duration, out_dir / "music.m4a")
        srt = self._subtitles(script, audio, out_dir / "captions.srt")

        fade = min(1.0, duration / 6)
        fade_out_start = max(0.0, duration - fade)
        filter_complex = (
            f"[1:a]volume={self.narration_volume},"
            f"afade=t=in:st=0:d={fade:.2f},"
            f"afade=t=out:st={fade_out_start:.2f}:d={fade:.2f}[n];"
            f"[2:a]volume={self.music_volume}[m];"
            f"[n][m]amix=inputs=2:duration=first:dropout_transition=0[a]"
        )

        # Two-step mux: Termux FFmpeg can deadlock when a subtitle input is read
        # in the same filtergraph as a re-encoded video + `-shortest`. Render the
        # picture+sound once, then burn in subtitles with a stream copy.
        base = out_dir / "final_no_subs.mp4"
        final = out_dir / "final.mp4"
        final.unlink(missing_ok=True)
        run_command([
            "ffmpeg", "-y", "-v", "error",
            "-i", str(silent), "-i", audio["merged_audio"], "-i", str(music),
            "-filter_complex", filter_complex,
            "-vf", f"fade=t=in:st=0:d={fade:.2f},"
                   f"fade=t=out:st={fade_out_start:.2f}:d={fade:.2f}",
            "-map", "0:v:0", "-map", "[a]",
            "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-r", str(load_settings().get("video", {}).get("fps", 30)),
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart", str(base),
        ], timeout=1800)

        try:
            run_command([
                "ffmpeg", "-y", "-v", "error",
                "-i", str(base), "-i", str(srt),
                "-map", "0", "-map", "1", "-c", "copy", "-c:s", "mov_text",
                "-movflags", "+faststart", str(final),
            ], timeout=300)
        except Exception as exc:  # noqa: BLE001
            log.warning("Subtitle mux failed (%s); keeping external SRT", exc)
            final = base

        manifest = {
            "topic_id": script["topic_id"],
            "language": script["language"],
            "title": script["title"],
            "video_path": str(final),
            "subtitle_path": str(srt),
            "music_path": str(music),
            "duration": round(probe_duration(final), 2),
            "resolution": f"{self.video_cfg.get('width', 1920)}x{self.video_cfg.get('height', 1080)}",
            "rendered_at": iso_now(),
        }
        write_json(out_dir / "render_manifest.json", manifest)
        log.info("Final video rendered: %.1fs -> %s", manifest["duration"], final)
        return manifest
