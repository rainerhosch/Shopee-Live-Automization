from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config as cfg
from .logger import log_bus
from .models import (
    BotControl,
    CalibratePoint,
    ProfileMetaUpdate,
    RunOnceRequest,
    SettingsUpdate,
    TapRequest,
    TaskCreate,
    TaskUpdate,
)
from .paths import ASSETS_DIR, STATIC_DIR
from .device_manager import device_manager
from .scheduler import bot


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = bot.reload_settings()
    await log_bus.info("Shopee Live Bot backend started")
    # Best-effort connect; dashboard still works offline
    try:
        await device_manager.connect()
    except Exception as exc:
        await log_bus.warn(f"Client not available at startup: {exc}")
    yield
    await bot.stop()
    await device_manager.close()
    await log_bus.info("Backend shutdown")


app = FastAPI(title="Shopee Live Bot", version="0.1.0", lifespan=lifespan)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@app.get("/")
async def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(500, "Dashboard not found (backend/static/index.html)")
    return FileResponse(index_path)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "panda_connected": device_manager.connected,
        "bot_status": bot.status,
    }


@app.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    return cfg.load_settings()


@app.put("/api/settings")
async def put_settings(body: SettingsUpdate) -> dict[str, Any]:
    data = body.model_dump(exclude_none=True)
    saved = cfg.save_settings(data)
    bot.reload_settings()
    if "connection_mode" in data or "panda_url" in data or "adb_path" in data:
        await device_manager.close()
        try:
            await device_manager.connect()
        except Exception as exc:
            await log_bus.warn(f"Reconnect after settings change failed: {exc}")
    await log_bus.info("Settings updated", settings=saved)
    return saved


@app.get("/api/devices")
async def devices() -> dict[str, Any]:
    try:
        resp = await device_manager.list_devices()
    except Exception as exc:
        raise HTTPException(503, f"Client unavailable: {exc}") from exc
    raw = resp.get("data")
    device_list = raw if isinstance(raw, list) else []
    # Surface common Panda/ADB license / param errors for the dashboard
    message = resp.get("message") or ""
    hint = None
    if resp.get("code") != 10000:
        if "会员" in str(message) or "member" in str(message).lower():
            hint = (
                "Panda API requires an activated membership (会员). "
                "Socket connects, but list/control commands are blocked until licensed."
            )
        else:
            hint = f"Client returned code {resp.get('code')}: {message}"
    return {
        "panda_connected": device_manager.connected,
        "code": resp.get("code"),
        "message": message,
        "hint": hint,
        "devices": device_list,
    }


@app.post("/api/panda/reconnect")
async def panda_reconnect() -> dict[str, Any]:
    await device_manager.close()
    try:
        await device_manager.connect()
        return {"ok": True, "connected": True}
    except Exception as exc:
        return {"ok": False, "connected": False, "error": str(exc)}


@app.get("/api/bot")
async def bot_status() -> dict[str, Any]:
    return bot.snapshot()


@app.post("/api/bot/control")
async def bot_control(body: BotControl) -> dict[str, Any]:
    try:
        if body.action == "start":
            return await bot.start(device=body.device, profile=body.profile, dry_run=body.dry_run)
        if body.action == "pause":
            return await bot.pause()
        if body.action == "stop":
            return await bot.stop()
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    raise HTTPException(400, "Unknown action")


@app.get("/api/tasks")
async def list_tasks() -> list[dict[str, Any]]:
    return list(bot.tasks.values())


async def screen_streamer(device: str = None):
    """Generator for MJPEG stream from device screenshot."""
    while True:
        try:
            frame = await device_manager.screenshot_raw(device)
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')
            else:
                await asyncio.sleep(0.5)
        except Exception as exc:
            import traceback
            err = traceback.format_exc()
            await log_bus.error(f"Stream exception: {exc}\n{err}")
            await asyncio.sleep(1)
        await asyncio.sleep(0.2)

@app.get("/api/stream")
async def mjpeg_stream(device: str = None):
    return StreamingResponse(screen_streamer(device), media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/api/scrcpy")
async def launch_scrcpy(device: str = None):
    """Launch native scrcpy window for the device."""
    import subprocess
    cmd = ["C:\\scrcpy\\scrcpy.exe"]
    if device:
        cmd.extend(["-s", device])
    
    try:
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NO_WINDOW)
        return {"ok": True, "message": "Scrcpy launched"}
    except Exception as exc:
        raise HTTPException(500, f"Failed to launch scrcpy: {exc}")


