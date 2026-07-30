"""
Handler: ganti egg, lihat pesanan, info server
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import database as db, pterodactyl as ptero
from bot.config import PTERODACTYL_URL

log = logging.getLogger(__name__)


# ─── /pesanan — daftar order user ─────────────────────────────────────────────

async def cmd_pesanan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders  = db.get_user_orders(user_id, limit=5)

    if not orders:
        text = "📦 Kamu belum punya pesanan.\n\nGunakan /beli untuk beli paket."
    else:
        lines = ["📦 *Pesanan Terakhir Kamu:*\n"]
        status_emoji = {"pending": "⏳", "paid": "✅", "expired": "❌"}
        for o in orders:
            emoji = status_emoji.get(o["status"], "❓")
            lines.append(
                f"{emoji} *#{o['id']}* — {o['package_name']}\n"
                f"   💰 Rp {o['amount']:,} | {o['egg_type'].upper()}\n"
                f"   Status: `{o['status']}`\n"
                + (f"   Bayar: [Link]({o['payment_url']})\n" if o["status"] == "pending" and o["payment_url"] else "")
            )
        text = "\n".join(lines)

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Menu Utama", callback_data="menu_main")]
    ])
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=markup, disable_web_page_preview=True)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown",
                                                      reply_markup=markup,
                                                      disable_web_page_preview=True)


async def cb_menu_pesanan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await cmd_pesanan(update, ctx)


# ─── /gantiegg — ganti runtime server ────────────────────────────────────────

async def cmd_gantiegg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders  = db.get_user_orders(user_id, limit=10)
    paid    = [o for o in orders if o["status"] == "paid" and o.get("server_id")]

    if not paid:
        text = (
            "🔧 *Ganti Egg (Runtime)*\n\n"
            "Tidak ada server aktif yang bisa diganti egg-nya.\n"
            "Beli paket dulu via /beli"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu Utama", callback_data="menu_main")]])
        if update.message:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
        else:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
        return

    lines  = ["🔧 *Ganti Egg — Pilih Order:*\n"]
    buttons = []
    for o in paid:
        current = "🟢 Node.js" if o["egg_type"] == "nodejs" else "🐍 Python"
        lines.append(f"• *#{o['id']}* {o['package_name']} — saat ini: {current}")
        buttons.append([InlineKeyboardButton(
            f"#{o['id']} — {o['package_name']} ({current})",
            callback_data=f"gantiegg_{o['id']}_{o['server_id']}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Menu Utama", callback_data="menu_main")])

    text   = "\n".join(lines)
    markup = InlineKeyboardMarkup(buttons)
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_menu_gantiegg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await cmd_gantiegg(update, ctx)


async def cb_gantiegg_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tampilkan pilihan egg untuk order tertentu."""
    q        = update.callback_query
    await q.answer()
    parts    = q.data.split("_")
    order_id = int(parts[1])
    server_id = int(parts[2])
    order    = db.get_order(order_id)

    if not order or order["telegram_id"] != q.from_user.id:
        await q.answer("Order tidak ditemukan.", show_alert=True)
        return

    current  = order["egg_type"]
    text = (
        f"🔧 *Ganti Egg — Order #{order_id}*\n\n"
        f"Paket: *{order['package_name']}*\n"
        f"Runtime saat ini: *{'🟢 Node.js' if current == 'nodejs' else '🐍 Python'}*\n\n"
        "Pilih runtime baru:"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Node.js", callback_data=f"doegg_{order_id}_{server_id}_nodejs"),
            InlineKeyboardButton("🐍 Python",  callback_data=f"doegg_{order_id}_{server_id}_python"),
        ],
        [InlineKeyboardButton("🔙 Batal", callback_data="menu_gantiegg")],
    ])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_doegg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Eksekusi ganti egg."""
    q = update.callback_query
    await q.answer("⏳ Mengganti egg...")

    parts     = q.data.split("_")
    order_id  = int(parts[1])
    server_id = int(parts[2])
    new_egg   = parts[3]
    order     = db.get_order(order_id)

    if not order or order["telegram_id"] != q.from_user.id:
        await q.answer("Order tidak ditemukan.", show_alert=True)
        return

    if order["egg_type"] == new_egg:
        await q.answer("Runtime sudah sama, tidak perlu diganti.", show_alert=True)
        return

    result = ptero.update_server_egg(server_id, new_egg)
    if result["success"]:
        db.update_egg_type(order_id, new_egg)
        egg_label = "🟢 Node.js" if new_egg == "nodejs" else "🐍 Python"
        await q.edit_message_text(
            f"✅ *Berhasil!* Runtime server diubah ke *{egg_label}*\n\n"
            f"Server ID: `{server_id}`\n"
            "⚠️ Restart server kamu di panel untuk menerapkan perubahan.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 Buka Panel", url=PTERODACTYL_URL),
                InlineKeyboardButton("🔙 Menu",       callback_data="menu_main"),
            ]])
        )
    else:
        await q.edit_message_text(
            f"❌ *Gagal mengganti egg.*\n\n`{result.get('error', 'Unknown')}`\n\n"
            "Coba lagi atau hubungi admin.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Kembali", callback_data="menu_gantiegg")
            ]])
        )
