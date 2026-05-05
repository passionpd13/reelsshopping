"""1688 (alibaba.com B2B Chinese) search adapter.

1688's offer search page is more permissive than Taobao for unauthenticated
HTML, but JSON layout drifts. We parse defensively and skip malformed entries.
"""

import json
import re
from urllib.parse import quote_plus

from ..models import ProductQuery, SearchCandidate
from .base import SearchAdapter


_DATA_RE = re.compile(r'window\._INIT_DATA_\s*=\s*(\{.*?\});', re.DOTALL)


class Alibaba1688Adapter(SearchAdapter):
    name = "alibaba1688"
    BASE = "https://s.1688.com/selloffer/offer_search.htm"

    async def search(self, query: ProductQuery, *, limit: int = 8) -> list[SearchCandidate]:
        q = query.primary_query("zh") or query.primary_query("en")
        if not q:
            return []
        url = f"{self.BASE}?keywords={quote_plus(q)}"
        try:
            resp = await self._client.get(url, headers={"Referer": "https://www.1688.com/"})
        except Exception:
            return []
        if resp.status_code != 200:
            return []

        items = self._extract_items(resp.text)
        out: list[SearchCandidate] = []
        for it in items[:limit]:
            offer_id = str(it.get("id") or it.get("offerId") or "")
            title = it.get("subject") or it.get("title") or ""
            pic = it.get("image") or it.get("imgUrl") or ""
            detail = it.get("detailUrl") or (
                f"https://detail.1688.com/offer/{offer_id}.html" if offer_id else ""
            )
            if not detail:
                continue
            if detail.startswith("//"):
                detail = "https:" + detail
            if isinstance(pic, str) and pic.startswith("//"):
                pic = "https:" + pic
            out.append(
                SearchCandidate(
                    platform="alibaba1688",
                    title=title,
                    product_url=detail,
                    thumbnail_url=pic or None,
                )
            )
        return out

    @staticmethod
    def _extract_items(html: str) -> list[dict]:
        m = _DATA_RE.search(html)
        if not m:
            return []
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            return []
        # Layout drifts; walk known shapes.
        for path in (
            ("data", "offerList"),
            ("data", "offerResult", "offerList"),
            ("offerList",),
        ):
            cur: object = data
            for key in path:
                if isinstance(cur, dict) and key in cur:
                    cur = cur[key]
                else:
                    cur = None
                    break
            if isinstance(cur, list) and cur:
                return cur
        return []
