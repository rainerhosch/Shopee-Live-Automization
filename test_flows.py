from backend.app.flows import build_steps
import json

profile = {"points": {}} # mock profile
settings = {"step_delay_ms": 600}

lelang = build_steps("lelang", profile, {"judul": "Lelang1", "mode": "Acak", "peserta": "Hanya Pengikut", "batas_waktu": "60dtk"}, settings)
iklan = build_steps("iklan_live", profile, {"tujuan": "Tingkatkan Penonton", "durasi_hari": "1 hari", "durasi_jam": "2 Jam", "modal": "15000"}, settings)
bonus = build_steps("bonus_koin", profile, {"untuk_dibagikan": "200000", "koin_per_klaim": "200", "jumlah_klaim": "1000"}, settings)

print("Lelang Steps:", len(lelang))
print("Iklan Steps:", len(iklan))
print("Bonus Steps:", len(bonus))
