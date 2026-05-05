"""Taobao search adapter.

Reality check: Taobao's web search aggressively gates non-logged-in traffic.
Without a valid `TAOBAO_COOKIE`, search responses often degrade to login walls
or empty result sets. The adapter still returns whatever it can parse, and the
pipeline falls back to other platforms / SerpAPI when results are thin.
"""

import json
import re
from urllib.parse import quote_plus

from ..models import ProductQuery, SearchCandidate
from .base import SearchAdapter


_PAGE_CONFIG_RE = re.compile(r"g_page_config\s*=\s*(\{.*?\});\s*g_srp_loadCss", re.DOTALL)


class TaobaoAdapter(SearchAdapter):
    name = "taobao"
    BASE = "https://s.taobao.com/search"

    async def search(self, query: ProductQuery, *, limit: int = 8) -> list[SearchCandidate]:
        q = query.primary_query("zh") or query.primary_query("en")
        if not q:
            return []
        url = f"{self.BASE}?q={quote_plus(q)}&commend=all&search_type=item"
        try:
            resp = await self._client.get(url, headers={"Referer": "https://www.taobao.com/"})
        except Exception:
            return []
        if resp.status_code != 200:
            return []

        items = self._parse_page_config(resp.text)
        out: list[SearchCandidate] = []
        for it in items[:limit]:
            title = it.get("raw_title") or it.get("title") or ""
            nid = it.get("nid") or it.get("itemId") or ""
            pic = it.get("pic_url") or it.get("pic") or ""
            detail = it.get("detail_url") or (
                f"https://item.taobao.com/item.htm?id={nid}" if nid else ""
            )
            if not detail:
                continue
            if detail.startswith("//"):
                detail = "https:" + detail
            if pic.startswith("//"):
                pic = "https:" + pic
            out.append(
                SearchCandidate(
                    platform="taobao",
                    title=title,
                    product_url=detail,
                    thumbnail_url=pic or None,
                )
            )
        return out

    @staticmethod
    def _parse_page_config(html: str) -> list[dict]:
        m = _PAGE_CONFIG_RE.search(html)
        if not m:
            return []
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            return []
        try:
            return data["mods"]["itemlist"]["data"]["auctions"] or []
        except (KeyError, TypeError):
            return []
