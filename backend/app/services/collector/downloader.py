"""URL-based video downloader using yt-dlp.

Supports Instagram Reels and TikTok. Users paste URLs manually; no scraping.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class DownloadResult:
    platform: str
    platform_video_id: str | None
    url: str
    local_path: Path
    caption: str | None
    uploader: str | None
    duration_sec: float | None
    width: int | None
    height: int | None
    view_count: int | None
    like_count: int | None
    posted_at: datetime | None


def platform_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "tiktok" in host:
        return "tiktok"
    if "instagram" in host:
        return "instagram"
    return "other"


def _ydl_opts(out_tmpl: str, cookies_file: str = "") -> dict:
    opts: dict = {
        "outtmpl": out_tmpl,
        "format": "mp4/bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "nocheckcertificate": True,
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file
    return opts


def _parse_ts(ts: int | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, OSError):
        return None


def download_url(url: str, dest_dir: Path | None = None) -> DownloadResult:
    """Download a reel/video from URL and return rich metadata."""
    settings = get_settings()
    dest_dir = dest_dir or settings.sources_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    out_tmpl = str(dest_dir / "%(extractor)s-%(id)s.%(ext)s")
    opts = _ydl_opts(out_tmpl, cookies_file=settings.ytdlp_cookies_file)

    log.info("Downloading %s", url)
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise RuntimeError(f"yt-dlp returned no info for {url}")
        # Flat playlists can wrap a single entry.
        if "entries" in info and info.get("entries"):
            info = info["entries"][0]
        file_path = Path(ydl.prepare_filename(info))
        if file_path.suffix != ".mp4":
            # yt-dlp may leave source ext; the merged mp4 is alongside.
            mp4 = file_path.with_suffix(".mp4")
            if mp4.exists():
                file_path = mp4

    if not file_path.exists():
        raise FileNotFoundError(f"Expected downloaded file not found: {file_path}")

    platform = platform_from_url(url)
    return DownloadResult(
        platform=platform,
        platform_video_id=info.get("id"),
        url=url,
        local_path=file_path,
        caption=info.get("description") or info.get("title"),
        uploader=info.get("uploader") or info.get("channel"),
        duration_sec=info.get("duration"),
        width=info.get("width"),
        height=info.get("height"),
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        posted_at=_parse_ts(info.get("timestamp")),
    )
