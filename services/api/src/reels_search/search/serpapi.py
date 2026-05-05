"""SerpAPI fallback adapter.

When direct platform scraping fails (cookies missing, anti-bot), SerpAPI gives
us a reliable text-search path. We use Google search restricted to taobao /
1688 / douyin / aliexpress domains, which usually yields product detail pages
the downloader can then visit to extract a video.
"""

from typing import Any

from ..config import settings
from ..models import ProductQuery, SearchCandidate
from .base import SearchAdapter


_DOMAINS = (
    "site:item.taobao.com OR "
    "site:detail.tmall.com OR "
    "site:detail.1688.com OR "
    "site:douyin.com OR "
    "site:aliexpress.com"
)


class SerpApiAdapter(SearchAdapter):
    name = "serpapi"
    BASE = "https://serpapi.com/search.json"

    async def search(self, query: ProductQuery, *, limit: int = 8) -> list[SearchCandidate]:
        if not settings.serpapi_key:
            return []
        q = query.primary_query("zh") or query.primary_query("en")
        if not q:
            return []
        params: dict[str, Any] = {
            "engine": "google",
            "q": f"{q} {_DOMAINS}",
            "num": str(min(limit, 10)),
            "hl": "zh-CN",
            "api_key": settings.serpapi_key,
        }
        try:
            resp = await self._client.get(self.BASE, params=params)
        except Exception:
            return []
        if resp.status_code != 200:
            return []

        data = resp.json()
        organic = data.get("organic_results") or []
        out: list[SearchCandidate] = []
        for r in organic[:limit]:
            link = r.get("link") or ""
            title = r.get("title") or ""
            thumb = r.get("thumbnail")
            if not link:
                continue
            out.append(
                SearchCandidate(
                    platform=_platform_for(link),
                    title=title,
                    product_url=link,
                    thumbnail_url=thumb,
                )
            )
        return out


def _platform_for(url: str) -> Any:
    if "taobao.com" in url or "tmall.com" in url:
        return "taobao"
    if "1688.com" in url:
        return "alibaba1688"
    if "douyin.com" in url:
        return "douyin"
    return "serpapi"
