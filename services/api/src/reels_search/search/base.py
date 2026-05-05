from abc import ABC, abstractmethod

import httpx

from ..models import ProductQuery, SearchCandidate

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ko;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class SearchAdapter(ABC):
    """Adapter for one search backend (Taobao, 1688, Douyin, SerpAPI...).

    Implementations should return a list of SearchCandidate. They MAY pre-fill
    `video_url` if the search response includes it; otherwise the downloader
    will visit `product_url` and try to extract a video.
    """

    name: str = "base"

    def __init__(self, *, cookie: str = "", timeout: float = 15.0) -> None:
        self.cookie = cookie
        headers = dict(DEFAULT_HEADERS)
        if cookie:
            headers["Cookie"] = cookie
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            http2=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "SearchAdapter":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    @abstractmethod
    async def search(self, query: ProductQuery, *, limit: int = 8) -> list[SearchCandidate]:
        ...
