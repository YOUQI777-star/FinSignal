"""
market_loader.py
----------------
Fetch A-share spot data and 10-day history from AKShare.

Two public functions:
    fetch_all_spot()          -> list[dict]  one entry per stock (current snapshot)
    fetch_hist_10d(code: str) -> dict        10-day metrics for a single stock

AKShare is a required dependency for the run_candidates script.
The Flask API only reads cached JSON, so this module is only imported
by the batch script — not at web-server startup.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any

log = logging.getLogger(__name__)

try:
    import akshare as ak
    _AK_AVAILABLE = True
except Exception:
    ak = None
    _AK_AVAILABLE = False


def _require_ak() -> None:
    if not _AK_AVAILABLE:
        raise RuntimeError("AKShare is not installed. Run: pip install akshare")


def fetch_all_spot() -> list[dict[str, Any]]:
    """
    Single call to ak.stock_zh_a_spot_em().
    Returns list of dicts with keys:
        code, name, price, turnover_today, total_mv, circ_mv, pct_change_today
    total_mv and circ_mv are in yuan (元).
    """
    _require_ak()
    log.info("Fetching all A-share spot data …")
    df = ak.stock_zh_a_spot_em()

    # Defensive: rename columns regardless of minor AKShare version differences
    col_map = {
        "代码": "code",
        "名称": "name",
        "最新价": "price",
        "换手率": "turnover_today",
        "总市值": "total_mv",
        "流通市值": "circ_mv",
        "涨跌幅": "pct_change_today",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    needed = ["code", "name", "price", "turnover_today", "total_mv", "circ_mv", "pct_change_today"]
    for col in needed:
        if col not in df.columns:
            df[col] = None

    records = df[needed].to_dict(orient="records")
    log.info("  %d stocks received", len(records))
    return records


def fetch_hist_10d(code: str, retries: int = 2) -> dict[str, Any] | None:
    """
    Fetch daily OHLCV + turnover for the last ~10 trading days.

    Returns dict:
        avg_turnover_10d   float   mean daily turnover rate (%)
        max_turnover_10d   float   max single-day turnover rate (%)
        pct_change_10d     float   price change over the window (%)
        days               int     actual trading days in window
    Returns None if fetch fails after retries.
    """
    _require_ak()
    end_date   = date.today().strftime("%Y%m%d")
    start_date = (date.today() - timedelta(days=25)).strftime("%Y%m%d")  # ~25 cal days ≥ 10 trading days

    for attempt in range(retries + 1):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="",      # unadjusted — we only need turnover / pct
            )
            if df is None or df.empty:
                return None

            # Normalize column names
            df = df.rename(columns={"换手率": "turnover", "涨跌幅": "pct", "收盘": "close"})
            df = df.tail(10)    # keep last 10 trading days

            turnover = df["turnover"].dropna().astype(float)
            close    = df["close"].dropna().astype(float)

            if turnover.empty or len(close) < 2:
                return None

            pct_change_10d = float((close.iloc[-1] / close.iloc[0] - 1) * 100)

            return {
                "avg_turnover_10d": round(float(turnover.mean()), 4),
                "max_turnover_10d": round(float(turnover.max()),  4),
                "pct_change_10d":   round(pct_change_10d, 4),
                "days":             len(df),
            }
        except Exception as exc:
            if attempt < retries:
                time.sleep(0.5)
            else:
                log.debug("hist fetch failed for %s: %s", code, exc)
                return None
    return None
