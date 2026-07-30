"""
Handler: alur pembelian paket
  menu_beli → pilih_paket → pilih_egg → konfirmasi → bayar
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.config import PACKAGES, get_package, PTERODACTYL_URL
from bot import database as db, pakasir, pterodactyl as ptero

log = logging.getLogger(__name__)


def _fmt_price(p: int) -> str:
    return f"Rp {p:,}".replace(",", ".")


def package_list_markup():
    rows = []
    for pkg in PACKAGES:
        if pkg["ram"] == 0:
            label = f"♾️ {pkg['name']} → {_fmt_price(pkg['price'])}"
        else:
            label = f"📦 {pkg['name']} — {pkg['ram']//1024}GB RAM | CPU {pkg['cpu']}% → {_fmt_price(pkg['price'])}"
        rows.append([InlineKeyboardButton(label, callback_data=f"pkg_{pkg['id']}")])
    rows.append([InlineKeyboardButton("🔙 Kembali", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


async def cmd_beli(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌐 *PANEL PTERODACTYL*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 *Harga Paket (per 30 hari):*\n\n"
        + "\n".join(
            f"   📦 *{p['name']}* — "
            + (f"{p['ram']//1024}GB RAM | CPU {p['cpu']}%" if p['ram'] else "RAM & Disk UNLI | CPU UNLI")
            + f" → *{_fmt_price(p['price'])}*"
            for p in PACKAGES
        )
        + "\n\n_Pilih paket di bawah:_"
    )
    markup = package_list_markup()
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_menu_beli(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await cmd_beli(update, ctx)


async def cb_pkg_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User pilih paket → tampilkan pilihan egg."""
    q = update.callback_query
    await q.answer()
    pkg_id = int(q.data.split("_")[1])
    pkg    = get_package(pkg_id)
    if not pkg:
        await q.answer("Paket tidak ditemukan.", show_alert=True)
        return

    ctx.user_data["pkg_id"] = pkg_id
    ram_str  = f"{pkg['ram']//1024}GB RAM" if pkg["ram"] else "RAM Unlimited"
    cpu_str  = f"CPU {pkg['cpu']}%" if pkg["cpu"] else "CPU Unlimited"
    disk_str = f"Disk {pkg['disk']//1024}GB" if pkg["disk"] else "Disk Unlimited"

    text = (
        f"📦 *{pkg['name']}*\n"
        f"├ {ram_str}\n"
        f"├ {cpu_str}\n"
        f"├ {disk_str}\n"
        f"└ *Harga: {_fmt_price(pkg['price'])}/30 hari*\n\n"
        "🔧 Pilih bahasa / runtime untuk server kamu:"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Node.js", callback_data=f"egg_{pkg_id}_nodejs"),
            InlineKeyboardButton("🐍 Python",  callback_data=f"egg_{pkg_id}_python"),
        ],
        [InlineKeyboardButton("🔙 Pilih Paket Lain", callback_data="menu_beli")],
    ])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_egg_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User pilih egg → buat order + payment link."""
    q = update.callback_query
    await q.answer("⏳ Membuat link pembayaran...")

    _, pkg_id_str, egg_type = q.data.split("_")
    pkg_id = int(pkg_id_str)
    pkg    = get_package(pkg_id)
    if not pkg:
        await q.answer("Paket tidak ditemukan.", show_alert=True)
        return

    user     = q.from_user
    egg_label = "Node.js 🟢" if egg_type == "nodejs" else "Python 🐍"
    note      = f"PteroShop {pkg['name']} ({egg_label}) - @{user.username or user.id}"

    # Buat order di DB
    order_id = db.create_order(
        telegram_id=user.id,
        username=user.username or user.first_name,
        package_id=pkg_id,
        package_name=pkg["name"],
        amount=pkg["price"],
        egg_type=egg_type,
    )

    # Buat payment link Pakasir
    result = pakasir.create_payment(order_id, pkg["price"], note)

    if not result["success"]:
        await q.edit_message_text(
            f"❌ *Gagal membuat link pembayaran.*\n\n`{result.get('error','Unknown error')}`\n\n"
            "Coba lagi atau hubungi admin.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Coba Lagi", callback_data="menu_beli")
            ]])
        )
        return

    # Simpan trx_id & payment_url
    db.set_order_payment(order_id, result["trx_id"], result["url"])

    ram_str  = f"{pkg['ram']//1024}GB RAM" if pkg["ram"] else "RAM Unlimited"
    cpu_str  = f"CPU {pkg['cpu']}%" if pkg["cpu"] else "CPU Unlimited"

    text = (
        f"✅ *Order #{order_id} Dibuat!*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Paket:* {pkg['name']}\n"
        f"🔧 *Runtime:* {egg_label}\n"
        f"💾 {ram_str} | {cpu_str}\n"
        f"💰 *Total: {_fmt_price(pkg['price'])}*\n\n"
        "🔗 *Link Pembayaran:*\n"
        f"{result['url']}\n\n"
        "⏳ Bayar sebelum *24 jam* — order akan expired otomatis.\n"
        "✅ Setelah bayar, data login dikirim ke sini secara otomatis."
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Bayar Sekarang", url=result["url"])],
        [InlineKeyboardButton("🔄 Cek Status Bayar", callback_data=f"cekbayar_{order_id}_{result['trx_id']}")],
        [InlineKeyboardButton("🔙 Menu Utama", callback_data="menu_main")],
    ])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_cek_bayar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Manual check status pembayaran."""
    q = update.callback_query
    await q.answer("⏳ Mengecek status...")
    parts   = q.data.split("_")
    order_id = int(parts[1])
    trx_id   = parts[2]
    order    = db.get_order(order_id)

    if not order:
        await q.answer("Order tidak ditemukan.", show_alert=True)
        return

    if order["status"] == "paid":
        await q.answer("✅ Sudah lunas! Data login sudah dikirim.", show_alert=True)
        return

    # Cek ke Pakasir
    status = pakasir.check_status(trx_id)
    if status["paid"]:
        await _process_paid_order(q, order)
    else:
        await q.answer(
            f"⏳ Belum dibayar (status: {status['status']}). "
            "Selesaikan pembayaran terlebih dahulu.",
            show_alert=True
        )


