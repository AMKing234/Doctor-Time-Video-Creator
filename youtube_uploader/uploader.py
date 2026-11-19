"""YouTube upload + scheduling.

SAFETY: upload.enabled is false in config/settings.json and YOUTUBE_ENABLED
defaults to false. Running the upload stage therefore only writes a dry-run
manifest describing what WOULD be uploaded. Set both explicitly to go live.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from common.config import load_settings
from common.control import upload_override
from common.logging_setup import get_logger
from common.paths import data_path, ensure_dir
from common.utils import iso_now, write_json
from database.manager import Database

log = get_logger("youtube_uploader")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]


class YouTubeUploader:
    def __init__(self, db: Database | None = None) -> None:
        cfg = load_settings().get("upload", {})
        override = upload_override()
        if override is not None:
            # Dashboard switch is explicit: ON attempts a live upload, OFF stays dry-run.
            self.enabled = override
            self.dry_run = not override
        else:
            self.enabled = bool(cfg.get("enabled", False))
            env_enabled = os.environ.get("YOUTUBE_ENABLED", "").strip().lower()
            if env_enabled:
                self.enabled = env_enabled in {"1", "true", "yes", "on"}
            self.dry_run = bool(cfg.get("dry_run", True)) or not self.enabled
        self.privacy = str(cfg.get("privacy", "private"))
        self.schedule_enabled = bool(cfg.get("schedule_enabled", False))
        self.db = db or Database()

    def _build_service(self):
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        token_file = Path(os.environ.get("YOUTUBE_TOKEN_FILE", "token.json"))
        secrets_file = Path(os.environ.get("YOUTUBE_CLIENT_SECRETS", "client_secrets.json"))
        creds = None
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(__import__("google.auth.transport.requests", fromlist=["Request"]).Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), SCOPES)
                creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=creds)

    def _live_upload(self, seo: dict[str, Any], render: dict[str, Any],
                     thumbnail: dict[str, Any] | None) -> str:
        from googleapiclient.http import MediaFileUpload

        service = self._build_service()
        body = {
            "snippet": {
                "title": seo["title"],
                "description": seo["description"],
                "tags": seo["tags"],
                "categoryId": seo["category_id"],
                "defaultLanguage": "hi" if seo["language"] == "hi" else "en",
            },
            "status": {
                "privacyStatus": "private" if self.schedule_enabled else self.privacy,
                "embeddable": True,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(render["video_path"], mimetype="video/mp4",
                                resumable=True, chunksize=8 * 1024 * 1024)
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
        video_id = response["id"]

        if thumbnail and Path(thumbnail["path"]).exists():
            service.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail["path"], mimetype="image/jpeg"),
            ).execute()

        if self.schedule_enabled:
            scheduled = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            service.videos().update(
                part="status",
                body={"id": video_id, "status": {"privacyStatus": "private",
                                                  "publishAt": scheduled}},
            ).execute()
        return video_id

    def upload(self, seo: dict[str, Any], render: dict[str, Any],
               thumbnail: dict[str, Any] | None = None,
               scheduled_for: str | None = None) -> dict[str, Any]:
        plan = {
            "video_id": seo["video_id"],
            "title": seo["title"],
            "video_path": render["video_path"],
            "thumbnail_path": thumbnail["path"] if thumbnail else None,
            "privacy": self.privacy,
            "scheduled_for": scheduled_for,
            "mode": "dry-run" if self.dry_run else "live",
            "created_at": iso_now(),
        }

        if self.dry_run:
            log.info("DRY RUN — upload disabled. Nothing was sent to YouTube.")
            log.info("Would upload: %s | %s", seo["title"], render["video_path"])
        else:
            try:
                plan["youtube_id"] = self._live_upload(seo, render, thumbnail)
                self.db.update_video(seo["video_id"], youtube_id=plan["youtube_id"],
                                     status="uploaded", scheduled_for=scheduled_for)
                log.info("Uploaded video: %s", plan["youtube_id"])
            except Exception as exc:  # noqa: BLE001
                plan["mode"] = "failed"
                plan["error"] = str(exc)
                log.error("YouTube upload failed: %s", exc)

        out_dir = ensure_dir(data_path("uploads"))
        write_json(out_dir / f"{seo['video_id']}.json", plan)
        return plan
