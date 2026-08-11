from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
STATIC_DIR = BACKEND_DIR / "static"
CONFIG_DIR = ROOT / "config"
COORDS_DIR = CONFIG_DIR / "coords"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
ASSETS_DIR = ROOT / "assets"
