"""
Background scheduler:
- Setiap 60 detik: cek status pembayaran order pending via Pakasir API
- Setiap 1 jam: expire order yang sudah >24 jam
"""
import asyncio, logging
from bot import database as db, pakasir

log = logging.getLogger(__name__)

_on_paid_callback = None

def set_paid_callback(fn):
    global _on_paid_callback
    _on_paid_callback = fn


async def poll_pending_orders():
    """Cek semua order pending ke Pakasir API."""
    orders = db.get_pending_orders()
    if not orders:
        return
    for order in orders:
        trx_id = order.get("trx_id")
        if not trx_id:
            continue
        try:
            status = pakasir.check_status(trx_id)
            if status["paid"]:
                log.info("Polling: order %s is now paid!", order["id"])
                if _on_paid_callback:
                    await _on_paid_callback(order)
        except Exception:
            log.exception("Error polling order %s", order["id"])
        await asyncio.sleep(0.5)   # rate limit


async def run_scheduler():
    """Loop scheduler."""
    tick = 0
    while True:
        await asyncio.sleep(60)
        tick += 1
        try:
            await poll_pending_orders()
        except Exception:
            log.exception("Scheduler poll error")
        if tick % 60 == 0:   # setiap jam
            try:
                db.expire_old_pending()
            except Exception:
                log.exception("Scheduler expire error")
