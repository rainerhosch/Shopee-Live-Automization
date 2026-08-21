from __future__ import annotations

from typing import Any

from .config import get_point


def _tap_step(key: str, profile: dict[str, Any], delay_ms: int, note: str = "", text_target: str = None) -> dict[str, Any]:
    try:
        pt = get_point(profile, key)
        x, y = pt["x"], pt["y"]
    except KeyError:
        x, y = "0", "0"
    
    return {
        "kind": "tap",
        "key": key,
        "x": x,
        "y": y,
        "text_target": text_target,
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
        _tap_step("home.mulai_livestream", profile, delay + 400, "Mulai Livestream")
    ]


def build_lelang(profile: dict[str, Any], params: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    delay = int(settings.get("step_delay_ms", 600))
    batas = str(params.get("batas_waktu", "10 detik"))
    time_map = {
        "10 detik": "lelang.time_10",
        "30 detik": "lelang.time_30",
        "50 detik": "lelang.time_50",
        "10dtk": "lelang.time_10",
        "30dtk": "lelang.time_30",
        "60dtk": "lelang.time_60",
        "120dtk": "lelang.time_120",
    }
    if batas not in time_map:
        raise ValueError(f"Invalid batas_waktu: {batas}")

    steps = [
        _tap_step("home.lelang", profile, delay + 200, "Open Lelang")
    ]
    if params.get("judul"):
        steps.append(_tap_step("lelang.judul", profile, delay, "Focus Judul"))
        steps.append({
            "kind": "input_text",
            "content": str(params["judul"]),
            "delay_ms": delay,
            "note": "Type Judul",
        })
        steps.append({"kind": "push", "type": 4, "delay_ms": delay, "note": "Dismiss Keyboard (BACK)"})

    if params.get("harga"):
        steps.append(_tap_step("lelang.harga", profile, delay, "Focus Harga"))
        steps.append({
            "kind": "input_text",
            "content": str(params["harga"]),
            "delay_ms": delay,
            "note": "Type Harga",
        })
        steps.append({"kind": "push", "type": 4, "delay_ms": delay, "note": "Dismiss Keyboard (BACK)"})
        
    mode = str(params.get("mode", "Acak"))
    mode_key = "lelang.mode_acak" if mode == "Acak" else "lelang.mode_tercepat"
    steps.append(_tap_step("lelang.mode", profile, delay, "Open Mode"))
    steps.append(_tap_step(mode_key, profile, delay, f"Select Mode {mode}"))

    peserta = str(params.get("peserta", "Semua Penonton"))
    peserta_key = "lelang.peserta_semua" if peserta == "Semua Penonton" else "lelang.peserta_followers"
    steps.append(_tap_step("lelang.peserta", profile, delay, "Open Peserta"))
    steps.append(_tap_step(peserta_key, profile, delay, f"Select Peserta {peserta}"))

    steps.append(_tap_step(time_map[batas], profile, delay, f"Batas {batas}", text_target=batas))
    steps.append(_tap_step("lelang.mulai", profile, delay + 300, "Mulai", text_target="Mulai"))
    return steps


def build_iklan_live(profile: dict[str, Any], params: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    delay = int(settings.get("step_delay_ms", 600))
    tujuan = str(params.get("tujuan", "Tingkatkan Penonton"))
    roas = str(params.get("roas", "ROAS = 5.4"))
    roas_custom = str(params.get("roas_custom", "5.0"))
    durasi_hari = str(params.get("durasi_hari", "Tak Terbatas"))
    durasi_jam = str(params.get("durasi_jam", "Sepanjang Hari"))
    tipe_modal = str(params.get("tipe_modal", "Modal Tidak Terbatas"))
    modal_harian = str(params.get("modal_harian", "10000"))

    tujuan_map = {
        "Tingkatkan Penonton": "iklan.tujuan_penonton",
        "GMV (Max Auto)": "iklan.tujuan_gmv_auto",
        "GMV (Max ROAS)": "iklan.tujuan_gmv_roas",
    }
    durasi_map = {
        "Tak Terbatas": "iklan.durasi_tak_terbatas",
        "1 hari": "iklan.durasi_1",
        "3 hari": "iklan.durasi_3",
        "7 hari": "iklan.durasi_7",
        "14 hari": "iklan.durasi_14",
        "Atur Sendiri": "iklan.durasi_custom",
    }
    jam_map = {
        "Sepanjang Hari": "iklan.jam_all",
        "30 Menit": "iklan.jam_30m",
        "1 Jam": "iklan.jam_1h",
        "2 Jam": "iklan.jam_2h",
        "4 Jam": "iklan.jam_4h",
        "Atur Sendiri": "iklan.jam_custom",
    }
    roas_map = {
        "ROAS = 5.4": "iklan.roas_54",
        "ROAS = 8.0": "iklan.roas_80",
        "ROAS = 9.7": "iklan.roas_97",
        "Masukan Target": "iklan.roas_custom",
    }

    if tujuan not in tujuan_map:
        raise ValueError(f"Invalid tujuan: {tujuan}")
    if durasi_hari not in durasi_map:
        raise ValueError(f"Invalid durasi_hari: {durasi_hari}")

    steps = [
        _tap_step("home.iklan_live", profile, delay + 3500, "Open Iklan Live")
    ]
    
    fallback_steps = [
        _tap_step("iklan.tujuan_dropdown", profile, delay + 1000, "Buka Opsi Tujuan", text_target="Tujuan"),
    ]
    fallback_steps[-1]["tap_right_edge"] = True
    
    # 1. Select Main Tujuan in Popup
    if tujuan == "Tingkatkan Penonton":
        fallback_steps.append(_tap_step("iklan.tujuan_penonton", profile, delay, "Tujuan Tingkatkan Penonton", text_target="Penonton"))
    else:
        # Both GMV Max Auto and GMV Max ROAS require selecting "GMV Max" in the popup first
        fallback_steps.append(_tap_step("iklan.tujuan_gmv_max_popup", profile, delay, "Tujuan GMV Max", text_target="GMV Max"))
        
    fallback_steps.append(_tap_step("iklan.tujuan_konfirmasi", profile, delay + 2500, "Konfirmasi Tujuan", text_target="Konfirmasi"))

    # 2. Select Sub-Tujuan on Main Screen (if GMV Max)
    if tujuan == "GMV (Max Auto)":
        fallback_steps.append(_tap_step("iklan.tujuan_gmv_auto", profile, delay, "Pilih GMV Max Auto", text_target="GMV Max Auto"))
    elif tujuan == "GMV (Max ROAS)":
        fallback_steps.append(_tap_step("iklan.tujuan_gmv_roas", profile, delay, "Pilih GMV Max ROAS", text_target="GMV Max ROAS"))

    # Swipe down to ensure Durasi / Modal are visible
    fallback_steps.append({
        "kind": "swipe",
        "x1": 50,
        "y1": 80,
        "x2": 50,
        "y2": 20,
        "duration_ms": 500,
        "delay_ms": delay + 500,
        "note": "Scroll down",
    })

    if tujuan == "GMV (Max ROAS)":
        if roas not in roas_map:
            raise ValueError(f"Invalid ROAS: {roas}")
        fallback_steps.append(_tap_step(roas_map[roas], profile, delay, f"Select ROAS {roas}", text_target=roas))
        if roas == "Masukan Target":
            fallback_steps.append({
                "kind": "input_text",
                "content": roas_custom,
                "delay_ms": delay,
                "note": f"Type ROAS {roas_custom}",
            })
            
    # Swipe down again to ensure Durasi / Modal are fully visible (since ROAS expands the view)
    fallback_steps.append({
        "kind": "swipe",
        "x1": 50,
        "y1": 80,
        "x2": 50,
        "y2": 20,
        "duration_ms": 500,
        "delay_ms": delay + 500,
        "note": "Scroll down 2",
    })

    fallback_steps.append(_tap_step(durasi_map[durasi_hari], profile, delay, f"Durasi Hari {durasi_hari}", text_target=durasi_hari))

    if tujuan == "Tingkatkan Penonton":
        if durasi_jam not in jam_map:
            raise ValueError(f"Invalid durasi_jam: {durasi_jam}")
        fallback_steps.append(_tap_step(jam_map[durasi_jam], profile, delay, f"Durasi Jam {durasi_jam}", text_target=durasi_jam))

    fallback_steps.append(_tap_step("iklan.modal", profile, delay + 800, "Buka Opsi Modal", text_target="Modal Tidak Terbatas"))
    if tipe_modal == "Modal Tidak Terbatas":
        fallback_steps.append(_tap_step("iklan.modal_unlimited", profile, delay, "Select Modal Tidak Terbatas", text_target="Modal Tidak Terbatas"))
    else:
        fallback_steps.append(_tap_step("iklan.modal_daily", profile, delay, "Select Atur Modal Harian", text_target="Atur Modal Harian"))
        fallback_steps.append({
            "kind": "input_text",
            "content": modal_harian,
            "delay_ms": delay,
            "note": f"Type Modal {modal_harian}",
        })
    
    fallback_steps.append(_tap_step("iklan.modal_selanjutnya", profile, delay + 1000, "Selanjutnya (Modal)", text_target="Selanjutnya"))
    fallback_steps.append(_tap_step("iklan.aktifkan", profile, delay, "Aktifkan Iklan", text_target="Aktifkan Iklan"))
    
    # 6. Optional: Konfirmasi penggantian iklan jika ada iklan lain yang sedang berjalan
    fallback_steps.append({
        "kind": "tap_optional",
        "text_target": "Lanjutkan",
        "delay_ms": delay,
        "note": "Konfirmasi popup penggantian iklan jika ada"
    })

    # Inject dynamic step
    steps.append({
        "kind": "dynamic_iklan_live",
        "penambahan_modal": params.get("penambahan_modal", 5000),
        "fallback_steps": fallback_steps,
        "delay_ms": delay
    })

    return steps


def build_bonus_koin(profile: dict[str, Any], params: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    delay = int(settings.get("step_delay_ms", 600))
    untuk = str(params.get("untuk_dibagikan", "100000"))
    klaim = str(params.get("koin_per_klaim", "100"))
    jumlah = str(params.get("jumlah_klaim", "1000"))

    return [
        _tap_step("home.lainnya", profile, delay + 200, "Open Lainnya"),
        _tap_step("lainnya.bonus_koin", profile, delay + 200, "Open Bonus Koin"),
        _tap_step("bonus.input_dibagikan", profile, delay, "Focus Bagi"),
        {"kind": "input_text", "content": untuk, "delay_ms": delay, "note": f"Input Bagi {untuk}"},
        {"kind": "push", "type": 4, "delay_ms": delay, "note": "Dismiss Keyboard (BACK)"},

        _tap_step("bonus.input_per_klaim", profile, delay, "Focus Klaim"),
        {"kind": "input_text", "content": klaim, "delay_ms": delay, "note": f"Input Klaim {klaim}"},
        {"kind": "push", "type": 4, "delay_ms": delay, "note": "Dismiss Keyboard (BACK)"},

        _tap_step("bonus.input_jumlah_klaim", profile, delay, "Focus Jumlah"),
        {"kind": "input_text", "content": jumlah, "delay_ms": delay, "note": f"Input Jumlah {jumlah}"},
        {"kind": "push", "type": 4, "delay_ms": delay, "note": "Dismiss Keyboard (BACK)"},
        
        _tap_step("bonus.mulai", profile, delay + 500, "Simpan Bonus Koin"),
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
