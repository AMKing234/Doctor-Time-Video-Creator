"""Persistent state: topics, research, scripts, videos, analytics, runs, errors.

SQLite keeps the system self-contained in GitHub Actions. Large media files are
stored via the storage module (external), only their metadata paths live here.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from common.paths import DATA_DIR, ensure_dirs
from common.utils import iso_now

DB_PATH = DATA_DIR / "automation.db"


class Database:
    def __init__(self, path: str | Path | None = None) -> None:
        ensure_dirs()
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS topics (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title_en TEXT NOT NULL,
                    title_hi TEXT NOT NULL,
                    tags TEXT,
                    score REAL DEFAULT 0,
                    status TEXT DEFAULT 'discovered',
                    created_at TEXT,
                    used_at TEXT
                );

                CREATE TABLE IF NOT EXISTS research (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT,
                    UNIQUE(topic_id, created_at)
                );

                CREATE TABLE IF NOT EXISTS scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    path TEXT NOT NULL,
                    scene_count INTEGER DEFAULT 0,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    topic_id TEXT,
                    language TEXT,
                    title TEXT,
                    video_path TEXT,
                    thumbnail_path TEXT,
                    seo_path TEXT,
                    duration REAL,
                    status TEXT DEFAULT 'rendered',
                    youtube_id TEXT,
                    scheduled_for TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT,
                    views INTEGER DEFAULT 0,
                    watch_time_minutes REAL DEFAULT 0,
                    avg_view_duration REAL DEFAULT 0,
                    engagement_rate REAL DEFAULT 0,
                    best_hour INTEGER,
                    captured_at TEXT
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    stage TEXT,
                    status TEXT,
                    details TEXT,
                    started_at TEXT,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stage TEXT,
                    message TEXT,
                    context TEXT,
                    created_at TEXT
                );
                """
            )

    # -- topics -----------------------------------------------------------
    def upsert_topic(self, topic: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO topics
                   (id, category, title_en, title_hi, tags, score, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     score=excluded.score, status=excluded.status""",
                (
                    topic["id"], topic["category"], topic["title"]["en"],
                    topic["title"]["hi"], ",".join(topic.get("tags", [])),
                    float(topic.get("score", 0)), topic.get("status", "discovered"),
                    iso_now(),
                ),
            )

    def is_topic_used(self, topic_id: str, freshness_days: int = 30) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT used_at FROM topics WHERE id=?", (topic_id,)
            ).fetchone()
        if not row or not row["used_at"]:
            return False
        from datetime import datetime, timedelta, timezone
        try:
            used = datetime.fromisoformat(row["used_at"])
            return datetime.now(timezone.utc) - used < timedelta(days=freshness_days)
        except ValueError:
            return True

    def mark_topic_used(self, topic_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE topics SET used_at=?, status='used' WHERE id=?",
                (iso_now(), topic_id),
            )

    def all_topics(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM topics ORDER BY created_at DESC")]

    # -- generic record helper -------------------------------------------
    def insert(self, table: str, **fields: Any) -> int:
        allowed = {
            "research": {"topic_id", "payload", "created_at"},
            "scripts": {"topic_id", "language", "path", "scene_count", "created_at"},
            "videos": {"id", "topic_id", "language", "title", "video_path",
                       "thumbnail_path", "seo_path", "duration", "status",
                       "youtube_id", "scheduled_for", "created_at"},
            "analytics": {"video_id", "views", "watch_time_minutes",
                          "avg_view_duration", "engagement_rate", "best_hour",
                          "captured_at"},
            "runs": {"id", "stage", "status", "details", "started_at", "finished_at"},
            "errors": {"stage", "message", "context", "created_at"},
        }
        if table not in allowed:
            raise ValueError(f"Unknown table: {table}")
        cols = [c for c in fields if c in allowed[table]]
        values = [fields[c] for c in cols]
        placeholders = ",".join("?" for _ in cols)
        with self.connect() as conn:
            cur = conn.execute(
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                values,
            )
            return int(cur.lastrowid)

    def update_video(self, video_id: str, **fields: Any) -> None:
        allowed = {"title", "video_path", "thumbnail_path", "seo_path", "duration",
                   "status", "youtube_id", "scheduled_for"}
        cols = [c for c in fields if c in allowed]
        if not cols:
            return
        sets = ",".join(f"{c}=?" for c in cols)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE videos SET {sets} WHERE id=?",
                [fields[c] for c in cols] + [video_id],
            )

    def update_run(self, run_id: str, **fields: Any) -> None:
        allowed = {"stage", "status", "details", "started_at", "finished_at"}
        cols = [c for c in fields if c in allowed]
        if not cols:
            return
        sets = ",".join(f"{c}=?" for c in cols)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE runs SET {sets} WHERE id=?",
                [fields[c] for c in cols] + [run_id],
            )

    def records(self, table: str, limit: int = 50) -> list[dict[str, Any]]:
        if table not in {"topics", "research", "scripts", "videos", "analytics", "runs", "errors"}:
            raise ValueError(f"Unknown table: {table}")
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,)
            )]

    def stats(self) -> dict[str, int]:
        out: dict[str, int] = {}
        with self.connect() as conn:
            for table in ("topics", "videos", "runs", "errors", "analytics"):
                out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return out
