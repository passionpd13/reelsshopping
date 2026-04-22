"""In-process SSE event broker.

Simple pub/sub for progress updates (pipeline stages, job status).
Replace with Redis pub/sub when scaling beyond a single worker.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from time import time
from typing import Any


@dataclass
class Event:
    topic: str
    type: str
    payload: dict[str, Any]
    ts: float

    def to_sse(self) -> str:
        data = json.dumps({"type": self.type, "payload": self.payload, "ts": self.ts})
        return f"event: {self.type}\ndata: {data}\n\n"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = defaultdict(set)

    async def publish(self, topic: str, type_: str, payload: dict[str, Any]) -> None:
        evt = Event(topic=topic, type=type_, payload=payload, ts=time())
        for q in list(self._subscribers.get(topic, ())):
            await q.put(evt)

    async def subscribe(self, topic: str) -> AsyncIterator[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=100)
        self._subscribers[topic].add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers[topic].discard(q)


bus = EventBus()
