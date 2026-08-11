from typing import Any
from . import config as cfg
from .panda_client import panda
from .adb_client import AdbClient

adb_client = AdbClient()

class DeviceManager:
    """Wrapper to route commands to the active client (Panda or ADB) based on settings."""

    @property
    def client(self):
        mode = cfg.load_settings().get("connection_mode", "adb")
        if mode == "panda":
            return panda
        return adb_client

    @property
    def connected(self):
        return self.client.connected

    async def connect(self) -> None:
        await self.client.connect()

    async def close(self) -> None:
        await self.client.close()

    async def ensure(self) -> None:
        await self.client.ensure()

    async def list_devices(self) -> dict[str, Any]:
        return await self.client.list_devices()

    async def tap(self, devices: str, x: str | float, y: str | float, *, settle_ms: int = 80, dry_run: bool = False) -> dict[str, Any]:
        return await self.client.tap(devices, x, y, settle_ms=settle_ms, dry_run=dry_run)

    async def start_apk(self, devices: str, apk: str, *, dry_run: bool = False) -> dict[str, Any]:
        return await self.client.start_apk(devices, apk, dry_run=dry_run)

    async def push_event(self, devices: str, type_code: str | int, *, dry_run: bool = False) -> dict[str, Any]:
        return await self.client.push_event(devices, type_code, dry_run=dry_run)

    async def input_text(self, devices: str, content: str, *, dry_run: bool = False) -> dict[str, Any]:
        return await self.client.input_text(devices, content, dry_run=dry_run)

device_manager = DeviceManager()