@app.delete("/api/queue")
async def clear_queue() -> dict[str, Any]:
    bot.queue.clear()
    return bot.snapshot()


@app.delete("/api/queue/{task_id}")
async def remove_from_queue(task_id: str) -> dict[str, Any]:
    bot.queue = [t for t in bot.queue if t["id"] != task_id]
    return bot.snapshot()


@app.get("/api/screen")
async def get_screen(device: str):
    try:
        image_bytes = await device_manager.screenshot_raw(device)
        return Response(content=image_bytes, media_type="image/png")
    except NotImplementedError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Screenshot failed: {exc}")


@app.post("/api/tasks")
async def create_task(body: TaskCreate) -> dict[str, Any]:
    task = bot.add_task(body.type, body.interval_sec, body.params, body.enabled)
    await log_bus.info(f"Task created {task['id']} type={task['type']}", task=task)
    return task


@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: str, body: TaskUpdate) -> dict[str, Any]:
    try:
        task = bot.update_task(task_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(404, "Task not found") from exc
    return task


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str) -> dict[str, Any]:
    bot.remove_task(task_id)
    return {"ok": True}


@app.delete("/api/tasks")
async def clear_tasks() -> dict[str, Any]:
    bot.clear_tasks()
    return {"ok": True}


@app.post("/api/tasks/run-once")
async def run_once(body: RunOnceRequest) -> dict[str, Any]:
    try:
        results = await bot.run_once(
            body.type,
            body.params,
            device=body.device,
            profile=body.profile,
            dry_run=body.dry_run,
        )
        return {"ok": True, "results": results}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/logs")
async def get_logs(limit: int = 200) -> list[dict[str, Any]]:
    return log_bus.history(limit)


@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket) -> None:
    await ws.accept()
    for entry in log_bus.history(100):
        await ws.send_json(entry)
    q = await log_bus.subscribe()
    try:
        while True:
            entry = await q.get()
            await ws.send_json(entry)
    except WebSocketDisconnect:
        pass
    finally:
        await log_bus.unsubscribe(q)


@app.get("/api/profiles")
async def profiles() -> dict[str, Any]:
    return {"profiles": cfg.list_profiles(), "default": cfg.load_settings().get("default_profile")}


@app.get("/api/profiles/{name}")
async def get_profile(name: str, device: str = None) -> dict[str, Any]:
    try:
        return cfg.load_profile(name, device)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.patch("/api/profiles/{name}")
async def patch_profile(name: str, body: ProfileMetaUpdate, device: str = None) -> dict[str, Any]:
    try:
        profile = cfg.load_profile(name, device)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    data = body.model_dump(exclude_none=True)
    profile.update(data)
    return cfg.save_profile(name, profile, device)


