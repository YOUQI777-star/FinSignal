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

from backend.scrapers.cn_tushare import TushareCNClient, tushare_available

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


def get_recent_trading_dates(limit: int = 10) -> list[str]:
    """
    Return the most recent A-share trading dates in ascending order.
    """
    latest = get_last_trading_date()
    if _TRADE_DATES:
      past = [d for d in _TRADE_DATES if d <= latest]
      if past:
          return past[-limit:]

    if tushare_available():
        try:
            client = TushareCNClient()
            start = (date.fromisoformat(latest) - timedelta(days=max(limit * 3, 30))).isoformat()
            dates = client.get_trade_dates(start_date=start, end_date=latest)
            if dates:
                return dates[-limit:]
        except Exception as exc:
            log.warning("Tushare trading calendar fetch failed: %s", exc)

    # Fallback: weekdays only
    dates: list[str] = []
    current = date.fromisoformat(latest)
    while len(dates) < limit:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current -= timedelta(days=1)
    return sorted(dates)


def fetch_turnover_history_for_code(
    code: str,
    *,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """
    Fetch historical daily turnover-rate rows for one A-share code.
    """
    if tushare_available():
        try:
            return TushareCNClient().fetch_daily_history(
                code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            log.warning("Tushare history fetch failed for %s (%s → %s): %s", code, start_date, end_date, exc)

    if not _AK_AVAILABLE:
        raise RuntimeError("No CN historical source available — install akshare or configure TUSHARE_TOKEN")

    df = ak.stock_zh_a_hist(
        symbol=str(code).zfill(6),
        period="daily",
        start_date=start_date.replace("-", ""),
        end_date=end_date.replace("-", ""),
        adjust="",
    )
    if df is None or df.empty:
        return []

    date_col = "日期" if "日期" in df.columns else df.columns[0]
    turnover_col = "换手率" if "换手率" in df.columns else None
    if turnover_col is None:
        return []

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        try:
            turnover = float(row.get(turnover_col))
        except (TypeError, ValueError):
            turnover = None
        rows.append({
            "code": str(code).zfill(6),
            "date": str(row.get(date_col))[:10],
            "turnover_rate": turnover,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "pct_change": None,
            "volume": None,
            "amount": None,
            "circ_mv": None,
        })
    return rows


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