async def _process_paid_order(q_or_ctx, order: dict):
    """Buat user + server Pterodactyl setelah pembayaran dikonfirmasi."""
    from bot.config import PTERODACTYL_URL

    # Buat user Pterodactyl
    user_result = ptero.create_user(order["telegram_id"], order["username"] or "user")
    if not user_result["success"]:
        log.error("Failed to create ptero user for order %s: %s", order["id"], user_result.get("error"))
        return False

    pkg = get_package(order["package_id"])

    # Buat server
    srv_result = ptero.create_server(
        user_id=user_result["user_id"],
        order_id=order["id"],
        package=pkg,
        egg_type=order["egg_type"],
    )

    server_id = srv_result.get("server_id") if srv_result["success"] else None
    if not srv_result["success"]:
        log.warning("Server creation failed for order %s: %s", order["id"], srv_result.get("error"))

    # Update DB
    db.set_order_paid(
        trx_id=order["trx_id"],
        ptero_user_id=user_result["user_id"],
        ptero_user=user_result["username"],
        ptero_pass=user_result["password"],
        ptero_email=user_result["email"],
        server_id=server_id,
    )
    db.upsert_user(
        order["telegram_id"],
        order["username"],
        user_result["user_id"],
        user_result["email"],
    )

    egg_label = "Node.js 🟢" if order["egg_type"] == "nodejs" else "Python 🐍"
    panel_url = PTERODACTYL_URL

    msg = (
        "🎉 *Pembayaran Dikonfirmasi! Server Aktif!*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 *Paket:* {order['package_name']}\n"
        f"🔧 *Runtime:* {egg_label}\n\n"
        "🔐 *Data Login Panel:*\n"
        f"🌐 URL  : `{panel_url}`\n"
        f"📧 Email: `{user_result['email']}`\n"
        f"👤 User : `{user_result['username']}`\n"
        f"🔑 Pass : `{user_result['password']}`\n\n"
        + (f"🖥️ Server ID: `{server_id}`\n\n" if server_id else "⚠️ Server sedang dibuat manual, hubungi admin.\n\n")
        + "⚠️ *Simpan data ini!* Kamu bisa ganti password setelah login.\n"
        "🔧 Gunakan /gantiegg jika ingin ganti runtime (Node.js/Python)."
    )

    # Kirim ke user via bot context
    try:
        if hasattr(q_or_ctx, "bot"):          # callback query
            await q_or_ctx.bot.send_message(order["telegram_id"], msg, parse_mode="Markdown")
        elif hasattr(q_or_ctx, "message"):    # Update
            await q_or_ctx.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        log.exception("Failed to send paid notification for order %s", order["id"])

    return True


# Export helper untuk dipakai webhook
process_paid_order = _process_paid_order
