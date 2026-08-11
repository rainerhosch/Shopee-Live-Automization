from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TaskType = Literal[
    "lelang",
    "iklan_live",
    "bonus_koin",
    "hujan_bonus",
    "open_shopee",
    "go_live",
]


class SettingsUpdate(BaseModel):
    panda_url: str | None = None
    shopee_package: str | None = None
    default_device: str | None = None
    default_profile: str | None = None
    step_delay_ms: int | None = None
    tap_settle_ms: int | None = None
    dry_run: bool | None = None
    auto_go_live: bool | None = None


class TaskCreate(BaseModel):
    type: TaskType
    enabled: bool = True
    interval_sec: int = Field(default=300, ge=10, le=86400)
    params: dict[str, Any] = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    enabled: bool | None = None
    interval_sec: int | None = Field(default=None, ge=10, le=86400)
    params: dict[str, Any] | None = None


class BotControl(BaseModel):
    action: Literal["start", "pause", "stop"]
    device: str | None = None
    profile: str | None = None
    dry_run: bool | None = None


class TapRequest(BaseModel):
    device: str
    x: str | float
    y: str | float
    dry_run: bool | None = None


class CalibratePoint(BaseModel):
    key: str
    x: str | float
    y: str | float
    label: str | None = None
    group: str | None = None
    test_tap: bool = False
    device: str | None = None


class ProfileMetaUpdate(BaseModel):
    label: str | None = None
    device_serial: str | None = None
    source_width: int | None = None
    source_height: int | None = None
    notes: str | None = None
    calibrated: bool | None = None


class RunOnceRequest(BaseModel):
    type: TaskType
    device: str | None = None
    profile: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool | None = None
