"""Track pipeline runs, retry failed stages and persist error history."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Callable

from common.logging_setup import get_logger
from common.utils import iso_now
from database.manager import Database

log = get_logger("error_handler")


class StageFailed(RuntimeError):
    pass


class ErrorTracker:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database()

    def run(self, stage: str, fn: Callable[[], Any], attempts: int = 3) -> Any:
        run_id = uuid.uuid4().hex[:12]
        self.db.insert("runs", id=run_id, stage=stage, status="running",
                       started_at=iso_now(), details="{}")
        last: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                result = fn()
                self.db.update_run(run_id, status="success",
                                   finished_at=iso_now(), details=json.dumps({"attempt": attempt}))
                log.info("Stage %s completed (attempt %d)", stage, attempt)
                return result
            except Exception as exc:  # noqa: BLE001
                last = exc
                self.db.insert("errors", stage=stage, message=str(exc),
                               context=json.dumps({"attempt": attempt, "run_id": run_id}),
                               created_at=iso_now())
                log.warning("Stage %s failed (attempt %d/%d): %s", stage, attempt, attempts, exc)
                if attempt < attempts:
                    time.sleep(2 * attempt)
        self.db.update_run(run_id, status="failed", finished_at=iso_now(),
                           details=json.dumps({"error": str(last)}))
        raise StageFailed(f"Stage '{stage}' failed after {attempts} attempts: {last}")
