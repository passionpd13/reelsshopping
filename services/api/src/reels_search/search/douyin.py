"""Douyin search adapter.

Douyin's web search is a heavy SPA and its public API requires signed requests
(X-Bogus, _signature). A robust implementation either drives a headless browser
or uses a paid scraping service. For the PoC we attempt the JSON discovery
endpoint and gracefully return [] when it fails so the pipeline can fall back.
"""

import json
from urllib.parse import quote_plus

from ..models import ProductQuery, SearchCandidate
from .base import SearchAdapter


class DouyinAdapter(SearchAdapter):
    name = "douyin"
    # General search page; we extract the SSR JSON when available.
    SEARCH_URL = "https://www.douyin.com/search/{q}?type=video"

    async def search(self, query: ProductQuery, *, limit: int = 8) -> list[SearchCandidate]:
        q = query.primary_query("zh") or query.primary_query("en")
        if not q:
            return []
        url = self.SEARCH_URL.format(q=quote_plus(q))
        try:
            resp = await self._client.get(url, headers={"Referer": "https://www.douyin.com/"})
        except Exception:
            return []
        if resp.status_code != 200:
            return []

        items = self._extract_video_items(resp.text)
        out: list[SearchCandidate] = []
        for it in items[:limit]:
            aweme_id = str(it.get("aweme_id") or it.get("awemeId") or "")
            if not aweme_id:
                continue
            title = (it.get("desc") or "").strip()
            cover = ""
            video = it.get("video") or {}
            cover_obj = video.get("cover") or video.get("origin_cover") or {}
            url_list = cover_obj.get("url_list") if isinstance(cover_obj, dict) else None
            if isinstance(url_list, list) and url_list:
                cover = url_list[0]
            page_url = f"https://www.douyin.com/video/{aweme_id}"
            out.append(
                SearchCandidate(
                    platform="douyin",
                    title=title,
                    product_url=page_url,
                    thumbnail_url=cover or None,
                    # yt-dlp can resolve and download from the page URL.
                    video_url=page_url,
                )
            )
        return out

    @staticmethod
    def _extract_video_items(html: str) -> list[dict]:
        # Douyin SSRs a RENDER_DATA blob (URL-encoded JSON) into a script tag.
        # When present, video items live under several keys depending on the
        # search vertical. We search broadly for aweme objects.
        marker = '"aweme_list"'
        idx = html.find(marker)
        if idx == -1:
            marker = '"awemeList"'
            idx = html.find(marker)
            if idx == -1:
                return []
        # Walk forward to the array opening and parse with a depth counter.
        start = html.find("[", idx)
        if start == -1:
            return []
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(html)):
            ch = html[i]
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[start : i + 1])
                    except json.JSONDecodeError:
                        return []
        return []
