# Shopee Live Bot (Panda)

Automate Shopee Live host tools on an **Admin Live** Android phone through **Panda** screen projection.

```
HP Admin Live ──USB/WiFi──► Panda (ws://127.0.0.1:22222/)
                                ▲
                         Bot backend (FastAPI)
                                ▲
                      Web dashboard (panel)
```

## Features

- Open Shopee, Lelang, Iklan Live, Bonus Koin, Hujan Bonus
- Task scheduler with Start / Pause / Stop
- Dry-run mode (safe by default)
- Live logs over WebSocket
- **Coordinate calibration** UI for profile `admin_live`

## Prerequisites

1. [Panda](https://doc.some3c.com/panda-manual/api-documentation) running on this PC  
2. **Panda API membership activated** (unlicensed installs connect to `ws://127.0.0.1:22222/` but return `请激活会员后使用` on commands)  
3. HP Admin Live connected (USB or WiFi)  
4. Python 3.11+  

## Setup

```powershell
cd C:\Users\oktan\Work\Project\Shopee-Automization
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
# From repo root, with venv active
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open: http://127.0.0.1:8000/

## First-time calibration (HP Admin Live)

Default taps are **placeholders**. Calibrate before turning dry-run OFF.

1. Start Panda + connect the Admin Live phone.  
2. Open the dashboard → **Refresh devices** → select the phone.  
3. Keep **Dry-run ON** while learning the UI.  
4. On the phone, open Shopee Live host screen (mode tes is fine).  
5. In **Coordinate Calibration**:
   - Pick a checklist point (start with `Home · Lelang`)
   - Open the matching UI on the phone
   - Click the same control on the reference image (or type X/Y %)
   - **Save point** — or **Save + Test tap** (with dry-run OFF only when ready)
6. Calibrate at least:
   - `home.lelang`, `home.iklan_live`, `home.lainnya`
   - Lelang times + Mulai
   - Iklan tujuan/durasi + Aktifkan
   - Lainnya → Bonus/Hujan + presets + Mulai  
7. Profile is stored in `config/coords/admin_live.json`.

## Using tasks

1. Save settings (device + profile + dry-run).  
2. Create a task (e.g. Lelang every 300s).  
3. **Run once now** to verify the sequence in logs.  
4. **Start Bot** to enable the scheduler.  

When ready for real touches: set **Dry-run OFF**, Save settings, re-test one flow carefully (ads/coins spend real balance).

## Config

| Path | Purpose |
|------|---------|
| `config/settings.json` | Panda URL, package, dry-run, delays |
| `config/coords/admin_live.json` | Percentage coordinate map |

## API (selected)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/devices` | Panda device list |
| GET/PUT | `/api/settings` | Bot settings |
| POST | `/api/bot/control` | `{action: start\|pause\|stop}` |
| POST | `/api/tasks` | Create scheduled task |
| POST | `/api/tasks/run-once` | Execute one task now |
| GET | `/api/calibration/checklist` | Calibration items |
| POST | `/api/profiles/{name}/points` | Save calibrated point |
| WS | `/ws/logs` | Live log stream |

## Safety

- Default **`dry_run: true`** — logs planned taps only.  
- Iklan Live and coin tools can spend real saldo.  
- Stop clears the runner; disable tasks you do not want.

## Project layout

```
backend/app/          FastAPI app, Panda client, scheduler, flows
backend/static/       Dashboard panel
config/               Settings + coordinate profiles
assets/image/         UI reference screenshots
.grok/skills/shopee-live-bot/   Agent skill
```