@app.post("/api/profiles/{name}/points")
async def calibrate_point(name: str, body: CalibratePoint, device: str = None) -> dict[str, Any]:
    try:
        profile = cfg.set_point(
            name,
            body.key,
            body.x,
            body.y,
            label=body.label,
            group=body.group,
            device=device,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    tap_result = None
    if body.test_tap:
        test_dev = device or body.device or bot.device or cfg.load_settings().get("default_device")
        if not test_dev:
            raise HTTPException(400, "device required for test_tap")
        try:
            await device_manager.ensure()
        except Exception:
            await device_manager.connect()
        dry = bool(cfg.load_settings().get("dry_run", True))
        tap_result = await device_manager.tap(test_dev, body.x, body.y, dry_run=dry)

    return {"ok": True, "profile": profile, "tap": tap_result}


@app.get("/api/profiles/{name}/export")
async def export_profile(name: str, device: str = None):
    try:
        path = cfg.profile_path(name, device)
        if not path.exists():
            path = cfg.profile_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Profile {name} not found")
        filename = f"{name}_{device}.json" if device else f"{name}.json"
        return FileResponse(path, media_type="application/json", filename=filename)
    except Exception as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/profiles/{name}/import")
async def import_profile(name: str, file: UploadFile = File(...), device: str = None) -> dict[str, Any]:
    try:
        content = await file.read()
        import json
        data = json.loads(content.decode("utf-8"))
        if "points" not in data:
            raise ValueError("Invalid profile file: missing 'points'")
        cfg.save_profile(name, data, device)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


    await log_bus.info(f"Calibrated point {body.key} = ({body.x}, {body.y}) on profile {name}")
    return {"profile": profile, "tap_result": tap_result}


@app.post("/api/tap")
async def manual_tap(body: TapRequest) -> dict[str, Any]:
    settings = cfg.load_settings()
    dry = settings.get("dry_run", True) if body.dry_run is None else body.dry_run
    try:
        await device_manager.ensure()
    except Exception:
        await device_manager.connect()
    resp = await device_manager.tap(
        body.device,
        body.x,
        body.y,
        settle_ms=int(settings.get("tap_settle_ms", 80)),
        dry_run=bool(dry),
    )
    return resp


@app.get("/api/calibration/checklist")
async def calibration_checklist(profile: str = "admin_live", device: str = None) -> dict[str, Any]:
    """Ordered calibration points for Admin Live HP."""
    try:
        data = cfg.load_profile(profile, device)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    # Priority order: home bar first, then each form
    order = [
        "home.lelang",
        "home.iklan_live",
        "home.lainnya",
        "home.mulai_livestream",
        "home.produk",
        "home.komentar",
        "home.voucher",
        "lelang.time_10",
        "lelang.time_30",
        "lelang.time_60",
        "lelang.time_120",
        "lelang.mulai",
        "lelang.judul",
        "lelang.close",
        "iklan.tujuan_gmv_auto",
        "iklan.tujuan_gmv_roas",
        "iklan.durasi_tak_terbatas",
        "iklan.durasi_1",
        "iklan.durasi_3",
        "iklan.durasi_7",
        "iklan.durasi_14",
        "iklan.durasi_manual",
        "iklan.aktifkan",
        "iklan.close",
        "lainnya.bonus_koin",
        "lainnya.hujan_bonus",
        "lainnya.close",
        "bonus.bagi_250k",
        "bonus.bagi_100k",
        "bonus.bagi_50k",
        "bonus.bagi_25k",
        "bonus.claim_200",
        "bonus.claim_100",
        "bonus.claim_50",
        "bonus.claim_25",
        "bonus.mulai",
        "bonus.close",
        "hujan.koin_127",
        "hujan.koin_191",
        "hujan.koin_255",
        "hujan.mulai",
        "hujan.close",
    ]
    points = data.get("points") or {}
    items = []
    for key in order:
        if key not in points:
            continue
        pt = points[key]
        items.append(
            {
                "key": key,
                "label": pt.get("label") or key,
                "group": pt.get("group") or key.split(".")[0],
                "x": str(pt.get("x")),
                "y": str(pt.get("y")),
                "calibrated": bool(pt.get("calibrated")),
            }
        )
    # Append any extra keys not in order
    for key, pt in points.items():
        if key in order:
            continue
        items.append(
            {
                "key": key,
                "label": pt.get("label") or key,
                "group": pt.get("group") or key.split(".")[0],
                "x": str(pt.get("x")),
                "y": str(pt.get("y")),
                "calibrated": bool(pt.get("calibrated")),
            }
        )

    return {
        "profile": profile,
        "meta": {
            "label": data.get("label"),
            "device_serial": data.get("device_serial"),
            "calibrated": data.get("calibrated"),
            "source_width": data.get("source_width"),
            "source_height": data.get("source_height"),
            "notes": data.get("notes"),
        },
        "items": items,
        "progress": {
            "done": sum(1 for i in items if i["calibrated"]),
            "total": len(items),
        },
        "reference_images": {
            "home": "/assets/image/Tampilan Tombol Home Live.jpg",
            "lainnya": "/assets/image/Tampilan Menu Lainnya.jpg",
            "lelang": "/assets/image/Form Lelang.jpg",
            "iklan": "/assets/image/Form Iklan-Live.jpeg",
            "bonus": "/assets/image/Form Bonus Koin.jpg",
            "hujan": "/assets/image/Form Hujan Bonus.jpg",
        },
    }
