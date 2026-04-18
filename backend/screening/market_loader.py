"""
market_loader.py
----------------
Fetch A-share realtime spot data from AKShare in a single call.

fetch_realtime_spots() -> list[dict]
    One call, returns all ~5800 A-share stocks with today's metrics.
    Fields: code, name, price, turnover, circ_mv, total_mv, pct_change

get_last_trading_date() -> str
    Returns the most recent A-share trading date as "YYYY-MM-DD".
    Uses AKShare's Sina trading calendar (cached 24h).
    Falls back to skipping weekends if calendar fetch fails.
"""
from __future__ import annotations

import logging
import math
import time as _time
from datetime import date, timedelta
from typing import Any

log = logging.getLogger(__name__)

try:
    import akshare as ak
    _AK_AVAILABLE = True
except Exception:
    ak = None
    _AK_AVAILABLE = False


def ak_available() -> bool:
    return _AK_AVAILABLE


# ── Trading calendar cache ────────────────────────────────────────────────────
_TRADE_DATES: list[str] = []          # sorted "YYYY-MM-DD" strings
_TRADE_DATES_AT: float  = 0.0        # time.monotonic() of last fetch
_TRADE_DATES_TTL        = 24 * 3600  # refresh once per day


def get_last_trading_date() -> str:
    """
    Return the most recent A-share trading date as "YYYY-MM-DD".
    Fetches the Sina trading calendar via AKShare (cached 24 h).
    Falls back to walking backwards and skipping weekends if the API fails.
    """
    global _TRADE_DATES, _TRADE_DATES_AT

    today     = date.today()
    today_str = today.isoformat()

    if _AK_AVAILABLE:
        now = _time.monotonic()
        if not _TRADE_DATES or (now - _TRADE_DATES_AT) > _TRADE_DATES_TTL:
            try:
                df   = ak.tool_trade_date_hist_sina()
                col  = df.columns[0]
                _TRADE_DATES    = sorted(str(d)[:10] for d in df[col].tolist())
                _TRADE_DATES_AT = now
                log.info("Loaded %d trading dates from AKShare calendar", len(_TRADE_DATES))
            except Exception as exc:
                log.warning("Trading calendar fetch failed (will use weekend fallback): %s", exc)

        if _TRADE_DATES:
            # last element <= today
            past = [d for d in _TRADE_DATES if d <= today_str]
            if past:
                return past[-1]

    # Fallback: walk backwards skipping Sat/Sun (ignores CN public holidays)
    d = today
    for _ in range(7):
        if d.weekday() < 5:   # Mon=0 … Fri=4
            return d.isoformat()
        d -= timedelta(days=1)
    return today_str


def fetch_realtime_spots() -> list[dict[str, Any]]:
    """
    Single AKShare call → all A-share spot data.
    Returns list of dicts with normalised field names.
    Raises RuntimeError if AKShare not installed.
    Raises Exception (pass-through) if network fails.
    """
    if not _AK_AVAILABLE:
        raise RuntimeError("AKShare not installed — run: pip install akshare")

    log.info("Fetching realtime A-share spot data …")
    df = ak.stock_zh_a_spot_em()

    col_map = {
        "代码":   "code",
        "名称":   "name",
        "最新价": "price",
        "换手率": "turnover",      # today's turnover %
        "流通市值": "circ_mv",     # 元
        "总市值":   "total_mv",    # 元
        "涨跌幅":   "pct_change",  # today's % change
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    needed = ["code", "name", "price", "turnover", "circ_mv", "total_mv", "pct_change"]
    for col in needed:
        if col not in df.columns:
            df[col] = None

    def _safe(v) -> float | None:
        try:
            f = float(v)
            return None if math.isnan(f) else f
        except (TypeError, ValueError):
            return None

    records = []
    for row in df[needed].itertuples(index=False):
        records.append({
            "code":       str(row.code).zfill(6),
            "name":       str(row.name or ""),
            "price":      _safe(row.price),
            "turnover":   _safe(row.turnover),
            "circ_mv":    _safe(row.circ_mv),
            "total_mv":   _safe(row.total_mv),
            "pct_change": _safe(row.pct_change),
        })

    log.info("  %d stocks received", len(records))
    return records
