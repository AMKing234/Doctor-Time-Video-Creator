"""Local-only YouTube OAuth, verification and upload.

Credentials never leave local_agent/vault/. This module is never called by the
cloud workflows; the cloud only produces metadata manifests.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.config import load_settings
from common.logging_setup import get_logger
from common.paths import ROOT
from common.utils import read_json
from database.manager import Database
from local_agent import vault

log = get_logger("local_youtube")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _creds():
    from google.oauth2.credentials import Credentials

    secrets_path, token_path = vault.youtube_paths()
    if not token_path.exists():
        raise RuntimeError("YouTube not connected. Run: python local_agent/agent.py --setup-youtube <client_secrets.json>")
    data = vault.load(token_path.name, {}) or {}
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", SCOPES),
    )


def _refresh_if_needed(creds) -> Any:
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        secrets_path, token_path = vault.youtube_paths()
        vault.save(token_path.name, json_load(creds.to_json()))
        return creds
    raise RuntimeError("YouTube credentials expired; reconnect required")


def json_load(text: str) -> dict[str, Any]:
    import json
    return json.loads(text)


def setup(client_secrets_path: str | Path) -> dict[str, Any]:
    """Import client secrets, run OAuth locally and verify the channel."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets_path, token_path = vault.youtube_paths()
    vault.ensure_vault()
    vault.import_file(client_secrets_path, secrets_path.name)
    log.info("Client secrets imported locally: %s", secrets_path)

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    try:
        creds = flow.run_console()
    except Exception as exc:  # noqa: BLE001
        log.warning("Console OAuth failed (%s); trying local server", exc)
        creds = flow.run_local_server(port=0)

    vault.save(token_path.name, json_load(creds.to_json()))
    log.info("Token stored in local vault (never in git): %s", token_path)
    return verify()


def verify() -> dict[str, Any]:
    from googleapiclient.discovery import build

    creds = _refresh_if_needed(_creds())
    service = build("youtube", "v3", credentials=creds)
    response = service.channels().list(part="snippet,statistics", mine=True).execute()
    items = response.get("items") or []
    if not items:
        raise RuntimeError("OAuth OK but no YouTube channel found for this account")
    item = items[0]
    return {
        "connected": True,
        "channel_id": item["id"],
        "title": item["snippet"]["title"],
        "subscribers": item.get("statistics", {}).get("subscriberCount"),
        "token_location": str(vault.youtube_paths()[1]),
        "stored_in_git": False,
    }


def status() -> dict[str, Any]:
    secrets_path, token_path = vault.youtube_paths()
    result: dict[str, Any] = {
        "client_secrets_present": secrets_path.exists(),
        "token_present": token_path.exists(),
        "connected": False,
        "stored_in_git": False,
    }
    if not token_path.exists():
        return result
    try:
        result.update(verify())
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    return result


def upload(video_path: str | Path, seo: dict[str, Any],
           thumbnail_path: str | Path | None = None,
           publish_at: str | None = None) -> dict[str, Any]:
    """Upload from THIS device only. No credentials are sent anywhere."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(video)

    creds = _refresh_if_needed(_creds())
    service = build("youtube", "v3", credentials=creds)
    privacy = str(load_settings().get("upload", {}).get("privacy", "private"))
    body = {
        "snippet": {
            "title": seo["title"],
            "description": seo["description"],
            "tags": seo.get("tags", []),
            "categoryId": seo.get("category_id", "27"),
            "defaultLanguage": "hi" if seo.get("language") == "hi" else "en",
        },
        "status": {
            "privacyStatus": "private" if publish_at else privacy,
            "embeddable": True,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4", resumable=True,
                            chunksize=8 * 1024 * 1024)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response["id"]

    if thumbnail_path and Path(thumbnail_path).exists():
        service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
        ).execute()

    if publish_at:
        service.videos().update(
            part="status",
            body={"id": video_id, "status": {"privacyStatus": "private",
                                              "publishAt": publish_at}},
        ).execute()

    result = {
        "youtube_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "uploaded_from": "local",
        "credentials_location": "local vault only",
    }
    video_key = seo.get("video_id")
    if video_key:
        try:
            Database().update_video(video_key, youtube_id=video_id,
                                    status="uploaded", scheduled_for=publish_at)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not update local DB: %s", exc)
    return result
