"""
MySQL database untuk menyimpan orders, users, dan config bot.
Gunakan PyMySQL sebagai driver (pure Python, mudah install).
"""
import os, threading
import pymysql
import pymysql.cursors

_lock = threading.Lock()

def _cfg():
    return dict(
        host     = os.environ.get("DB_HOST",     "127.0.0.1"),
        port     = int(os.environ.get("DB_PORT", "3306")),
        user     = os.environ.get("DB_USER",     os.environ.get("DB_USERNAME", "pterobot")),
        password = os.environ.get("DB_PASSWORD", ""),
        database = os.environ.get("BOT_DB_NAME", "pterobot"),
        charset  = "utf8mb4",
        cursorclass = pymysql.cursors.DictCursor,
        autocommit  = False,
    )

def get_conn():
    return pymysql.connect(**_cfg())

def init_db():
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    telegram_id   BIGINT NOT NULL,
                    username      VARCHAR(255),
                    package_id    INT NOT NULL,
                    package_name  VARCHAR(255) NOT NULL,
                    amount        INT NOT NULL,
                    egg_type      VARCHAR(50) NOT NULL DEFAULT 'nodejs',
                    trx_id        VARCHAR(255) UNIQUE,
                    payment_url   TEXT,
                    status        VARCHAR(50) NOT NULL DEFAULT 'pending',
                    ptero_user_id INT,
                    ptero_user    VARCHAR(255),
                    ptero_pass    VARCHAR(255),
                    ptero_email   VARCHAR(255),
                    server_id     INT,
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                    paid_at       DATETIME,
                    expires_at    DATETIME,
                    INDEX idx_telegram (telegram_id),
                    INDEX idx_trx      (trx_id),
                    INDEX idx_status   (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id   BIGINT PRIMARY KEY,
                    username      VARCHAR(255),
                    ptero_user_id INT,
                    ptero_email   VARCHAR(255),
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_config (
                    cfg_key   VARCHAR(100) PRIMARY KEY,
                    cfg_value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id       INT AUTO_INCREMENT PRIMARY KEY,
                    name     VARCHAR(255) NOT NULL,
                    ram      INT NOT NULL DEFAULT 0,
                    cpu      INT NOT NULL DEFAULT 0,
                    disk     INT NOT NULL DEFAULT 0,
                    price    INT NOT NULL DEFAULT 0,
                    active   TINYINT(1) NOT NULL DEFAULT 1,
                    sort_order INT NOT NULL DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
            conn.commit()
        finally:
            conn.close()

# ─── Config ───────────────────────────────────────────────────────────────────

def get_config(key: str, default=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cfg_value FROM bot_config WHERE cfg_key=%s", (key,))
            row = cur.fetchone()
            return row["cfg_value"] if row else default
    finally:
        conn.close()

def set_config(key: str, value: str):
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bot_config (cfg_key, cfg_value)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE cfg_value=VALUES(cfg_value)
                """, (key, value))
            conn.commit()
        finally:
            conn.close()

def get_all_config() -> dict:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cfg_key, cfg_value FROM bot_config")
            return {r["cfg_key"]: r["cfg_value"] for r in cur.fetchall()}
    finally:
        conn.close()

# ─── Products ─────────────────────────────────────────────────────────────────

def get_products(active_only=True):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            q = "SELECT * FROM products"
            if active_only:
                q += " WHERE active=1"
            q += " ORDER BY sort_order, id"
            cur.execute(q)
            return cur.fetchall()
    finally:
        conn.close()

def upsert_product(name, ram, cpu, disk, price, active=1, sort_order=0, product_id=None):
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                if product_id:
                    cur.execute("""
                        UPDATE products SET name=%s,ram=%s,cpu=%s,disk=%s,price=%s,active=%s,sort_order=%s
                        WHERE id=%s
                    """, (name, ram, cpu, disk, price, active, sort_order, product_id))
                else:
                    cur.execute("""
                        INSERT INTO products (name,ram,cpu,disk,price,active,sort_order)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """, (name, ram, cpu, disk, price, active, sort_order))
            conn.commit()
        finally:
            conn.close()

def delete_product(product_id: int):
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
            conn.commit()
        finally:
            conn.close()

def get_product(product_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products WHERE id=%s", (product_id,))
            return cur.fetchone()
    finally:
        conn.close()

# ─── Orders ───────────────────────────────────────────────────────────────────

def create_order(telegram_id, username, package_id, package_name, amount, egg_type="nodejs"):
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO orders (telegram_id, username, package_id, package_name, amount, egg_type)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (telegram_id, username, package_id, package_name, amount, egg_type))
                conn.commit()
                return cur.lastrowid
        finally:
            conn.close()

def set_order_payment(order_id, trx_id, payment_url):
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE orders SET trx_id=%s, payment_url=%s WHERE id=%s",
                    (trx_id, payment_url, order_id)
                )
            conn.commit()
        finally:
            conn.close()

def set_order_paid(trx_id, ptero_user_id, ptero_user, ptero_pass, ptero_email, server_id):
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE orders
                    SET status='paid', paid_at=NOW(),
                        expires_at=DATE_ADD(NOW(), INTERVAL 30 DAY),
                        ptero_user_id=%s, ptero_user=%s, ptero_pass=%s,
                        ptero_email=%s, server_id=%s
                    WHERE trx_id=%s
                """, (ptero_user_id, ptero_user, ptero_pass, ptero_email, server_id, trx_id))
            conn.commit()
        finally:
            conn.close()

def get_order_by_trx(trx_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE trx_id=%s", (trx_id,))
            return cur.fetchone()
    finally:
        conn.close()

def get_order(order_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
            return cur.fetchone()
    finally:
        conn.close()

def get_pending_orders():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM orders
                WHERE status='pending' AND created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                ORDER BY created_at DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()

def get_user_orders(telegram_id, limit=5):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM orders WHERE telegram_id=%s
                ORDER BY created_at DESC LIMIT %s
            """, (telegram_id, limit))
            return cur.fetchall()
    finally:
        conn.close()

def expire_old_pending():
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE orders SET status='expired'
                    WHERE status='pending'
                    AND created_at < DATE_SUB(NOW(), INTERVAL 24 HOUR)
                """)
            conn.commit()
        finally:
            conn.close()

def update_egg_type(order_id, egg_type):
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE orders SET egg_type=%s WHERE id=%s", (egg_type, order_id))
            conn.commit()
        finally:
            conn.close()

def get_all_orders(limit=100, status=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if status:
                cur.execute("SELECT * FROM orders WHERE status=%s ORDER BY created_at DESC LIMIT %s",
                            (status, limit))
            else:
                cur.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT %s", (limit,))
            return cur.fetchall()
    finally:
        conn.close()

def get_stats():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(amount),0) as rev FROM orders WHERE status='paid'")
            paid = cur.fetchone()
            cur.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='pending'")
            pend = cur.fetchone()
            cur.execute("SELECT COUNT(DISTINCT telegram_id) as cnt FROM orders WHERE status='paid'")
            buyers = cur.fetchone()
            cur.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='paid' AND paid_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)")
            week = cur.fetchone()
            return {
                "total_orders": paid["cnt"],
                "total_revenue": int(paid["rev"]),
                "pending": pend["cnt"],
                "unique_buyers": buyers["cnt"],
                "week_orders": week["cnt"],
            }
    finally:
        conn.close()

# ─── Users ────────────────────────────────────────────────────────────────────

def upsert_user(telegram_id, username, ptero_user_id=None, ptero_email=None):
    with _lock:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (telegram_id, username, ptero_user_id, ptero_email)
                    VALUES (%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                        username=VALUES(username),
                        ptero_user_id=COALESCE(VALUES(ptero_user_id), ptero_user_id),
                        ptero_email=COALESCE(VALUES(ptero_email), ptero_email)
                """, (telegram_id, username, ptero_user_id, ptero_email))
            conn.commit()
        finally:
            conn.close()

def get_user(telegram_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE telegram_id=%s", (telegram_id,))
            return cur.fetchone()
    finally:
        conn.close()

def get_all_users(limit=200):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.*,
                       COUNT(o.id) as total_orders,
                       COALESCE(SUM(CASE WHEN o.status='paid' THEN o.amount ELSE 0 END),0) as total_spent
                FROM users u
                LEFT JOIN orders o ON u.telegram_id=o.telegram_id
                GROUP BY u.telegram_id
                ORDER BY u.created_at DESC LIMIT %s
            """, (limit,))
            return cur.fetchall()
    finally:
        conn.close()
