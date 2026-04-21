from __future__ import annotations

import logging
import os
import threading

from backend.data_access.turnover_history_store import TurnoverHistoryStore
from backend.screening.market_loader import get_last_trading_date
from backend.screening.screening_service import get_candidates

log = logging.getLogger(__name__)

_startup_lock = threading.Lock()
_startup_started = False


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _needs_daily_snapshot(store: TurnoverHistoryStore, trading_date: str) -> bool:
    stats = store.date_stats("CN", trading_date)
    total_rows = stats.get("total_rows", 0)
    complete_rows = stats.get("complete_rows", 0)
    if total_rows < 3000:
        return True
    if complete_rows < max(int(total_rows * 0.75), 2500):
        return True
    return False


def _run_startup_snapshot_guard() -> None:
    if not _env_flag("STARTUP_CAPTURE_SNAPSHOT", True):
        log.info("[startup] STARTUP_CAPTURE_SNAPSHOT disabled; skip.")
        return

    store = TurnoverHistoryStore()
    try:
        trading_date = get_last_trading_date()
    except Exception as exc:
        log.warning("[startup] Unable to resolve last trading date: %s", exc)
        return

    try:
        latest_snapshot = store.get_meta("cn_latest_snapshot_date")
        needs_refresh = latest_snapshot != trading_date or _needs_daily_snapshot(store, trading_date)
        if not needs_refresh:
            log.info("[startup] CN snapshot already ready for %s.", trading_date)
            return

        log.info("[startup] Capturing CN turnover snapshot for %s …", trading_date)
        result = get_candidates(force_refresh=True)
        final_date = str(result.get("trading_date") or "")
        stats = store.date_stats("CN", final_date) if final_date else {}
        log.info("[startup] Snapshot ready for %s: %s", final_date or trading_date, stats)
    except Exception as exc:
        log.warning("[startup] Snapshot guard failed (non-fatal): %s", exc)


def start_background_maintenance() -> None:
    global _startup_started
    with _startup_lock:
        if _startup_started:
            return
        _startup_started = True
    threading.Thread(
        target=_run_startup_snapshot_guard,
        daemon=True,
        name="startup-maintenance",
    ).start()
