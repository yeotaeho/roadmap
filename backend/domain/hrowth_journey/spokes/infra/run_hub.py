# 생성 런 인프로세스 브로드캐스트 허브 — user_id 별 SSE 구독 큐 팬아웃
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

_QUEUE_MAX = 200


class RunHub:
    """user_id → 구독 큐 집합. 프로세스 로컬(진실원본은 DB progress)."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, user_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._subs.setdefault(user_id, set()).add(q)
        return q

    def unsubscribe(self, user_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(user_id)
        if subs is not None:
            subs.discard(q)
            if not subs:
                self._subs.pop(user_id, None)

    def publish(self, user_id: str, event: dict) -> None:
        for q in self._subs.get(user_id, ()):  # 구독자 없으면 무동작.
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # 느린 구독자는 이벤트를 잃는다 — DB 스냅샷이 보정.
                logger.warning("RunHub 큐 가득 참 — 이벤트 드롭")


run_hub = RunHub()
