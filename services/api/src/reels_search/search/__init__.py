from .alibaba1688 import Alibaba1688Adapter
from .base import SearchAdapter
from .douyin import DouyinAdapter
from .serpapi import SerpApiAdapter
from .taobao import TaobaoAdapter

ADAPTERS: dict[str, type[SearchAdapter]] = {
    "taobao": TaobaoAdapter,
    "alibaba1688": Alibaba1688Adapter,
    "douyin": DouyinAdapter,
    "serpapi": SerpApiAdapter,
}

__all__ = [
    "ADAPTERS",
    "SearchAdapter",
    "TaobaoAdapter",
    "Alibaba1688Adapter",
    "DouyinAdapter",
    "SerpApiAdapter",
]
