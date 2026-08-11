from __future__ import annotations

from typing import Any

from .config import get_point


def _tap_step(key: str, profile: dict[str, Any], delay_ms: int, note: str = "") -> dict[str, Any]:
    pt = get_point(profile, key)
    return {
        "kind": "tap",
        "key": key,
        "x": pt["x"],
        "y": pt["y"],
        "delay_ms": delay_ms,
        "note": note or key,
    }


def _wait(delay_ms: int, note: str = "wait") -> dict[str, Any]:
    return {"kind": "wait", "delay_ms": delay_ms, "note": note}


def _start_apk(apk: str, delay_ms: int = 2000) -> dict[str, Any]:
    return {"kind": "start_apk", "apk": apk, "delay_ms": delay_ms, "note": f"start {apk}"}


def _push(type_code: str, delay_ms: int = 400, note: str = "pushEvent") -> dict[str, Any]:
    return {"kind": "push", "type": type_code, "delay_ms": delay_ms, "note": note}


def build_open_shopee(profile: dict[str, Any], params: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    apk = params.get("apk") or settings.get("shopee_package") or "com.shopee.id"
    return [_start_apk(apk, delay_ms=2500)]


def build_go_live(profile: dict[str, Any], params: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    delay = int(settings.get("step_delay_ms", 600))
    return [
        _tap_step("home.mulai_livestream", profile, delay + 400, "Mulai Livestream"),
    ]


def build_lelang(profile: dict[str, Any], params: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    delay = int(settings.get("step_delay_ms", 600))
    batas = str(params.get("batas_waktu", "10dtk"))
    time_map = {
        "10dtk": "lelang.time_10",
        "30dtk": "lelang.time_30",
        "60dtk": "lelang.time_60",
        "120dtk": "lelang.time_120",
    }
    if batas not in time_map:
        raise ValueError(f"Invalid batas_waktu: {batas}")

    steps = [
        _tap_step("home.lelang", profile, delay + 200, "Open Lelang"),
        _tap_step(time_map[batas], profile, delay, f"Batas {batas}"),
    ]
    # Optional title fill (requires calibrated judul + IME)
    if params.get("judul"):
        steps.insert(1, _tap_step("lelang.judul", profile, delay, "Focus Judul"))
        steps.insert(2, {
            "kind": "input_text",
            "content": str(params["judul"]),
            "delay_ms": delay,
            "note": "Type Judul",
        })
    steps.append(_tap_step("lelang.mulai", profile, delay + 300, "Mulai Lelang"))
    return steps


def build_iklan_live(profile: dict[str, Any], params: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    delay = int(settings.get("step_delay_ms", 600))
    tujuan = str(params.get("tujuan", "GMV Max Auto"))
    durasi = str(params.get("durasi", "Tak Terbatas"))

    tujuan_map = {
        "GMV Max Auto": "iklan.tujuan_gmv_auto",
        "GMV Max ROAS": "iklan.tujuan_gmv_roas",
    }
    durasi_map = {
        "Tak Terbatas": "iklan.durasi_tak_terbatas",
        "1 hari": "iklan.durasi_1",
        "3 hari": "iklan.durasi_3",
        "7 hari": "iklan.durasi_7",
        "14 hari": "iklan.durasi_14",
        "Atur sendiri": "iklan.durasi_manual",
        "Atur sendiri/manual": "iklan.durasi_manual",
    }
    if tujuan not in tujuan_map:
        raise ValueError(f"Invalid tujuan: {tujuan}")
    if durasi not in durasi_map:
        raise ValueError(f"Invalid durasi: {durasi}")

    return [
        _tap_step("home.iklan_live", profile, delay + 300, "Open Iklan Live"),
        _tap_step(tujuan_map[tujuan], profile, delay, f"Tujuan {tujuan}"),
        _tap_step(durasi_map[durasi], profile, delay, f"Durasi {durasi}"),
        _tap_step("iklan.aktifkan", profile, delay + 400, "Aktifkan Iklan"),
    ]


def build_bonus_koin(profile: dict[str, Any], params: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    delay = int(settings.get("step_delay_ms", 600))
    bagi = int(params.get("untuk_dibagikan", 100000))
    claim = int(params.get("koin_per_klaim", 100))

    bagi_map = {
        250000: "bonus.bagi_250k",
        100000: "bonus.bagi_100k",
        50000: "bonus.bagi_50k",
        25000: "bonus.bagi_25k",
    }
    claim_map = {
        200: "bonus.claim_200",
        100: "bonus.claim_100",
        50: "bonus.claim_50",
        25: "bonus.claim_25",
    }
    if bagi not in bagi_map:
        raise ValueError(f"Invalid untuk_dibagikan: {bagi}")
    if claim not in claim_map:
        raise ValueError(f"Invalid koin_per_klaim: {claim}")

    return [
        _tap_step("home.lainnya", profile, delay + 200, "Open Lainnya"),
        _tap_step("lainnya.bonus_koin", profile, delay + 200, "Open Bonus Koin"),
        _tap_step(bagi_map[bagi], profile, delay, f"Bagi {bagi}"),
        _tap_step(claim_map[claim], profile, delay, f"Claim {claim}"),
        _tap_step("bonus.mulai", profile, delay + 300, "Mulai Bonus Koin"),
    ]


def build_hujan_bonus(profile: dict[str, Any], params: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    delay = int(settings.get("step_delay_ms", 600))
    koin = int(params.get("koin_dibagikan", 255))
    koin_map = {
        127: "hujan.koin_127",
        191: "hujan.koin_191",
        255: "hujan.koin_255",
    }
    if koin not in koin_map:
        raise ValueError(f"Invalid koin_dibagikan: {koin}")

    return [
        _tap_step("home.lainnya", profile, delay + 200, "Open Lainnya"),
        _tap_step("lainnya.hujan_bonus", profile, delay + 200, "Open Hujan Bonus"),
        _tap_step(koin_map[koin], profile, delay, f"Koin {koin}"),
        _tap_step("hujan.mulai", profile, delay + 300, "Mulai Hujan Bonus"),
    ]


BUILDERS = {
    "open_shopee": build_open_shopee,
    "go_live": build_go_live,
    "lelang": build_lelang,
    "iklan_live": build_iklan_live,
    "bonus_koin": build_bonus_koin,
    "hujan_bonus": build_hujan_bonus,
}


def build_steps(
    task_type: str,
    profile: dict[str, Any],
    params: dict[str, Any],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    if task_type not in BUILDERS:
        raise ValueError(f"Unknown task type: {task_type}")
    return BUILDERS[task_type](profile, params, settings)
