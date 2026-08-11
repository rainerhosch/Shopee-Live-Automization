from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import COORDS_DIR, SETTINGS_PATH


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {
            "connection_mode": "adb",
            "adb_path": "adb",
            "panda_url": "ws://127.0.0.1:22222/",
            "shopee_package": "com.shopee.id",
            "default_device": "",
            "default_profile": "admin_live",
            "step_delay_ms": 600,
            "tap_settle_ms": 80,
            "dry_run": True,
            "auto_go_live": False,
        }
    return _read_json(SETTINGS_PATH)


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    current.update(data)
    _write_json(SETTINGS_PATH, current)
    return current


def list_profiles() -> list[str]:
    COORDS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in COORDS_DIR.glob("*.json"))


def profile_path(name: str, device: str | None = None) -> Path:
    safe = name.replace("..", "").replace("/", "").replace("\\", "")
    if device:
        safe_dev = device.replace("..", "").replace("/", "").replace("\\", "").replace(":", "_")
        return COORDS_DIR / f"{safe}_{safe_dev}.json"
    return COORDS_DIR / f"{safe}.json"


def load_profile(name: str, device: str | None = None) -> dict[str, Any]:
    path = profile_path(name, device)
    if device and not path.exists():
        path = profile_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Coordinate profile not found: {name}")
    data = _read_json(path)
    # Automatically seed device info if missing
    if device and not data.get("device_serial"):
        data["device_serial"] = device
    return data


def save_profile(name: str, data: dict[str, Any], device: str | None = None) -> dict[str, Any]:
    data = deepcopy(data)
    data["profile"] = name
    if device:
        data["device_serial"] = device
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(profile_path(name, device), data)
    return data


def set_point(
    name: str,
    key: str,
    x: str | float,
    y: str | float,
    *,
    label: str | None = None,
    group: str | None = None,
    mark_partial: bool = True,
    device: str | None = None,
) -> dict[str, Any]:
    profile = load_profile(name, device)
    points = profile.setdefault("points", {})
    existing = points.get(key, {})
    points[key] = {
        "x": str(x),
        "y": str(y),
        "label": label or existing.get("label") or key,
        "group": group or existing.get("group") or key.split(".")[0],
        "calibrated": True,
    }
    if mark_partial:
        # Full calibrated flag only when all points marked calibrated
        all_done = all(bool(p.get("calibrated")) for p in points.values())
        profile["calibrated"] = all_done
    return save_profile(name, profile, device)


def get_point(profile: dict[str, Any], key: str) -> dict[str, str]:
    points = profile.get("points") or {}
    if key not in points:
        raise KeyError(f"Missing coordinate key: {key}")
    pt = points[key]
    return {"x": str(pt["x"]), "y": str(pt["y"])}
