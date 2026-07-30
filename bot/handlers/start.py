"""
Handler: /start, /help, menu utama
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.config import PACKAGES
from bot import database as db


WELCOME = """🦕 *Selamat datang di PteroShop Bot!*

Jual beli hosting panel Pterodactyl — murah, otomatis, langsung aktif setelah bayar.

Pilih menu di bawah untuk mulai:"""


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Beli Paket", callback_data="menu_beli")],
        [InlineKeyboardButton("📦 Pesanan Saya", callback_data="menu_pesanan")],
        [InlineKeyboardButton("🔧 Ganti Egg",   callback_data="menu_gantiegg")],
        [InlineKeyboardButton("ℹ️ Cara Pakai",   callback_data="menu_help")],
    ])


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username or user.first_name)
    await update.message.reply_text(WELCOME, parse_mode="Markdown", reply_markup=main_menu())


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Cara Pakai PteroShop*\n\n"
        "1️⃣ Ketik /beli atau tekan *Beli Paket*\n"
        "2️⃣ Pilih paket yang kamu mau\n"
        "3️⃣ Pilih bahasa: *Node.js* atau *Python*\n"
        "4️⃣ Bayar via link QRIS / VA yang muncul\n"
        "5️⃣ Setelah bayar, data login dikirim otomatis ke sini\n\n"
        "🔧 *Ganti Egg*\n"
        "Kalau salah pilih bahasa, gunakan /gantiegg untuk ganti.\n\n"
        "📞 *Butuh bantuan?* Hubungi admin."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())


async def cb_menu_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = (
        "📖 *Cara Pakai PteroShop*\n\n"
        "1️⃣ Tekan *Beli Paket* → pilih paket → pilih bahasa\n"
        "2️⃣ Bayar via link yang muncul (QRIS/VA)\n"
        "3️⃣ Data login Pterodactyl dikirim otomatis setelah pembayaran dikonfirmasi\n\n"
        "🔧 Gunakan *Ganti Egg* jika ingin ganti bahasa setelah beli.\n"
        "📦 Cek *Pesanan Saya* untuk melihat status order."
    )
    await q.edit_message_text(text, parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup([
                                  [InlineKeyboardButton("🔙 Kembali", callback_data="menu_main")]
                              ]))


async def cb_menu_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(WELCOME, parse_mode="Markdown", reply_markup=main_menu())
