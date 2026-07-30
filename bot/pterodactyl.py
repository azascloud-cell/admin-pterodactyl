"""
Pterodactyl Application API Client
Docs: https://dashflo.net/docs/api/pterodactyl/v1/
"""
import requests, secrets, string, logging
from bot.config import PTERODACTYL_URL, PTERODACTYL_KEY, NODEJS_EGG_ID, PYTHON_EGG_ID, DEFAULT_LOCATION, DEFAULT_NODE

log = logging.getLogger(__name__)

def _headers():
    return {
        "Authorization": f"Bearer {PTERODACTYL_KEY}",
        "Accept":        "application/json",
        "Content-Type":  "application/json",
    }

def _url(path): return f"{PTERODACTYL_URL}/api/application{path}"

def _gen_pass(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(chars) for _ in range(length))

# ─── Users ────────────────────────────────────────────────────────────────────

def create_user(telegram_id: int, username: str) -> dict:
    """
    Buat user baru di Pterodactyl panel.
    Returns: { "success": bool, "user_id": int, "email": str, "username": str, "password": str }
    """
    password  = _gen_pass()
    email     = f"tg{telegram_id}@pteroshop.bot"
    uname     = f"u{telegram_id}"[:16]   # max 16 chars

    payload = {
        "email":      email,
        "username":   uname,
        "first_name": username or f"User{telegram_id}",
        "last_name":  "PteroShop",
        "password":   password,
        "root_admin": False,
    }
    try:
        r = requests.post(_url("/users"), json=payload, headers=_headers(), timeout=15)
        if r.status_code in (200, 201):
            d = r.json()["attributes"]
            return {
                "success":  True,
                "user_id":  d["id"],
                "email":    d["email"],
                "username": d["username"],
                "password": password,
            }
        # User email already exists — coba get existing
        if r.status_code == 422:
            existing = get_user_by_email(email)
            if existing:
                return {
                    "success":  True,
                    "user_id":  existing["id"],
                    "email":    existing["email"],
                    "username": existing["username"],
                    "password": password,  # reset password
                    "existing": True,
                }
        log.error("create_user failed %s: %s", r.status_code, r.text[:300])
        return {"success": False, "error": r.text[:200]}
    except Exception as e:
        log.exception("create_user error")
        return {"success": False, "error": str(e)}

def get_user_by_email(email: str) -> dict | None:
    try:
        r = requests.get(_url(f"/users?filter[email]={email}"), headers=_headers(), timeout=10)
        data = r.json().get("data", [])
        if data:
            return data[0]["attributes"]
    except Exception:
        pass
    return None

# ─── Servers ─────────────────────────────────────────────────────────────────

def get_free_allocation(node_id: int) -> int | None:
    """Dapat allocation ID kosong pertama di node."""
    try:
        r = requests.get(
            _url(f"/nodes/{node_id}/allocations?per_page=100"),
            headers=_headers(), timeout=10
        )
        for alloc in r.json().get("data", []):
            a = alloc["attributes"]
            if not a.get("assigned"):
                return a["id"]
    except Exception:
        log.exception("get_free_allocation error")
    return None

def create_server(
    user_id:    int,
    order_id:   int,
    package:    dict,
    egg_type:   str = "nodejs",
    node_id:    int | None = None,
    location_id:int | None = None,
) -> dict:
    """
    Buat server baru untuk user.
    Returns: { "success": bool, "server_id": int }
    """
    node_id     = node_id or DEFAULT_NODE
    location_id = location_id or DEFAULT_LOCATION
    egg_id      = NODEJS_EGG_ID if egg_type == "nodejs" else PYTHON_EGG_ID
    alloc_id    = get_free_allocation(node_id)

    ram  = package["ram"]   # MB (0 = unlimited)
    cpu  = package["cpu"]   # %  (0 = unlimited)
    disk = package["disk"]  # MB (0 = unlimited)

    # Startup command per egg
    startup = {
        "nodejs": "node {{MAIN_FILE}}",
        "python": "python {{MAIN_FILE}}",
    }.get(egg_type, "bash")

    # Environment defaults per egg
    env = {
        "nodejs": {"MAIN_FILE": "index.js"},
        "python": {"MAIN_FILE": "main.py"},
    }.get(egg_type, {})

    payload = {
        "name":         f"Order-{order_id}",
        "user":         user_id,
        "egg":          egg_id,
        "docker_image": "ghcr.io/pterodactyl/yolks:nodejs_18" if egg_type == "nodejs"
                        else "ghcr.io/pterodactyl/yolks:python_3.11",
        "startup":      startup,
        "environment":  env,
        "limits": {
            "memory": ram,
            "swap":   0,
            "disk":   disk,
            "io":     500,
            "cpu":    cpu,
        },
        "feature_limits": {
            "databases":   1,
            "backups":     2,
            "allocations": 1,
        },
        "allocation": {"default": alloc_id} if alloc_id else None,
        "deploy": {
            "locations":        [location_id],
            "dedicated_ip":     False,
            "port_range":       [],
        } if not alloc_id else None,
    }

    # Hapus key None
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        r = requests.post(_url("/servers"), json=payload, headers=_headers(), timeout=20)
        if r.status_code in (200, 201):
            d = r.json()["attributes"]
            return {"success": True, "server_id": d["id"], "uuid": d["uuid"]}
        log.error("create_server failed %s: %s", r.status_code, r.text[:500])
        return {"success": False, "error": r.text[:300]}
    except Exception as e:
        log.exception("create_server error")
        return {"success": False, "error": str(e)}

def update_server_egg(server_id: int, egg_type: str) -> dict:
    """Ganti egg server yang sudah ada."""
    egg_id = NODEJS_EGG_ID if egg_type == "nodejs" else PYTHON_EGG_ID
    try:
        # Dapatkan detail server dulu
        r = requests.get(_url(f"/servers/{server_id}"), headers=_headers(), timeout=10)
        srv = r.json()["attributes"]

        payload = {
            "egg":         egg_id,
            "startup":     "node {{MAIN_FILE}}" if egg_type == "nodejs" else "python {{MAIN_FILE}}",
            "environment": {"MAIN_FILE": "index.js" if egg_type == "nodejs" else "main.py"},
            "skip_scripts": False,
        }
        r2 = requests.patch(
            _url(f"/servers/{server_id}/startup"),
            json=payload, headers=_headers(), timeout=15
        )
        if r2.status_code in (200, 201):
            return {"success": True}
        return {"success": False, "error": r2.text[:200]}
    except Exception as e:
        log.exception("update_server_egg error")
        return {"success": False, "error": str(e)}

def list_user_servers(ptero_user_id: int) -> list:
    """List semua server milik user."""
    try:
        r = requests.get(
            _url(f"/users/{ptero_user_id}?include=servers"),
            headers=_headers(), timeout=10
        )
        data = r.json()
        servers = (data.get("attributes", {})
                       .get("relationships", {})
                       .get("servers", {})
                       .get("data", []))
        return [s["attributes"] for s in servers]
    except Exception:
        return []

def get_panel_url() -> str:
    from bot.config import PTERODACTYL_URL
    return PTERODACTYL_URL
