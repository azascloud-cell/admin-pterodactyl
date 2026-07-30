"""
PteroShop Bot — Entry Point
Telegram bot jualan hosting Pterodactyl dengan pembayaran via Pakasir.
Juga menjalankan Panel Admin Web (Flask) di port 8080.
"""
import asyncio, logging, os
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)
from bot.config import TELEGRAM_BOT_TOKEN, BOT_OWNER_ID, PAKASIR_CALLBACK_URL, ADMIN_PANEL_PORT
from bot import database as db
from bot.handlers import start, buy, server, admin
from bot.handlers.buy import process_paid_order
from bot import webhook as wh
from bot import scheduler as sched
from panel_admin.app import run_panel

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


async def on_paid(order: dict):
    """Dipanggil saat pembayaran dikonfirmasi (dari webhook atau polling)."""
    log.info("Processing paid order #%s for user %s", order["id"], order["telegram_id"])
    app = _app
    try:
        await app.bot.send_message(
            order["telegram_id"],
            "✅ *Pembayaran diterima! Sedang menyiapkan server kamu...*",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await process_paid_order(app.bot, order)


_app = None   # Global app reference (set saat run)


def build_app() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ── Commands ─────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",     start.cmd_start))
    app.add_handler(CommandHandler("help",      start.cmd_help))
    app.add_handler(CommandHandler("beli",      buy.cmd_beli))
    app.add_handler(CommandHandler("pesanan",   server.cmd_pesanan))
    app.add_handler(CommandHandler("gantiegg",  server.cmd_gantiegg))
    app.add_handler(CommandHandler("admin",     admin.cmd_admin))
    app.add_handler(CommandHandler("orders",    admin.cmd_orders))
    app.add_handler(CommandHandler("confirm",   admin.cmd_confirm))
    app.add_handler(CommandHandler("setconfig", admin.cmd_setconfig))
    app.add_handler(CommandHandler("stats",     admin.cmd_stats))

    # ── Callback Queries ──────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(start.cb_menu_main,       pattern="^menu_main$"))
    app.add_handler(CallbackQueryHandler(start.cb_menu_help,       pattern="^menu_help$"))
    app.add_handler(CallbackQueryHandler(buy.cb_menu_beli,         pattern="^menu_beli$"))
    app.add_handler(CallbackQueryHandler(server.cb_menu_pesanan,   pattern="^menu_pesanan$"))
    app.add_handler(CallbackQueryHandler(server.cb_menu_gantiegg,  pattern="^menu_gantiegg$"))
    app.add_handler(CallbackQueryHandler(buy.cb_pkg_select,        pattern=r"^pkg_\d+$"))
    app.add_handler(CallbackQueryHandler(buy.cb_egg_select,        pattern=r"^egg_\d+_(nodejs|python)$"))
    app.add_handler(CallbackQueryHandler(buy.cb_cek_bayar,         pattern=r"^cekbayar_\d+_.+$"))
    app.add_handler(CallbackQueryHandler(server.cb_gantiegg_select,pattern=r"^gantiegg_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(server.cb_doegg,          pattern=r"^doegg_\d+_\d+_(nodejs|python)$"))

    return app


async def main():
    global _app

    # Init DB
    db.init_db()
    log.info("Database initialized (MySQL)")

    # Jalankan Panel Admin Web di background (port 8080)
    run_panel(ADMIN_PANEL_PORT)
    log.info("Panel Admin Web running on port %d", ADMIN_PANEL_PORT)

    # Bangun aplikasi bot
    _app = build_app()

    # Pasang callback ke webhook & scheduler
    wh.set_paid_callback(on_paid)
    sched.set_paid_callback(on_paid)

    # Jalankan webhook server (Flask, port 5000, thread daemon)
    wh.run_webhook(port=5000)
    log.info("Webhook server running on port 5000")
    if PAKASIR_CALLBACK_URL:
        log.info("Pakasir callback URL: %s", PAKASIR_CALLBACK_URL)
    else:
        log.warning("PAKASIR_CALLBACK_URL kosong — webhook dari Pakasir tidak akan diterima.")

    # Jalankan scheduler di background
    asyncio.create_task(sched.run_scheduler())
    log.info("Scheduler started (polling setiap 60 detik)")

    # Info startup
    me = await _app.bot.get_me()
    log.info("Bot started: @%s (id=%s)", me.username, me.id)
    if BOT_OWNER_ID:
        try:
            await _app.bot.send_message(BOT_OWNER_ID,
                f"🚀 *PteroShop Bot Online!*\n@{me.username}\n"
                f"📊 Panel Admin: port `{ADMIN_PANEL_PORT}`\n"
                f"Callback: `{PAKASIR_CALLBACK_URL or 'tidak dikonfigurasi'}`",
                parse_mode="Markdown")
        except Exception:
            pass

    # Mulai polling
    await _app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
