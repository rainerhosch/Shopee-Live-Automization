from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any


class LogBus:
    """In-memory ring buffer + fan-out to dashboard WebSocket clients."""

    def __init__(self, maxlen: int = 500) -> None:
        self._logs: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    def history(self, limit: int = 200) -> list[dict[str, Any]]:
        items = list(self._logs)
        return items[-limit:]

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(q)

    async def emit(
        self,
        level: str,
        message: str,
        **extra: Any,
    ) -> dict[str, Any]:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            **extra,
        }
        self._logs.append(entry)
        async with self._lock:
            dead: list[asyncio.Queue] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(entry)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        q.put_nowait(entry)
                    except asyncio.QueueFull:
                        dead.append(q)
            for q in dead:
                self._subscribers.discard(q)
        return entry

    async def info(self, message: str, **extra: Any) -> dict[str, Any]:
        return await self.emit("info", message, **extra)

    async def warn(self, message: str, **extra: Any) -> dict[str, Any]:
        return await self.emit("warn", message, **extra)

    async def error(self, message: str, **extra: Any) -> dict[str, Any]:
        return await self.emit("error", message, **extra)

    async def debug(self, message: str, **extra: Any) -> dict[str, Any]:
        return await self.emit("debug", message, **extra)


log_bus = LogBus()
