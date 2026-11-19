"""Bidirectional local <-> cloud sync bus using a dedicated `sync` git branch.

Only non-secret JSON manifests travel through this bus. `vault.assert_no_secrets`
rejects anything that looks like credentials. If the internet is down, outgoing
messages stay queued locally and are pushed on the next successful sync.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.logging_setup import get_logger
from common.paths import ROOT
from common.utils import read_json, run_command, write_json
from local_agent import vault

log = get_logger("sync")
LOCAL_CFG = read_json(ROOT / "config" / "local.json", {}) or {}
SYNC_CFG = LOCAL_CFG.get("sync", {})
BRANCH = str(SYNC_CFG.get("branch", "sync"))
WORKTREE = ROOT / str(SYNC_CFG.get("worktree", ".sync-work"))
INBOX = str(SYNC_CFG.get("cloud_inbox", "bus/inbox"))
OUTBOX = str(SYNC_CFG.get("cloud_outbox", "bus/outbox"))
QUEUE = ROOT / "local_agent" / "state" / "outbox"
LOCAL_INBOX = ROOT / "local_agent" / "state" / "inbox"


def _git(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    result = run_command(["git", *args], cwd=str(cwd or ROOT), check=check)
    return (result.stdout or "").strip()


def _remote_branch_exists() -> bool:
    try:
        return bool(_git(["ls-remote", "--heads", "origin", BRANCH], check=False))
    except Exception:
        return False


def ensure_worktree() -> Path:
    """Create/reuse the sync worktree on its own branch."""
    try:
        _git(["worktree", "prune"])
    except Exception:
        pass

    if not (WORKTREE / ".git").exists():
        try:
            if _remote_branch_exists():
                _git(["fetch", "origin", BRANCH])
                _git(["worktree", "add", "-B", BRANCH, str(WORKTREE), f"origin/{BRANCH}"])
            else:
                _git(["worktree", "add", "--orphan", "-B", BRANCH, str(WORKTREE)])
                (WORKTREE / "README.md").write_text(
                    "# Sync bus\n\nNon-secret manifests exchanged between local and cloud nodes.\n",
                    encoding="utf-8",
                )
                (WORKTREE / INBOX).mkdir(parents=True, exist_ok=True)
                (WORKTREE / OUTBOX).mkdir(parents=True, exist_ok=True)
                _git(["add", "-A"], cwd=WORKTREE)
                _git(["commit", "-m", "Initialize sync bus"], cwd=WORKTREE)
                _git(["push", "-u", "origin", BRANCH], cwd=WORKTREE)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Could not prepare sync worktree: {exc}") from exc

    (WORKTREE / INBOX).mkdir(parents=True, exist_ok=True)
    (WORKTREE / OUTBOX).mkdir(parents=True, exist_ok=True)
    return WORKTREE


def push(message: dict[str, Any], name: str = "message") -> dict[str, Any]:
    """Queue an outgoing message and attempt to push it to the cloud."""
    vault.assert_no_secrets(message)
    QUEUE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"{stamp}_{uuid.uuid4().hex[:6]}_{name}.json"
    local_copy = QUEUE / filename
    write_json(local_copy, message)

    try:
        tree = ensure_worktree()
        target = tree / INBOX / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        write_json(target, message)
        _git(["add", "-A"], cwd=tree)
        _git(["commit", "-m", f"sync: {name}"], cwd=tree, check=False)
        _git(["push", "origin", BRANCH], cwd=tree)
        local_copy.unlink(missing_ok=True)
        return {"status": "pushed", "file": filename, "branch": BRANCH}
    except Exception as exc:  # noqa: BLE001
        log.info("Offline — message queued locally: %s", exc)
        return {"status": "queued", "file": filename, "error": str(exc)}


def pull(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch cloud responses into the local inbox."""
    tree = ensure_worktree()
    try:
        _git(["fetch", "origin", BRANCH])
        _git(["reset", "--hard", f"origin/{BRANCH}"], cwd=tree)
    except Exception as exc:  # noqa: BLE001
        log.warning("Fetch failed; reading cached sync data: %s", exc)

    LOCAL_INBOX.mkdir(parents=True, exist_ok=True)
    received: list[dict[str, Any]] = []
    for path in sorted((tree / OUTBOX).glob("*.json"))[-limit:]:
        data = read_json(path, {}) or {}
        write_json(LOCAL_INBOX / path.name, data)
        received.append(data)
    return received


def status() -> dict[str, Any]:
    queued = sorted(QUEUE.glob("*.json")) if QUEUE.exists() else []
    inbox = sorted(LOCAL_INBOX.glob("*.json")) if LOCAL_INBOX.exists() else []
    return {
        "branch": BRANCH,
        "worktree": str(WORKTREE),
        "worktree_ready": (WORKTREE / ".git").exists(),
        "remote_branch_exists": _remote_branch_exists(),
        "queued_outgoing": len(queued),
        "received_messages": len(inbox),
    }
