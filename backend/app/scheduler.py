from __future__ import annotations

import asyncio
import time
import uuid
from copy import deepcopy
from typing import Any

from . import config as cfg
from .flows import build_steps
from .logger import log_bus
from .device_manager import device_manager


class BotScheduler:
    def __init__(self) -> None:
        self.status: str = "stopped"  # stopped | running | paused
        self.device: str = ""
        self.profile_name: str = "admin_live"
        self.dry_run: bool = True
        self.tasks: dict[str, dict[str, Any]] = {}
        self._device_lock = asyncio.Lock()
        self._runner_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self.last_run: dict[str, float] = {}
        self._settings: dict[str, Any] = cfg.load_settings()
        self.queue: list[dict[str, Any]] = []
        self.active_task: dict[str, Any] | None = None
        self._worker_task: asyncio.Task | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "device": self.device,
            "profile": self.profile_name,
            "dry_run": self.dry_run,
            "tasks": list(self.tasks.values()),
            "queue": self.queue,
            "active_task": self.active_task,
            "panda_connected": device_manager.connected,
            "settings": self._settings,
        }

    def reload_settings(self) -> dict[str, Any]:
        self._settings = cfg.load_settings()
        if not self.device and self._settings.get("default_device"):
            self.device = self._settings["default_device"]
        if self._settings.get("default_profile"):
            self.profile_name = self._settings["default_profile"]
        if "dry_run" in self._settings:
            self.dry_run = bool(self._settings["dry_run"])
        return self._settings

    def add_task(self, task_type: str, interval_sec: int, params: dict[str, Any], enabled: bool = True) -> dict[str, Any]:
        task_id = str(uuid.uuid4())[:8]
        task = {
            "id": task_id,
            "type": task_type,
            "enabled": enabled,
            "interval_sec": interval_sec,
            "params": params or {},
            "created_at": time.time(),
            "run_count": 0,
            "last_error": None,
        }
        self.tasks[task_id] = task
        return task

    def update_task(self, task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        task = self.tasks[task_id]
        for k in ("enabled", "interval_sec", "params", "run_count"):
            if k in patch and patch[k] is not None:
                task[k] = patch[k]
        return task

    def remove_task(self, task_id: str) -> None:
        self.tasks.pop(task_id, None)
        self.last_run.pop(task_id, None)

    def clear_tasks(self) -> None:
        self.tasks.clear()
        self.last_run.clear()

    async def start(self, device: str | None = None, profile: str | None = None, dry_run: bool | None = None) -> dict[str, Any]:
        self.reload_settings()
        if device:
            self.device = device
        if profile:
            self.profile_name = profile
        if dry_run is not None:
            self.dry_run = dry_run
        if not self.device:
            raise ValueError("No device selected")

        if self.status == "running":
            return self.snapshot()

        if self.status == "paused":
            self.status = "running"
            await log_bus.info("Bot resumed")
            return self.snapshot()

        self._stop_event.clear()
        self.status = "running"
        try:
            await device_manager.connect()
        except Exception as exc:
            self.status = "stopped"
            raise RuntimeError(f"Cannot connect: {exc}") from exc

        self._runner_task = asyncio.create_task(self._loop(), name="bot-scheduler")
        self._worker_task = asyncio.create_task(self._worker(), name="bot-worker")
        await log_bus.info(
            f"Bot started device={self.device} profile={self.profile_name} dry_run={self.dry_run}"
        )
        return self.snapshot()

    async def pause(self) -> dict[str, Any]:
        if self.status == "running":
            self.status = "paused"
            await log_bus.warn("Bot paused")
        return self.snapshot()

    async def stop(self) -> dict[str, Any]:
        self.status = "stopped"
        self._stop_event.set()
        if self._runner_task and not self._runner_task.done():
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
        self._runner_task = None
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._worker_task = None
        self.queue.clear()
        self.active_task = None
        await log_bus.warn("Bot stopped — queue cleared of in-flight runner")
        return self.snapshot()

    async def _loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                if self.status == "running":
                    now = time.time()
                    for task in list(self.tasks.values()):
                        if not task.get("enabled"):
                            continue
                        tid = task["id"]
                        interval = int(task.get("interval_sec") or 300)
                        last = self.last_run.get(tid, 0)
                        if now - last >= interval:
                            if self.active_task is not None or len(self.queue) > 0:
                                pass # Jangan update last_run, biarkan mencoba lagi detik berikutnya
                            else:
                                self.queue.append(task)
                                self.last_run[tid] = time.time()
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass

    async def _worker(self) -> None:
        try:
            while not self._stop_event.is_set():
                if self.queue and self.status == "running":
                    self.active_task = self.queue.pop(0)
                    try:
                        await self._process_task(self.active_task)
                    finally:
                        self.active_task = None
                else:
                    await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass

    async def _process_task(self, task: dict[str, Any]) -> None:
        tid = task["id"]
        try:
            await self.execute_task(task)
            if tid in self.tasks:
                self.tasks[tid]["run_count"] = int(self.tasks[tid].get("run_count") or 0) + 1
                self.tasks[tid]["last_error"] = None
            else:
                task["run_count"] = int(task.get("run_count") or 0) + 1
                task["last_error"] = None
                
            # Incremental logic
            if task["type"] == "lelang":
                params = self.tasks[tid]["params"] if tid in self.tasks else task["params"]
                harga = params.get("harga")
                kel = params.get("kelipatan_harga")
                max_val = params.get("max_harga")
                if harga and kel:
                    try:
                        new_harga = int(harga) + int(kel)
                        if max_val:
                            max_int = int(max_val)
                            if new_harga > max_int:
                                new_harga = max_int
                        params["harga"] = str(new_harga)
                    except ValueError:
                        pass
            elif task["type"] == "iklan_live":
                params = self.tasks[tid]["params"] if tid in self.tasks else task["params"]
                modal = params.get("modal")
                kel = params.get("kelipatan_modal")
                max_val = params.get("max_modal")
                if modal and kel:
                    try:
                        new_modal = int(modal) + int(kel)
                        if max_val:
                            max_int = int(max_val)
                            if new_modal > max_int:
                                new_modal = max_int
                        params["modal"] = new_modal
                    except ValueError:
                        pass
        except Exception as exc:
            if tid in self.tasks:
                self.tasks[tid]["last_error"] = str(exc)
            else:
                task["last_error"] = str(exc)
            await log_bus.error(f"Task {tid} ({task['type']}) failed: {exc}")

    async def execute_task(self, task: dict[str, Any], *, dry_run_override: bool | None = None) -> list[dict[str, Any]]:
        if not self.device:
            raise ValueError("No device selected")
        settings = cfg.load_settings()
        profile = cfg.load_profile(self.profile_name, self.device)
        steps = build_steps(task["type"], profile, task.get("params") or {}, settings)
        dry = self.dry_run if dry_run_override is None else dry_run_override
        settle = int(settings.get("tap_settle_ms", 80))

        await log_bus.info(
            f"Execute {task['type']} id={task.get('id', 'once')} steps={len(steps)} dry_run={dry}",
            task=task,
        )

        async with self._device_lock:
            results: list[dict[str, Any]] = []
            for step in steps:
                result = await self._run_step(step, dry=dry, settle=settle)
                results.append(result)
                delay = int(step.get("delay_ms") or 0)
                if delay > 0:
                    await asyncio.sleep(delay / 1000)
            return results

    async def _run_step(self, step: dict[str, Any], *, dry: bool, settle: int) -> dict[str, Any]:
        kind = step["kind"]
        note = step.get("note") or kind
        await log_bus.info(f"Step: {note}", step=step)

        if kind == "wait":
            return {"ok": True, "step": step}

        if kind == "tap":
            text_target = step.get("text_target")
            resp = None
            
            # 1. Try finding by text (UI Automator) first
            if text_target and not dry:
                if hasattr(device_manager, "tap_text"):
                    success = await device_manager.tap_text(self.device, text_target)
                    if success:
                        resp = {"code": 10000, "message": f"Text matched: {text_target}"}
            
            # 2. Fallback to coordinate tap
            if not resp:
                resp = await device_manager.tap(
                    self.device,
                    step["x"],
                    step["y"],
                    settle_ms=settle,
                    dry_run=dry,
                )
            return {"ok": resp.get("code") == 10000, "step": step, "response": resp}

        if kind == "swipe":
            resp = await device_manager.swipe(
                self.device,
                step["x1"],
                step["y1"],
                step["x2"],
                step["y2"],
                duration_ms=step.get("duration_ms", 500),
                dry_run=dry,
            )
            return {"ok": resp.get("code") == 10000, "step": step, "response": resp}

        if kind == "start_apk":
            resp = await device_manager.start_apk(self.device, step["apk"], dry_run=dry)
            return {"ok": resp.get("code") == 10000, "step": step, "response": resp}

        if kind == "push":
            resp = await device_manager.push_event(self.device, step["type"], dry_run=dry)
            return {"ok": resp.get("code") == 10000, "step": step, "response": resp}

        if kind == "input_text":
            resp = await device_manager.input_text(self.device, step["content"], dry_run=dry)
            return {"ok": resp.get("code") == 10000, "step": step, "response": resp}

        raise ValueError(f"Unknown step kind: {kind}")

    async def run_once(
        self,
        task_type: str,
        params: dict[str, Any],
        *,
        device: str | None = None,
        profile: str | None = None,
        dry_run: bool | None = None,
    ) -> list[dict[str, Any]]:
        if device:
            self.device = device
        if profile:
            self.profile_name = profile
        self.reload_settings()
        if not self.device:
            raise ValueError("No device selected")
        try:
            await device_manager.ensure()
        except Exception:
            await device_manager.connect()
        task_id = "manual_" + str(uuid.uuid4())[:4]
        task = {"id": task_id, "type": task_type, "params": params or {}, "enabled": True, "manual": True}
        self.queue.append(task)
        await log_bus.info(f"Task {task_id} added to manual queue.")
        return []


bot = BotScheduler()
