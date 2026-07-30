"""
Handler: perintah admin
/admin       — menu admin
/setconfig   — set konfigurasi (egg IDs, location, node)
/orders      — list semua order
/confirm <trx_id> — konfirmasi pembayaran manual
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.config import BOT_OWNER_ID
from bot import database as db
from bot.handlers.buy import process_paid_order

log = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return BOT_OWNER_ID != 0 and user_id == BOT_OWNER_ID


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = (
        "🛠️ *Admin Panel*\n\n"
        "/orders — list semua order\n"
        "/confirm `<trx_id>` — konfirmasi bayar manual\n"
        "/setconfig — lihat konfigurasi aktif\n"
        "/stats — statistik penjualan"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    pending = db.get_pending_orders()
    if not pending:
        await update.message.reply_text("✅ Tidak ada order pending.")
        return
    lines = [f"📋 *Pending Orders ({len(pending)}):*\n"]
    for o in pending[:20]:
        lines.append(
            f"• *#{o['id']}* TG:`{o['telegram_id']}` — {o['package_name']}\n"
            f"  💰 Rp {o['amount']:,} | trx: `{o.get('trx_id','—')}`\n"
            f"  {o['created_at']}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi pembayaran manual: /confirm <trx_id>"""
    if not is_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /confirm <trx_id>")
        return

    trx_id = ctx.args[0]
    order  = db.get_order_by_trx(trx_id)
    if not order:
        await update.message.reply_text(f"❌ Order dengan trx_id `{trx_id}` tidak ditemukan.",
                                        parse_mode="Markdown")
        return
    if order["status"] == "paid":
        await update.message.reply_text("✅ Order ini sudah lunas.")
        return

    await update.message.reply_text(f"⏳ Memproses order #{order['id']}...")
    ok = await process_paid_order(update, order)
    if ok:
        await update.message.reply_text(f"✅ Order #{order['id']} berhasil diproses! Credentials dikirim ke user.")
    else:
        await update.message.reply_text(f"❌ Gagal proses order #{order['id']}. Cek log.")


async def cmd_setconfig(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    import bot.config as cfg
    text = (
        "⚙️ *Konfigurasi Aktif:*\n\n"
        f"Panel URL  : `{cfg.PTERODACTYL_URL}`\n"
        f"Node.js Egg: `{cfg.NODEJS_EGG_ID}`\n"
        f"Python Egg : `{cfg.PYTHON_EGG_ID}`\n"
        f"Location   : `{cfg.DEFAULT_LOCATION}`\n"
        f"Node       : `{cfg.DEFAULT_NODE}`\n"
        f"Callback   : `{cfg.PAKASIR_CALLBACK_URL or 'Tidak dikonfigurasi'}`\n\n"
        "Untuk ganti, set environment variable:\n"
        "`NODEJS_EGG_ID`, `PYTHON_EGG_ID`, `DEFAULT_LOCATION_ID`, `DEFAULT_NODE_ID`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = db.get_conn()
    total  = conn.execute("SELECT COUNT(*) FROM orders WHERE status='paid'").fetchone()[0]
    rev    = conn.execute("SELECT SUM(amount) FROM orders WHERE status='paid'").fetchone()[0] or 0
    pend   = conn.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]
    users  = conn.execute("SELECT COUNT(DISTINCT telegram_id) FROM orders WHERE status='paid'").fetchone()[0]
    conn.close()
    await update.message.reply_text(
        f"📊 *Statistik PteroShop*\n\n"
        f"✅ Total penjualan : *{total}* order\n"
        f"💰 Total revenue   : *Rp {rev:,.0f}*\n"
        f"⏳ Order pending   : *{pend}*\n"
        f"👥 Unique buyers   : *{users}*",
        parse_mode="Markdown"
    )
