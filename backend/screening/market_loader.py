"""
market_loader.py
----------------
Fetch A-share realtime spot data from AKShare in a single call.

fetch_realtime_spots() -> list[dict]
    One call, returns all ~5800 A-share stocks with today's metrics.
    Fields: code, name, price, turnover, circ_mv, total_mv, pct_change
"""
from __future__ import annotations

import logging
import math
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
