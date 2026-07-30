"""
SQLite database untuk menyimpan orders dan users.
"""
import sqlite3, os, threading

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
_lock = threading.Lock()

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _lock:
        conn = get_conn()
        cur = conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id   INTEGER NOT NULL,
            username      TEXT,
            package_id    INTEGER NOT NULL,
            package_name  TEXT NOT NULL,
            amount        INTEGER NOT NULL,
            egg_type      TEXT NOT NULL DEFAULT 'nodejs',
            trx_id        TEXT UNIQUE,
            payment_url   TEXT,
            status        TEXT NOT NULL DEFAULT 'pending',
            ptero_user_id INTEGER,
            ptero_user    TEXT,
            ptero_pass    TEXT,
            ptero_email   TEXT,
            server_id     INTEGER,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            paid_at       DATETIME,
            expires_at    DATETIME
        );

        CREATE TABLE IF NOT EXISTS users (
            telegram_id   INTEGER PRIMARY KEY,
            username      TEXT,
            ptero_user_id INTEGER,
            ptero_email   TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_orders_telegram ON orders(telegram_id);
        CREATE INDEX IF NOT EXISTS idx_orders_trx ON orders(trx_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        """)
        conn.commit()
        conn.close()

# ─── Orders ───────────────────────────────────────────────────────────────────

def create_order(telegram_id, username, package_id, package_name, amount, egg_type="nodejs"):
    with _lock:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO orders (telegram_id, username, package_id, package_name, amount, egg_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (telegram_id, username, package_id, package_name, amount, egg_type))
        conn.commit()
        order_id = cur.lastrowid
        conn.close()
        return order_id

def set_order_payment(order_id, trx_id, payment_url):
    with _lock:
        conn = get_conn()
        conn.execute(
            "UPDATE orders SET trx_id=?, payment_url=? WHERE id=?",
            (trx_id, payment_url, order_id)
        )
        conn.commit()
        conn.close()

def set_order_paid(trx_id, ptero_user_id, ptero_user, ptero_pass, ptero_email, server_id):
    with _lock:
        conn = get_conn()
        conn.execute("""
            UPDATE orders
            SET status='paid', paid_at=CURRENT_TIMESTAMP,
                expires_at=datetime(CURRENT_TIMESTAMP, '+30 days'),
                ptero_user_id=?, ptero_user=?, ptero_pass=?, ptero_email=?, server_id=?
            WHERE trx_id=?
        """, (ptero_user_id, ptero_user, ptero_pass, ptero_email, server_id, trx_id))
        conn.commit()
        conn.close()

def get_order_by_trx(trx_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE trx_id=?", (trx_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_order(order_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_pending_orders():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE status='pending' AND created_at > datetime('now','-24 hours')"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_orders(telegram_id, limit=5):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE telegram_id=? ORDER BY created_at DESC LIMIT ?",
        (telegram_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def expire_old_pending():
    """Expire pending orders older than 24 jam."""
    with _lock:
        conn = get_conn()
        conn.execute(
            "UPDATE orders SET status='expired' WHERE status='pending' AND created_at < datetime('now','-24 hours')"
        )
        conn.commit()
        conn.close()

def update_egg_type(order_id, egg_type):
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE orders SET egg_type=? WHERE id=?", (egg_type, order_id))
        conn.commit()
        conn.close()

# ─── Users ────────────────────────────────────────────────────────────────────

def upsert_user(telegram_id, username, ptero_user_id=None, ptero_email=None):
    with _lock:
        conn = get_conn()
        conn.execute("""
            INSERT INTO users (telegram_id, username, ptero_user_id, ptero_email)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                ptero_user_id=COALESCE(excluded.ptero_user_id, ptero_user_id),
                ptero_email=COALESCE(excluded.ptero_email, ptero_email)
        """, (telegram_id, username, ptero_user_id, ptero_email))
        conn.commit()
        conn.close()

def get_user(telegram_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
