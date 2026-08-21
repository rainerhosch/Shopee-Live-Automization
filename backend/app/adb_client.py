import asyncio
import os
import re
import subprocess
from typing import Any
from .logger import log_bus
from . import config as cfg

class AdbClient:
    def __init__(self) -> None:
        self.connected = False
        self._screen_sizes: dict[str, tuple[int, int]] = {}

    def get_adb_path(self) -> str:
        settings = cfg.load_settings()
        path = settings.get("adb_path") or "adb"
        if path == "adb":
            # Auto-detect localappdata if available on Windows
            localappdata = os.environ.get("LOCALAPPDATA")
            if localappdata:
                auto_path = os.path.join(localappdata, "Android", "Sdk", "platform-tools", "adb.exe")
                if os.path.exists(auto_path):
                    return auto_path
        return path

    async def _run_adb(self, *args: str) -> tuple[int, str, str]:
        code, stdout, stderr = await self._run_adb_bytes(*args)
        return code, stdout.decode(errors='replace').strip(), stderr.decode(errors='replace').strip()

    async def _run_adb_bytes(self, *args: str) -> tuple[int, bytes, bytes]:
        cmd = [self.get_adb_path(), *args]
        
        kwargs = {}
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **kwargs
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode or 0, stdout, stderr

    async def connect(self) -> None:
        code, out, err = await self._run_adb("start-server")
        if code != 0:
            raise RuntimeError(f"Failed to start ADB server: {err}")
        self.connected = True
        await log_bus.info(f"\nADB connected using {self.get_adb_path()}")

    async def close(self) -> None:
        self.connected = False
        # Do not kill adb server as other apps might use it
        self._screen_sizes.clear()

    async def screencap(self) -> bytes:
        from .vision import get_screen_bytes
        bytes_data = await get_screen_bytes(self)
        if not bytes_data:
            raise RuntimeError("Failed to get screencap")
        return bytes_data

    async def tap_text(self, devices: str, text: str, timeout: int = 5, tap_right_edge: bool = False) -> bool:
        """
        Mencari teks di layar (menggunakan UI Automator) dan melakukan tap jika ditemukan.
        """
        from .vision import dump_ui, find_node_by_text
        from .logger import log_bus
        import time
        
        await log_bus.info(f"🔍 Mencari tombol '{text}' di layar...")
        start = time.time()
        while time.time() - start < timeout:
            root = await dump_ui(self, devices)
            node = find_node_by_text(root, text)
            if node:
                cx, cy = node['center']
                if tap_right_edge:
                    try:
                        bounds_str = root.attrib.get('bounds', '[0,0][1080,2400]')
                        screen_width = int(bounds_str.replace('][', ',').replace('[', '').replace(']', '').split(',')[2])
                        cx = int(screen_width * 0.85)
                    except:
                        cx = cx + 300  # Fallback offset
                await log_bus.info(f"🎯 Ditemukan '{text}' di baris {cy}, tap di ({cx}, {cy})")
                await self.tap(devices, cx, cy)
                return True
            await asyncio.sleep(1)
            
        await log_bus.error(f"❌ Teks '{text}' tidak ditemukan setelah {timeout} detik.")
        return False

    async def read_text_by_regex(self, devices: str, pattern: str, timeout: int = 5) -> dict | None:
        """
        Mencari node berdasarkan regex dan mengembalikan data node (termasuk text dan center).
        """
        from .vision import dump_ui, find_node_by_regex
        from .logger import log_bus
        import time
        
        await log_bus.info(f"🔍 Mencari pola regex '{pattern}' di layar...")
        start = time.time()
        while time.time() - start < timeout:
            root = await dump_ui(self, devices)
            node = find_node_by_regex(root, pattern)
            if node:
                await log_bus.info(f"🎯 Ditemukan cocok dengan regex '{pattern}': '{node['text']}'")
                return node
            await asyncio.sleep(1)
            
        await log_bus.error(f"❌ Pola regex '{pattern}' tidak ditemukan setelah {timeout} detik.")
        return None
        
    async def read_all_text_by_regex(self, devices: str, pattern: str, timeout: int = 5) -> list[dict]:
        from .vision import dump_ui, find_all_nodes_by_regex
        await log_bus.info(f"🔍 Mencari semua pola regex '{pattern}' di layar...")
        end_time = asyncio.get_event_loop().time() + timeout
        
        while asyncio.get_event_loop().time() < end_time:
            root = await dump_ui(self, devices)
            nodes = find_all_nodes_by_regex(root, pattern)
            if nodes:
                await log_bus.info(f"🎯 Ditemukan {len(nodes)} node cocok dengan regex '{pattern}'")
                return nodes
            await asyncio.sleep(1)
            
        await log_bus.error(f"❌ Pola regex '{pattern}' tidak ditemukan setelah {timeout} detik.")
        return []

    async def check_text_exists(self, devices: str, text: str) -> bool:
        """
        Mengecek apakah suatu teks ada di layar tanpa melakukan tap (single check).
        """
        from .vision import dump_ui, find_node_by_text
        root = await dump_ui(self, devices)
        return find_node_by_text(root, text) is not None


    async def ensure(self) -> None:
        if not self.connected:
            await self.connect()

    async def list_devices(self) -> dict[str, Any]:
        await self.ensure()
        code, out, err = await self._run_adb("devices")
        if code != 0:
            return {"code": 10001, "message": err, "data": []}
        
        devices = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append({"serial": parts[0], "status": "device"})
        return {"code": 10000, "message": "OK", "data": devices}

    async def _get_screen_size(self, device: str) -> tuple[int, int]:
        if device in self._screen_sizes:
            return self._screen_sizes[device]
        code, out, err = await self._run_adb("-s", device, "shell", "wm", "size")
        if code != 0:
            raise RuntimeError(f"Cannot get screen size for {device}: {err}")
        # Output looks like: Physical size: 1080x2400
        m = re.search(r"(\d+)x(\d+)", out)
        if not m:
            raise RuntimeError(f"Unrecognized wm size output: {out}")
        size = (int(m.group(1)), int(m.group(2)))
        self._screen_sizes[device] = size
        return size

    async def tap(
        self,
        devices: str,
        x: str | float,
        y: str | float,
        *,
        settle_ms: int = 80,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            await log_bus.info(f"[dry-run] ADB tap device={devices} x={x} y={y}")
            return {"code": 10000, "message": "DRY_RUN", "data": {"x": x, "y": y}}
        
        fx, fy = float(x), float(y)
        # Convert percentages to absolute pixels if values are small (<=100) and have decimals 
        # (Based on user request: coordinate format for Panda is percentage, ADB needs pixels)
        if 0 < fx <= 100 and 0 < fy <= 100 and (isinstance(x, str) and '.' in x or isinstance(y, str) and '.' in y):
            width, height = await self._get_screen_size(devices)
            fx = (fx / 100.0) * width
            fy = (fy / 100.0) * height

        ix, iy = int(fx), int(fy)
        code, out, err = await self._run_adb("-s", devices, "shell", "input", "tap", str(ix), str(iy))
        if code != 0:
            raise RuntimeError(f"ADB tap failed: {err}")
        if settle_ms:
            await asyncio.sleep(settle_ms / 1000)
        return {"code": 10000, "message": "OK", "data": {"x": ix, "y": iy}}

    async def start_apk(self, devices: str, apk: str, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            await log_bus.info(f"[dry-run] ADB startApk {apk} on {devices}")
            return {"code": 10000, "message": "DRY_RUN", "data": None}
        code, out, err = await self._run_adb("-s", devices, "shell", "monkey", "-p", apk, "-c", "android.intent.category.LAUNCHER", "1")
        if code != 0:
            return {"code": 10001, "message": err, "data": None}
        return {"code": 10000, "message": "OK", "data": None}

    async def swipe(
        self,
        devices: str,
        x1: str | float,
        y1: str | float,
        x2: str | float,
        y2: str | float,
        duration_ms: int = 500,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            await log_bus.info(f"[dry-run] ADB swipe device={devices} {x1},{y1} -> {x2},{y2} duration={duration_ms}")
            return {"code": 10000, "message": "DRY_RUN", "data": None}
        
        fx1, fy1, fx2, fy2 = float(x1), float(y1), float(x2), float(y2)
        if (0 < fx1 <= 100 and 0 < fy1 <= 100) or (0 < fx2 <= 100 and 0 < fy2 <= 100):
            width, height = await self._get_screen_size(devices)
            if 0 < fx1 <= 100: fx1 = (fx1 / 100.0) * width
            if 0 < fy1 <= 100: fy1 = (fy1 / 100.0) * height
            if 0 < fx2 <= 100: fx2 = (fx2 / 100.0) * width
            if 0 < fy2 <= 100: fy2 = (fy2 / 100.0) * height

        code, out, err = await self._run_adb("-s", devices, "shell", "input", "swipe", str(int(fx1)), str(int(fy1)), str(int(fx2)), str(int(fy2)), str(duration_ms))
        if code != 0:
            return {"code": 10001, "message": err, "data": None}
        return {"code": 10000, "message": "OK", "data": None}

    async def screenshot(self, device: str, save_path: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {}
        # Scrcpy replacement logic isn't here, this is generic. We use screenshot_raw for live preview.
        # But for API compatibility:
        code, out, err = await self._run_adb("-s", device, "exec-out", "screencap", "-p")
        if code != 0:
            return {"code": 10001, "message": err, "data": None}
        return {"code": 10000, "message": "OK", "data": data}

    async def screenshot_raw(self, device: str = None) -> bytes:
        await self.ensure()
        args = ["exec-out", "screencap", "-p"]
        if device:
            args = ["-s", device] + args
        code, stdout, stderr = await self._run_adb_bytes(*args)
        if code != 0:
            raise RuntimeError(f"screencap failed: {stderr.decode(errors='replace')}")
        return stdout

    async def push_event(self, devices: str, type_code: str | int, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            await log_bus.info(f"[dry-run] ADB pushEvent {type_code}")
            return {"code": 10000, "message": "DRY_RUN", "data": None}
        code, out, err = await self._run_adb("-s", devices, "shell", "input", "keyevent", str(type_code))
        if code != 0:
            return {"code": 10001, "message": err, "data": None}
        return {"code": 10000, "message": "OK", "data": None}

    async def input_text(self, devices: str, content: str, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            await log_bus.info(f"[dry-run] ADB inputText {content!r}")
            return {"code": 10000, "message": "DRY_RUN", "data": None}
        code, out, err = await self._run_adb("-s", devices, "shell", "input", "text", f'"{content}"')
        if code != 0:
            return {"code": 10001, "message": err, "data": None}
        return {"code": 10000, "message": "OK", "data": None}
