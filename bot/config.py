"""
Konfigurasi bot — baca dari environment variable.
Nilai produk/paket kini disimpan di DB (tabel products).
Config dinamis (egg IDs, dll) bisa di-override via tabel bot_config.
"""
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PAKASIR_API_KEY    = os.environ.get("PAKASIR_API_KEY", "")
PAKASIR_PROJECT    = os.environ.get("PAKASIR_PROJECT", "")

PTERODACTYL_URL    = os.environ.get("PTERODACTYL_PANEL_URL", "").rstrip("/")
PTERODACTYL_KEY    = os.environ.get("PTERODACTYL_API_KEY", "")

BOT_OWNER_ID       = int(os.environ.get("BOT_OWNER_ID", "0"))

# Admin panel web
ADMIN_PANEL_PORT   = int(os.environ.get("ADMIN_PANEL_PORT", "8080"))
ADMIN_USERNAME     = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD     = os.environ.get("ADMIN_PASSWORD", "changeme")
SESSION_SECRET     = os.environ.get("SESSION_SECRET", "supersecretkey")

# Egg IDs — fallback jika belum ada di DB
NODEJS_EGG_ID      = int(os.environ.get("NODEJS_EGG_ID", "15"))
PYTHON_EGG_ID      = int(os.environ.get("PYTHON_EGG_ID", "16"))

# Default location/node untuk server baru
DEFAULT_LOCATION   = int(os.environ.get("DEFAULT_LOCATION_ID", "1"))
DEFAULT_NODE       = int(os.environ.get("DEFAULT_NODE_ID", "1"))

# Public webhook base URL
_domain = os.environ.get("REPLIT_DEV_DOMAIN", "") or os.environ.get("PUBLIC_DOMAIN", "")
WEBHOOK_BASE_URL      = f"https://{_domain}" if _domain else ""
PAKASIR_CALLBACK_PATH = "/pakasir/callback"
PAKASIR_CALLBACK_URL  = f"{WEBHOOK_BASE_URL}{PAKASIR_CALLBACK_PATH}" if WEBHOOK_BASE_URL else ""

# ─── Paket default (dipakai saat tabel products kosong) ───────────────────────
DEFAULT_PACKAGES = [
    {"id":  1, "name": "Paket 1",     "ram":  1024, "cpu":  30,  "disk":  5120,  "price":  3500},
    {"id":  2, "name": "Paket 2",     "ram":  2048, "cpu":  40,  "disk": 10240,  "price":  4500},
    {"id":  3, "name": "Paket 3",     "ram":  3072, "cpu":  50,  "disk": 15360,  "price":  5500},
    {"id":  4, "name": "Paket 4",     "ram":  4096, "cpu":  60,  "disk": 20480,  "price":  6500},
    {"id":  5, "name": "Paket 5",     "ram":  5120, "cpu":  70,  "disk": 25600,  "price":  7500},
    {"id":  6, "name": "Paket 6",     "ram":  6144, "cpu":  80,  "disk": 30720,  "price":  8500},
    {"id":  7, "name": "Paket 7",     "ram":  7168, "cpu":  90,  "disk": 35840,  "price":  9500},
    {"id":  8, "name": "Paket 8",     "ram":  8192, "cpu": 100,  "disk": 40960,  "price": 11000},
    {"id":  9, "name": "Paket 9",     "ram":  9216, "cpu": 120,  "disk": 46080,  "price": 12000},
    {"id": 10, "name": "Paket 10",    "ram": 10240, "cpu": 150,  "disk": 51200,  "price": 13000},
    {"id": 11, "name": "Unlimited ♾️","ram":     0, "cpu":   0,  "disk":     0,  "price": 16500},
]

def get_packages():
    """Ambil paket dari DB; fallback ke DEFAULT_PACKAGES jika DB kosong."""
    try:
        from bot import database as db
        rows = db.get_products(active_only=True)
        if rows:
            return [{"id": r["id"], "name": r["name"], "ram": r["ram"],
                     "cpu": r["cpu"], "disk": r["disk"], "price": r["price"]}
                    for r in rows]
    except Exception:
        pass
    return DEFAULT_PACKAGES

# Alias untuk backward compat
PACKAGES = DEFAULT_PACKAGES

def get_package(pkg_id: int):
    pkgs = get_packages()
    return next((p for p in pkgs if p["id"] == pkg_id), None)

def get_db_config(key: str, default=None):
    """Baca nilai dari tabel bot_config, fallback ke env/default."""
    try:
        from bot import database as db
        val = db.get_config(key)
        return val if val is not None else default
    except Exception:
        return default
