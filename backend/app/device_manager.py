from typing import Any
from . import config as cfg
from .panda_client import panda
from .adb_client import AdbClient
from . import vision
from .logger import log_bus

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

    async def tap_image(self, device_id: str, template_path: str, threshold: float = 0.8) -> bool:
        client = self.client
        screen_bytes = await self.screenshot_raw(device_id)
        if not screen_bytes:
            await log_bus.error("Gagal mengambil screenshot untuk tap_image")
            return False
            
        match = vision.find_image_on_screen(screen_bytes, template_path, threshold)
        if match and match["confidence"] >= threshold:
            cx, cy = match["center_pct"]
            conf = match["confidence"]
            await log_bus.info(f"Gambar {template_path} ditemukan dengan confidence {conf:.2f} di ({cx}%, {cy}%)")
            await self.tap(device_id, cx, cy)
            return True
        else:
            actual_conf = match["confidence"] if match else 0.0
            await log_bus.error(f"Gambar {template_path} tidak mencapai threshold {threshold} (Cuma dapat: {actual_conf:.2f})")
            return False

    async def tap_color_orange_button(self, device_id: str) -> bool:
        screen_bytes = await self.screenshot_raw(device_id)
        if not screen_bytes: return False
        match = vision.find_orange_button_color(screen_bytes)
        if match:
            cx, cy = match["center"]
            await log_bus.info(f"Tombol oranye ditemukan di ({cx}, {cy}), menekan tombol...")
            await self.tap(device_id, cx, cy)
            return True
        return False

    async def tap_text(self, devices: str, text: str, timeout: int = 3, tap_right_edge: bool = False, tap_x_offset: int = 0, tap_y_offset: int = 0, tap_below: bool = False, suppress_error: bool = False) -> bool:
        if hasattr(self.client, "tap_text"):
            return await self.client.tap_text(devices, text, timeout=timeout, tap_right_edge=tap_right_edge, tap_x_offset=tap_x_offset, tap_y_offset=tap_y_offset, tap_below=tap_below, suppress_error=suppress_error)
        return False

    async def check_text_exists(self, devices: str, text: str) -> bool:
        if hasattr(self.client, "check_text_exists"):
            return await self.client.check_text_exists(devices, text)
        return False

    async def read_text_by_regex(self, devices: str, pattern: str, timeout: int = 5) -> dict | None:
        if hasattr(self.client, "read_text_by_regex"):
            return await self.client.read_text_by_regex(devices, pattern, timeout=timeout)
        return None

    async def read_all_text_by_regex(self, devices: str, pattern: str, timeout: int = 5) -> list[dict]:
        if hasattr(self.client, "read_all_text_by_regex"):
            return await self.client.read_all_text_by_regex(devices, pattern, timeout=timeout)
        return []

    async def swipe(self, devices: str, x1: str | float, y1: str | float, x2: str | float, y2: str | float, duration_ms: int = 500, *, dry_run: bool = False) -> dict[str, Any]:
        if hasattr(self.client, "swipe"):
            return await self.client.swipe(devices, x1, y1, x2, y2, duration_ms=duration_ms, dry_run=dry_run)
        else:
            return {"code": 10001, "message": "Swipe not implemented for this client", "data": None}

    async def start_apk(self, devices: str, apk: str, *, dry_run: bool = False) -> dict[str, Any]:
        return await self.client.start_apk(devices, apk, dry_run=dry_run)

    async def push_event(self, devices: str, type_code: str | int, *, dry_run: bool = False) -> dict[str, Any]:
        return await self.client.push_event(devices, type_code, dry_run=dry_run)

    async def input_text(self, devices: str, content: str, *, dry_run: bool = False) -> dict[str, Any]:
        return await self.client.input_text(devices, content, dry_run=dry_run)

    async def screenshot_raw(self, device: str) -> bytes:
        mode = cfg.load_settings().get("connection_mode", "adb")
        if mode == "adb":
            return await adb_client.screenshot_raw(device)
        else:
            raise NotImplementedError("Live screen capture over WebSocket (Panda) is not currently supported in this API. Please use ADB mode for live calibration.")

device_manager = DeviceManager()
