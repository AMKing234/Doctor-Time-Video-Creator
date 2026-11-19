"""Turn still visuals into moving cinematic scene clips with FFmpeg zoompan."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.config import load_settings
from common.logging_setup import get_logger
from common.paths import data_path, ensure_dir
from common.utils import probe_duration, run_command, write_json

log = get_logger("animation_engine")


class AnimationEngine:
    def __init__(self) -> None:
        video = load_settings().get("video", {})
        self.width = int(video.get("width", 1920))
        self.height = int(video.get("height", 1080))
        self.fps = int(video.get("fps", 30))

    def _motion(self, index: int, duration: float) -> str:
        """Alternate zoom-in, zoom-out and slow horizontal pans."""
        frames = max(2, int(duration * self.fps))
        fade_out = max(0.2, min(0.6, duration / 5))
        base = f"d=1:s={self.width}x{self.height}:fps={self.fps}"
        mode = index % 3
        if mode == 0:
            motion = f"z='min(zoom+0.0009,1.16)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        elif mode == 1:
            motion = f"z='max(zoom-0.0007,1.02)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        else:
            motion = (
                "z='1.10':x='(iw-iw/zoom)*(on/240)':y='ih/2-(ih/zoom/2)'"
            )
        return (
            f"scale={self.width * 2}:{self.height * 2},"
            f"zoompan={motion}:{base},"
            f"format=yuv420p,fade=t=in:st=0:d=0.5,"
            f"fade=t=out:st={max(0.1, duration - fade_out):.2f}:d={fade_out:.2f}"
        )

    def animate_scene(self, image: str | Path, out: Path, duration: float,
                      index: int) -> Path:
        run_command([
            "ffmpeg", "-y", "-v", "error",
            "-loop", "1", "-framerate", str(self.fps), "-i", str(image),
            "-t", f"{max(1.0, duration):.2f}",
            "-vf", self._motion(index, duration),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-r", str(self.fps), "-an", str(out),
        ])
        return out

    def generate(self, visual_manifest: dict[str, Any],
                 audio_manifest: dict[str, Any]) -> dict[str, Any]:
        """Animate each still for exactly its narration scene length."""
        out_dir = ensure_dir(data_path(
            "animation", f"{visual_manifest['topic_id']}_{visual_manifest['language']}"
        ))
        audio_by_index = {s["index"]: s for s in audio_manifest["scenes"]}
        clips: list[dict[str, Any]] = []

        for visual in visual_manifest["visuals"]:
            idx = visual["index"]
            audio = audio_by_index.get(idx)
            duration = float(audio["duration"]) if audio else 6.0
            duration += audio_manifest.get("pause_ms", 320) / 1000.0
            out = out_dir / f"scene_{idx:03d}.mp4"
            self.animate_scene(visual["path"], out, duration, idx)
            clips.append({
                "index": idx,
                "path": str(out),
                "duration": round(probe_duration(out), 3),
            })

        manifest = {
            "topic_id": visual_manifest["topic_id"],
            "language": visual_manifest["language"],
            "fps": self.fps,
            "clips": clips,
        }
        write_json(out_dir / "animation_manifest.json", manifest)
        log.info("Animated %d scenes -> %s", len(clips), out_dir)
        return manifest
