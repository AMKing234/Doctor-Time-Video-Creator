"""Small, dependency-light helpers used by every engine."""
from __future__ import annotations

import functools
import json
import re
import subprocess
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from common.paths import ensure_dirs


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str | Path, data: Any, indent: int = 2) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=indent)
    return p


def slugify(text: str, max_len: int = 70) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len] or "item"


def run_command(cmd: list[str], check: bool = True, capture: bool = True,
                timeout: int | None = None) -> subprocess.CompletedProcess:
    """Run FFmpeg/FFprobe etc. with sane defaults and an optional timeout."""
    result = subprocess.run(
        [str(c) for c in cmd],
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(map(str, cmd))}\n"
            f"{(result.stderr or '')[-2000:]}"
        )
    return result


def probe_duration(path: str | Path) -> float:
    """Return media duration in seconds using ffprobe, or 0.0 on failure."""
    try:
        res = run_command([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ])
        return float((res.stdout or "0").strip() or 0)
    except Exception:
        return 0.0


def srt_time(seconds: float) -> str:
    ms = int(max(0, seconds) * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path: str | Path, cues: Iterable[tuple[float, float, str]]) -> Path:
    lines = []
    for i, (start, end, text) in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{srt_time(start)} --> {srt_time(end)}")
        lines.append(text.strip())
        lines.append("")
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def retry(attempts: int = 3, delay: float = 1.5, backoff: float = 2.0,
          exceptions: tuple[type[BaseException], ...] = (Exception,)) -> Callable:
    """Exponential-backoff retry decorator for flaky network/API calls."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            wait = delay
            last: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:  # noqa: BLE001 - intentional broad catch
                    last = exc
                    if attempt < attempts:
                        time.sleep(wait)
                        wait *= backoff
            raise last  # type: ignore[misc]
        return wrapper
    return decorator


def human_duration(seconds: float) -> str:
    minutes, sec = divmod(int(seconds), 60)
    return f"{minutes:02d}:{sec:02d}"


def chunk_text(text: str, limit: int = 900) -> list[str]:
    """Split long narration into TTS-safe chunks, respecting sentence ends."""
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= limit:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks or [text.strip()]


def setup_runtime() -> None:
    ensure_dirs()
