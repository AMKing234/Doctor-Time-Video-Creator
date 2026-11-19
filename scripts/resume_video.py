"""Resume a direct video from existing scripts/voice (skips slow TTS stage)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import Pipeline


def main() -> None:
    pipeline = Pipeline()
    print("scripts:", [(s["language"], s["scene_count"]) for s in pipeline._scripts()], flush=True)
    print("VISUALS", flush=True)
    pipeline.visual()
    print("RENDER", flush=True)
    renders = pipeline.video()
    print("SEO", flush=True)
    pipeline.seo()
    print("SKILLS + ARCHIVE", flush=True)
    skills = pipeline.skills_stage()

    downloads = Path("/sdcard/Download")
    saved: list[str] = []
    if downloads.is_dir():
        for render in renders:
            src = Path(render["video_path"])
            if src.exists():
                dst = downloads / f"stone-age-to-modern-age_{render['language']}.mp4"
                dst.write_bytes(src.read_bytes())
                saved.append(str(dst))

    print(json.dumps({
        "videos": renders,
        "archives": [r["delivery"] for r in skills["reports"]],
        "downloaded": saved,
    }, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
