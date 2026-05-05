"""Perceptual-hash ranking.

For each candidate we compare the query image's pHash to the candidate's
thumbnail pHash (Hamming distance over a 64-bit hash). This is fast, requires
no model weights, and is enough to push the *visually closest* product to the
top before we spend bandwidth downloading videos.

A more accurate ranker would use CLIP image embeddings; we keep this swappable.
"""

from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import httpx
import imagehash
from PIL import Image

from .models import SearchCandidate
from .search.base import DEFAULT_HEADERS

_HASH_BITS = 64  # imagehash.phash default size 8 -> 64-bit


def _phash_from_bytes(data: bytes) -> imagehash.ImageHash | None:
    try:
        with Image.open(BytesIO(data)) as img:
            return imagehash.phash(img.convert("RGB"))
    except Exception:
        return None


def phash_from_path(path: Path) -> imagehash.ImageHash | None:
    return _phash_from_bytes(path.read_bytes())


def similarity(a: imagehash.ImageHash | None, b: imagehash.ImageHash | None) -> float:
    if a is None or b is None:
        return 0.0
    distance = a - b  # Hamming distance
    return max(0.0, 1.0 - distance / _HASH_BITS)


async def _fetch_thumb(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        resp = await client.get(url, timeout=10.0)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    return resp.content


async def score_candidates(
    query_image: Path,
    candidates: list[SearchCandidate],
) -> list[tuple[SearchCandidate, float]]:
    """Return (candidate, similarity) pairs sorted by similarity desc.

    Candidates without thumbnails get score 0.0 but stay in the list so the
    pipeline can still try to download them as a last resort.
    """
    query_hash = phash_from_path(query_image)
    if query_hash is None:
        # Can't hash query -> can't rank. Preserve original order.
        return [(c, 0.0) for c in candidates]

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        thumb_bytes = await asyncio.gather(
            *(
                _fetch_thumb(client, c.thumbnail_url) if c.thumbnail_url else _none()
                for c in candidates
            )
        )

    scored: list[tuple[SearchCandidate, float]] = []
    for cand, data in zip(candidates, thumb_bytes, strict=True):
        if not data:
            scored.append((cand, 0.0))
            continue
        h = _phash_from_bytes(data)
        scored.append((cand, similarity(query_hash, h)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


async def _none() -> bytes | None:
    return None
