"""Video URL extraction and download.

Two-stage flow:
1. If the candidate already has a `video_url` (e.g. Douyin page), pass it
   straight to yt-dlp.
2. Otherwise, fetch the product page HTML and try to mine a video URL out of
   it. Taobao / 1688 / Tmall embed video URLs in inline JSON under a small set
   of keys; we try them in order.

If the per-page extractor finds nothing, we fall back to yt-dlp's generic
extractor on the page URL, which handles many sites' <video> tags and JSON-LD.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from yt_dlp import YoutubeDL

from .models import SearchCandidate, VideoResult
from .search.base import DEFAULT_HEADERS


# Order matters: more specific keys first.
_VIDEO_URL_PATTERNS = [
    re.compile(r'"videoMainUrl"\s*:\s*"([^"]+\.mp4[^"]*)"'),
    re.compile(r'"mainVideoUrl"\s*:\s*"([^"]+\.mp4[^"]*)"'),
    re.compile(r'"videoUrl"\s*:\s*"([^"]+\.mp4[^"]*)"'),
    re.compile(r'"video_url"\s*:\s*"([^"]+\.mp4[^"]*)"'),
    re.compile(r'"playAddr"\s*:\s*"([^"]+\.mp4[^"]*)"'),
    re.compile(r'<video[^>]+src="([^"]+\.mp4[^"]*)"'),
]


@dataclass
class DownloadError(Exception):
    candidate: SearchCandidate
    reason: str

    def __str__(self) -> str:  # pragma: no cover - debug aid
        return f"{self.candidate.platform} {self.candidate.product_url}: {self.reason}"


async def resolve_video_url(candidate: SearchCandidate) -> str | None:
    """Return a downloadable URL (direct .mp4 or page URL yt-dlp can handle)."""
    if candidate.video_url:
        return candidate.video_url

    # Douyin page URLs are best handled by yt-dlp's extractor directly.
    if candidate.platform == "douyin":
        return candidate.product_url

    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        timeout=15.0,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(candidate.product_url)
        except Exception:
            return None
        if resp.status_code != 200:
            return None
        for pat in _VIDEO_URL_PATTERNS:
            m = pat.search(resp.text)
            if m:
                # JSON-escaped URLs sometimes carry literal "/" or "\\/".
                url = m.group(1).replace("\\u002F", "/").replace("\\/", "/")
                return url
    # Fall through: let yt-dlp's generic extractor try the page URL.
    return candidate.product_url


def _sync_download(url: str, dest_dir: Path) -> tuple[Path, dict]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(dest_dir / "%(extractor)s-%(id)s-%(title).80s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "restrictfilenames": True,
        "retries": 3,
        "concurrent_fragment_downloads": 4,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise RuntimeError("yt-dlp returned no info")
        # Some extractors return a playlist; pick the first entry.
        if info.get("_type") == "playlist":
            entries = info.get("entries") or []
            if not entries:
                raise RuntimeError("empty playlist")
            info = entries[0]
        path = Path(ydl.prepare_filename(info))
    return path, info


async def download_candidate(candidate: SearchCandidate, dest_dir: Path) -> VideoResult:
    url = await resolve_video_url(candidate)
    if not url:
        raise DownloadError(candidate, "could not resolve video URL")
    try:
        path, info = await asyncio.to_thread(_sync_download, url, dest_dir)
    except Exception as e:
        raise DownloadError(candidate, f"yt-dlp failed: {e}") from e
    return VideoResult(
        candidate=candidate,
        local_path=path,
        duration_sec=info.get("duration"),
        width=info.get("width"),
        height=info.get("height"),
    )
