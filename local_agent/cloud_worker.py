"""Cloud-side sync bus worker (runs inside GitHub Actions).

Reads non-secret manifests from `bus/inbox` and writes replies to `bus/outbox`.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.utils import read_json, write_json
from local_agent import vault


def process(bus_dir: Path) -> dict[str, Any]:
    inbox = bus_dir / "bus" / "inbox"
    outbox = bus_dir / "bus" / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    processed = 0

    for path in sorted(inbox.glob("*.json")):
        message = read_json(path, {}) or {}
        kind = str(message.get("type", "unknown"))
        reply: dict[str, Any] = {
            "type": "ack",
            "reply_to": path.name,
            "original_type": kind,
            "node": "cloud",
            "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "ok",
        }
        if kind == "status_request":
            from database.manager import Database
            try:
                reply["stats"] = Database().stats()
            except Exception as exc:  # noqa: BLE001
                reply["stats_error"] = str(exc)
        elif kind == "production_request":
            reply["note"] = ("Production job accepted. Trigger Actions workflow "
                             "video-production.yml manually or via main.yml schedule.")
        else:
            reply["note"] = "Message received by cloud worker."

        vault.assert_no_secrets(reply)
        write_json(outbox / f"ack_{path.name}", reply)
        processed += 1
        path.unlink(missing_ok=True)

    return {"processed": processed, "outbox": str(outbox)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloud sync bus worker")
    parser.add_argument("--bus", default="sync-data", help="checked-out sync branch directory")
    args = parser.parse_args()
    result = process(Path(args.bus))
    print(result)


if __name__ == "__main__":
    main()
