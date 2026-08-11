from __future__ import annotations

import asyncio
import json
from typing import Any

from .logger import log_bus

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore
    ConnectionClosed = Exception  # type: ignore


class PandaClient:
    """Async WebSocket client for Panda screen-projection API."""

    def __init__(self, url: str = "ws://127.0.0.1:22222/") -> None:
        self.url = url
        self._ws: Any = None
        self._lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self.connected = False

    async def connect(self) -> None:
        if websockets is None:
            raise RuntimeError("websockets package not installed. Run: pip install websockets")
        async with self._connect_lock:
            if self._ws is not None and self.connected:
                return
            try:
                self._ws = await websockets.connect(self.url, open_timeout=5, close_timeout=2)
                self.connected = True
                await log_bus.info(f"Panda connected: {self.url}")
            except Exception as exc:
                self.connected = False
                self._ws = None
                await log_bus.error(f"Panda connect failed: {exc}")
                raise

    async def close(self) -> None:
        async with self._connect_lock:
            if self._ws is not None:
                try:
                    await self._ws.close()
                except Exception:
                    pass
            self._ws = None
            self.connected = False

    async def ensure(self) -> None:
        if not self.connected or self._ws is None:
            await self.connect()

    async def send(self, payload: dict[str, Any], timeout: float = 12.0) -> dict[str, Any]:
        async with self._lock:
            await self.ensure()
            assert self._ws is not None
            raw = json.dumps(payload, ensure_ascii=False)
            try:
                await self._ws.send(raw)
                resp_raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
            except ConnectionClosed as exc:
                self.connected = False
                self._ws = None
                await log_bus.warn(f"Panda connection closed: {exc}; retrying once")
                await self.connect()
                assert self._ws is not None
                await self._ws.send(raw)
                resp_raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
            except Exception:
                self.connected = False
                self._ws = None
                raise

            try:
                resp = json.loads(resp_raw)
            except json.JSONDecodeError:
                resp = {"code": 10001, "message": f"Non-JSON response: {resp_raw!r}", "data": None}

            await log_bus.debug(
                f"Panda {payload.get('action')} → {resp.get('code')} {resp.get('message')}",
                request=payload,
                response=resp,
            )
            return resp

    async def list_devices(self) -> dict[str, Any]:
        return await self.send({"action": "list"})

    async def tap(
        self,
        devices: str,
        x: str | float,
        y: str | float,
        *,
        settle_ms: int = 80,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        xs, ys = str(x), str(y)
        if dry_run:
            await log_bus.info(f"[dry-run] tap devices={devices} x={xs} y={ys}")
            return {"code": 10000, "message": "DRY_RUN", "data": {"x": xs, "y": ys}}

        r0 = await self.send(
            {"action": "pointerEvent", "devices": devices, "data": {"type": "0", "x": xs, "y": ys}}
        )
        if r0.get("code") != 10000:
            raise RuntimeError(f"press failed: {r0}")
        if settle_ms:
            await asyncio.sleep(settle_ms / 1000)
        r1 = await self.send(
            {"action": "pointerEvent", "devices": devices, "data": {"type": "1", "x": xs, "y": ys}}
        )
        if r1.get("code") != 10000:
            raise RuntimeError(f"lift failed: {r1}")
        return r1

    async def push_event(self, devices: str, type_code: str | int, *, dry_run: bool = False) -> dict[str, Any]:
        payload = {
            "action": "pushEvent",
            "devices": devices,
            "data": {"type": str(type_code)},
        }
        if dry_run:
            await log_bus.info(f"[dry-run] pushEvent {payload}")
            return {"code": 10000, "message": "DRY_RUN", "data": None}
        return await self.send(payload)

    async def start_apk(self, devices: str, apk: str, *, dry_run: bool = False) -> dict[str, Any]:
        payload = {"action": "startApk", "devices": devices, "data": {"apk": apk}}
        if dry_run:
            await log_bus.info(f"[dry-run] startApk {apk} on {devices}")
            return {"code": 10000, "message": "DRY_RUN", "data": None}
        return await self.send(payload)

    async def input_text(self, devices: str, content: str, *, dry_run: bool = False) -> dict[str, Any]:
        payload = {"action": "inputText", "devices": devices, "data": {"content": content}}
        if dry_run:
            await log_bus.info(f"[dry-run] inputText {content!r}")
            return {"code": 10000, "message": "DRY_RUN", "data": None}
        return await self.send(payload)

    async def screenshot(self, devices: str, save_path: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if save_path:
            data["savePath"] = save_path
        return await self.send({"action": "Screen", "devices": devices, "data": data})


# Shared singleton; URL updated from settings at startup
panda = PandaClient()
