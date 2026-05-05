"""End-to-end pipeline: image -> ProductQuery -> candidates -> ranked -> videos."""

from __future__ import annotations

import asyncio
from pathlib import Path

from .config import settings
from .download import DownloadError, download_candidate
from .models import ProductQuery, SearchCandidate, VideoResult
from .rank import score_candidates
from .search import ADAPTERS
from .vision import extract_query


def _cookie_for(platform: str) -> str:
    return {
        "taobao": settings.taobao_cookie,
        "alibaba1688": settings.alibaba1688_cookie,
        "douyin": settings.douyin_cookie,
    }.get(platform, "")


async def run_search(query: ProductQuery, platforms: list[str], per_platform_limit: int):
    async def search_one(name: str) -> list[SearchCandidate]:
        cls = ADAPTERS.get(name)
        if cls is None:
            return []
        async with cls(cookie=_cookie_for(name)) as adapter:
            try:
                return await adapter.search(query, limit=per_platform_limit)
            except Exception:
                return []

    results = await asyncio.gather(*(search_one(p) for p in platforms))
    flat: list[SearchCandidate] = []
    for r in results:
        flat.extend(r)
    return flat


async def find_videos(image_path: Path) -> tuple[ProductQuery, list[VideoResult]]:
    """Top-level entrypoint."""
    query = extract_query(image_path)

    candidates = await run_search(
        query,
        platforms=settings.platform_list,
        per_platform_limit=settings.max_candidates_per_platform,
    )

    # Auto-fallback to SerpAPI if direct scraping yielded nothing useful.
    if not candidates and settings.serpapi_key and "serpapi" not in settings.platform_list:
        candidates = await run_search(
            query, platforms=["serpapi"], per_platform_limit=settings.max_candidates_per_platform
        )

    if not candidates:
        return query, []

    ranked = await score_candidates(image_path, candidates)

    # Try to download in similarity order until we have N successful results.
    results: list[VideoResult] = []
    for cand, sim in ranked:
        if len(results) >= settings.max_results:
            break
        try:
            res = await download_candidate(cand, settings.download_dir)
        except DownloadError:
            continue
        res.similarity = sim
        results.append(res)
    return query, results
