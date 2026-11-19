#!/usr/bin/env python3
"""yt-video: local documentary generation with guaranteed local delivery."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_agent.fallback import ensure_delivered
from main import Pipeline


def produce(test_mode: bool = False) -> dict:
    pipeline = Pipeline(test_mode=test_mode)
    pipeline.script()
    pipeline.voice()
    pipeline.visual()
    renders = pipeline.video()
    pipeline.seo()

    deliveries = []
    for render in renders:
        video_id = f"{render['topic_id']}_{render['language']}"
        deliveries.append(ensure_delivered(None, video_id,
                                           "upload deferred to local YouTube node"))
    return {"renders": [r["video_path"] for r in renders], "deliveries": deliveries}


def main() -> None:
    parser = argparse.ArgumentParser(description="yt-video local production skill")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = produce(args.test)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str) if args.json else result)


if __name__ == "__main__":
    main()
