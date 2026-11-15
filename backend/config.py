"""Configuration for ASV Inventory Training Application."""
from pathlib import Path
import os
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
PUBLIC_DATA_DIR = DATA_DIR / "public"
PRIVATE_DATA_DIR = DATA_DIR / "private"
ASSETS_DIR = BASE_DIR / "assets"
TEMPLATES_DIR = BASE_DIR / "templates"

# Simplified Pack Paths
SLIDES_FILE = BASE_DIR / "slides.json"
SLIDES_DIR = BASE_DIR / "slides"
QUESTIONS_FILE = BASE_DIR / "questions.json"
ANSWER_KEY_FILE = BASE_DIR / "answer_key.server.json"
MAU_BAO_CAO_FILE = BASE_DIR / "Mau_bao_cao.csv"

DB_PATH = Path(os.getenv("ASV_DB_PATH", str(BASE_DIR / "asv_training.db")))
DEMO_DB_PATH = Path(os.getenv("ASV_DEMO_DB_PATH", str(BASE_DIR / "asv_demo.db")))

TZ_VN = timezone(timedelta(hours=7))
DEADLINE_EXCLUSIVE = datetime.fromisoformat("2026-12-01T00:00:00+07:00")
COURSE_VERSION = "2026.11-simple-v2"
LEGACY_COURSE_VERSION = "ASV-INV-2026.11-v1"

ADMIN_USERNAME = os.getenv("ASV_ADMIN_USER", "ADMIN01")
ADMIN_PASSWORD = os.getenv("ASV_ADMIN_PASS", "AsvAdmin@2026")
GOOGLE_SHEET_WEBHOOK_URL = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "")

JWT_SECRET = os.getenv("ASV_SECRET_KEY", "asv-inventory-2026-super-secure-production-secret-key-ajax")
SERVER_HOST = os.getenv("ASV_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", os.getenv("ASV_SERVER_PORT", "8000")))

def now_vn():
    return datetime.now(TZ_VN)

def now_iso():
    return now_vn().isoformat()
