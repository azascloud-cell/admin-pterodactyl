"""
Pakasir Payment Gateway Client
API Base: https://app.pakasir.com/api/

Endpoint yang digunakan:
  POST /create   — buat link pembayaran
  GET  /status   — cek status pembayaran
  GET  /transactiondetail — detail transaksi

Callback dari Pakasir: POST ke PAKASIR_CALLBACK_URL
"""
import requests, logging
from bot.config import PAKASIR_API_KEY, PAKASIR_PROJECT, PAKASIR_CALLBACK_URL

log = logging.getLogger(__name__)

BASE = "https://app.pakasir.com/api"

def create_payment(order_id: int, amount: int, note: str) -> dict:
    """
    Buat payment link Pakasir.
    Returns: { "success": bool, "url": str, "trx_id": str, "error": str }
    """
    callback = f"{PAKASIR_CALLBACK_URL}?order_id={order_id}" if PAKASIR_CALLBACK_URL else ""

    payload = {
        "project":      PAKASIR_PROJECT,
        "api_key":      PAKASIR_API_KEY,
        "amount":       amount,
        "note":         note,
        "callback_url": callback,
        "redirect_url": callback,   # redirect setelah bayar
    }

    try:
        # Coba POST JSON dulu
        r = requests.post(f"{BASE}/create", json=payload, timeout=15)
        data = r.json()
        log.debug("Pakasir create response: %s", data)

        # Handle berbagai format respons Pakasir
        if data.get("status") in ("success", "200", True, 1) or data.get("code") == 200:
            d = data.get("data", data)
            return {
                "success": True,
                "url":    d.get("url") or d.get("payment_url") or d.get("link"),
                "trx_id": str(d.get("trx_id") or d.get("id") or d.get("invoice_id") or order_id),
            }

        # Fallback: coba GET query string
        r2 = requests.get(f"{BASE}/create", params=payload, timeout=15)
        data2 = r2.json()
        log.debug("Pakasir create GET response: %s", data2)
        if data2.get("status") in ("success", "200", True, 1) or data2.get("code") == 200:
            d = data2.get("data", data2)
            return {
                "success": True,
                "url":    d.get("url") or d.get("payment_url") or d.get("link"),
                "trx_id": str(d.get("trx_id") or d.get("id") or d.get("invoice_id") or order_id),
            }

        return {"success": False, "error": data.get("message", str(data))}

    except Exception as e:
        log.exception("Pakasir create_payment error")
        return {"success": False, "error": str(e)}


def check_status(trx_id: str) -> dict:
    """
    Cek status pembayaran via Pakasir API.
    Returns: { "paid": bool, "status": str }
    """
    params = {
        "project": PAKASIR_PROJECT,
        "api_key": PAKASIR_API_KEY,
        "trx_id":  trx_id,
    }
    try:
        r = requests.get(f"{BASE}/transactiondetail", params=params, timeout=10)
        data = r.json()
        log.debug("Pakasir status: %s", data)

        d = data.get("data", data)
        status = str(d.get("status", "")).lower()
        paid = status in ("paid", "success", "completed", "settlement", "capture")
        return {"paid": paid, "status": status, "raw": data}
    except Exception as e:
        log.exception("Pakasir check_status error")
        return {"paid": False, "status": "error", "error": str(e)}


def parse_callback(form_data: dict) -> dict:
    """
    Parse data callback/webhook dari Pakasir.
    Normalisasi berbagai format field name.
    Returns: { "trx_id": str, "paid": bool, "amount": int }
    """
    trx_id = (
        form_data.get("trx_id") or
        form_data.get("invoice_id") or
        form_data.get("id") or
        form_data.get("transaction_id") or ""
    )
    status = str(
        form_data.get("status") or
        form_data.get("payment_status") or ""
    ).lower()
    paid   = status in ("paid", "success", "completed", "settlement", "capture")
    amount = int(form_data.get("amount") or form_data.get("nominal") or 0)

    return {"trx_id": str(trx_id), "paid": paid, "status": status, "amount": amount}
