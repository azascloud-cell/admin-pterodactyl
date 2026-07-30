"""
Flask webhook server untuk menerima callback pembayaran dari Pakasir.
Berjalan di thread terpisah dari bot Telegram.
"""
import logging, threading
from flask import Flask, request, jsonify
from bot import pakasir, database as db
from bot.config import PAKASIR_CALLBACK_PATH

log = logging.getLogger(__name__)
app = Flask(__name__)

# Callback yang di-inject dari main.py setelah bot init
_on_paid_callback = None   # async def on_paid(order: dict) -> None

def set_paid_callback(fn):
    global _on_paid_callback
    _on_paid_callback = fn


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "pteroshop-webhook"})


@app.route(PAKASIR_CALLBACK_PATH, methods=["POST", "GET"])
def pakasir_callback():
    """
    Endpoint yang dipanggil Pakasir setelah pembayaran sukses.
    Pakasir biasanya POST form-data atau JSON.
    """
    # Ambil data dari request
    if request.is_json:
        data = request.get_json(force=True) or {}
    else:
        data = request.form.to_dict()
        if not data:
            data = request.args.to_dict()

    log.info("Pakasir callback received: %s", data)

    # Ambil order_id dari query string (kita pasang saat create payment)
    order_id_qs = request.args.get("order_id") or data.get("order_id")

    parsed = pakasir.parse_callback(data)
    trx_id = parsed["trx_id"] or (str(order_id_qs) if order_id_qs else "")

    if not trx_id:
        log.warning("Pakasir callback: no trx_id found in %s", data)
        return jsonify({"status": "ignored", "reason": "no trx_id"}), 200

    if not parsed["paid"]:
        log.info("Pakasir callback: not paid yet (status=%s)", parsed["status"])
        return jsonify({"status": "ok", "paid": False}), 200

    # Cari order berdasarkan trx_id
    order = db.get_order_by_trx(trx_id)

    # Fallback: cari by order_id jika trx_id belum di-set ke DB
    if not order and order_id_qs:
        order = db.get_order(int(order_id_qs))
        if order and not order.get("trx_id"):
            db.set_order_payment(order["id"], trx_id, order.get("payment_url", ""))
            order["trx_id"] = trx_id

    if not order:
        log.warning("Pakasir callback: order not found for trx_id=%s", trx_id)
        return jsonify({"status": "ok", "note": "order not found"}), 200

    if order["status"] == "paid":
        return jsonify({"status": "ok", "note": "already processed"}), 200

    # Jadwalkan pemrosesan di event loop bot (thread-safe)
    if _on_paid_callback:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()

        # Jalankan coroutine dari thread Flask ke event loop bot
        asyncio.run_coroutine_threadsafe(_on_paid_callback(order), loop)
        log.info("Paid order %s queued for processing", order["id"])
    else:
        log.warning("No paid callback registered!")

    return jsonify({"status": "ok", "order_id": order["id"]}), 200


def run_webhook(port: int = 5000):
    """Jalankan Flask di thread daemon."""
    def _run():
        log.info("Webhook server started on port %d", port)
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True, name="webhook-server")
    t.start()
    return t
