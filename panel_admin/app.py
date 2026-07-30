"""
Panel Admin Web — Flask app untuk manage PteroShop Bot
Port default: 8080
"""
import os, functools
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from bot import database as db
from bot.config import ADMIN_USERNAME, ADMIN_PASSWORD, SESSION_SECRET, ADMIN_PANEL_PORT

app = Flask(__name__)
app.secret_key = SESSION_SECRET

# ─── Auth ─────────────────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Username atau password salah!", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    stats = db.get_stats()
    orders_recent = db.get_all_orders(limit=10)
    return render_template("dashboard.html", stats=stats, orders=orders_recent)


# ─── Orders ───────────────────────────────────────────────────────────────────

@app.route("/orders")
@login_required
def orders():
    status = request.args.get("status", "")
    all_orders = db.get_all_orders(limit=200, status=status or None)
    return render_template("orders.html", orders=all_orders, filter_status=status)


@app.route("/orders/<int:order_id>/confirm", methods=["POST"])
@login_required
def confirm_order(order_id):
    order = db.get_order(order_id)
    if not order:
        flash("Order tidak ditemukan.", "danger")
        return redirect(url_for("orders"))
    if order["status"] == "paid":
        flash("Order sudah lunas.", "warning")
        return redirect(url_for("orders"))

    # Tandai sebagai paid manual (tanpa buat server — admin confirm manual)
    db.set_order_paid(
        trx_id=order["trx_id"] or f"manual_{order_id}",
        ptero_user_id=order.get("ptero_user_id"),
        ptero_user=order.get("ptero_user") or "-",
        ptero_pass=order.get("ptero_pass") or "-",
        ptero_email=order.get("ptero_email") or "-",
        server_id=order.get("server_id"),
    )
    flash(f"Order #{order_id} dikonfirmasi sebagai paid.", "success")
    return redirect(url_for("orders"))


@app.route("/orders/<int:order_id>/delete", methods=["POST"])
@login_required
def delete_order(order_id):
    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        conn.commit()
    finally:
        conn.close()
    flash(f"Order #{order_id} dihapus.", "success")
    return redirect(url_for("orders"))


# ─── Products ─────────────────────────────────────────────────────────────────

@app.route("/products")
@login_required
def products():
    prods = db.get_products(active_only=False)
    return render_template("products.html", products=prods)


@app.route("/products/add", methods=["GET", "POST"])
@login_required
def product_add():
    if request.method == "POST":
        db.upsert_product(
            name       = request.form["name"],
            ram        = int(request.form.get("ram",  0)),
            cpu        = int(request.form.get("cpu",  0)),
            disk       = int(request.form.get("disk", 0)),
            price      = int(request.form.get("price",0)),
            active     = 1 if request.form.get("active") else 0,
            sort_order = int(request.form.get("sort_order", 0)),
        )
        flash("Produk berhasil ditambahkan.", "success")
        return redirect(url_for("products"))
    return render_template("product_form.html", product=None, action="Tambah")


@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def product_edit(pid):
    prod = db.get_product(pid)
    if not prod:
        flash("Produk tidak ditemukan.", "danger")
        return redirect(url_for("products"))
    if request.method == "POST":
        db.upsert_product(
            name       = request.form["name"],
            ram        = int(request.form.get("ram",  0)),
            cpu        = int(request.form.get("cpu",  0)),
            disk       = int(request.form.get("disk", 0)),
            price      = int(request.form.get("price",0)),
            active     = 1 if request.form.get("active") else 0,
            sort_order = int(request.form.get("sort_order", 0)),
            product_id = pid,
        )
        flash("Produk berhasil diperbarui.", "success")
        return redirect(url_for("products"))
    return render_template("product_form.html", product=prod, action="Edit")


@app.route("/products/<int:pid>/delete", methods=["POST"])
@login_required
def product_delete(pid):
    db.delete_product(pid)
    flash("Produk dihapus.", "success")
    return redirect(url_for("products"))


@app.route("/products/seed", methods=["POST"])
@login_required
def products_seed():
    """Isi tabel products dari DEFAULT_PACKAGES jika masih kosong."""
    from bot.config import DEFAULT_PACKAGES
    existing = db.get_products(active_only=False)
    if existing:
        flash("Produk sudah ada, tidak perlu seed ulang.", "warning")
        return redirect(url_for("products"))
    for i, p in enumerate(DEFAULT_PACKAGES):
        db.upsert_product(p["name"], p["ram"], p["cpu"], p["disk"], p["price"],
                          active=1, sort_order=i)
    flash(f"{len(DEFAULT_PACKAGES)} produk default berhasil ditambahkan.", "success")
    return redirect(url_for("products"))


# ─── Users ────────────────────────────────────────────────────────────────────

@app.route("/users")
@login_required
def users():
    all_users = db.get_all_users(limit=200)
    return render_template("users.html", users=all_users)


# ─── Config ───────────────────────────────────────────────────────────────────

CONFIG_KEYS = [
    ("PTERODACTYL_PANEL_URL",  "URL Panel Pterodactyl",       "text"),
    ("PTERODACTYL_API_KEY",    "API Key Pterodactyl",         "password"),
    ("PAKASIR_API_KEY",        "API Key Pakasir",             "password"),
    ("PAKASIR_PROJECT",        "Slug Proyek Pakasir",         "text"),
    ("NODEJS_EGG_ID",          "Egg ID Node.js",              "number"),
    ("PYTHON_EGG_ID",          "Egg ID Python",               "number"),
    ("DEFAULT_LOCATION_ID",    "Location ID Default",         "number"),
    ("DEFAULT_NODE_ID",        "Node ID Default",             "number"),
    ("BOT_OWNER_ID",           "Telegram ID Owner Bot",       "number"),
    ("PUBLIC_DOMAIN",          "Domain Publik (untuk webhook)","text"),
]


@app.route("/config", methods=["GET", "POST"])
@login_required
def config():
    if request.method == "POST":
        for key, _, _ in CONFIG_KEYS:
            val = request.form.get(key, "").strip()
            if val:
                db.set_config(key, val)
        flash("Konfigurasi disimpan. Restart bot agar perubahan berlaku.", "success")
        return redirect(url_for("config"))

    current = db.get_all_config()
    # Merge dengan env vars sebagai default
    merged = {}
    for key, label, typ in CONFIG_KEYS:
        merged[key] = current.get(key) or os.environ.get(key, "")

    return render_template("config.html", config=merged, config_keys=CONFIG_KEYS)


# ─── API (untuk bot internal) ─────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    try:
        return jsonify(db.get_stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Entry point ──────────────────────────────────────────────────────────────

def run_panel(port: int = None):
    import threading
    p = port or ADMIN_PANEL_PORT
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=p, debug=False, use_reloader=False),
        daemon=True, name="admin-panel"
    )
    t.start()
    return t


if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=ADMIN_PANEL_PORT, debug=False)
