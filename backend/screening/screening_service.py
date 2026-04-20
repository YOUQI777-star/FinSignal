"""
screening_service.py
--------------------
Realtime candidates screening — single AKShare call, in-memory cache.

Cache TTL: 30 minutes. First request of the day takes ~30-60s;
subsequent requests within the TTL window return instantly.

Public API:
    get_candidates(filters)  -> dict   always returns fresh-ish data
    apply_query_filters(...)  -> list  narrow results in memory
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from backend.data_access.turnover_history_store import TurnoverHistoryStore
from backend.screening.candidate_scoring import clear_candidate_score_caches
from backend.screening.candidate_rules import (
    DEFAULT_CIRC_MV_MAX,
    DEFAULT_EXCLUDE_ST,
    DEFAULT_PCT_MAX,
    DEFAULT_PCT_MIN,
    DEFAULT_PRICE_MAX,
    DEFAULT_TURNOVER_MIN,
    apply_rules,
    is_st,
)
from backend.screening.market_loader import fetch_realtime_spots, get_last_trading_date

log = logging.getLogger(__name__)

# ── In-memory cache ───────────────────────────────────────────────────────────
_CACHE_TTL_SECONDS = 30 * 60   # 30 minutes

_cache_lock       = threading.Lock()
_cached_result:   dict | None = None
_cache_fetched_at: float      = 0.0   # time.monotonic()
history_store = TurnoverHistoryStore()


def _cache_fresh() -> bool:
    return (
        _cached_result is not None
        and (time.monotonic() - _cache_fetched_at) < _CACHE_TTL_SECONDS
    )


# ── Core screening ────────────────────────────────────────────────────────────

def _run_screening(
    turnover_min: float,
    price_max:    float,
    circ_mv_max:  float,
    pct_max:      float,
    pct_min:      float,
    exclude_st:   bool,
) -> dict[str, Any]:
    """Fetch spots + apply rules. Returns full result dict."""
    spots = fetch_realtime_spots()
    trading_date = get_last_trading_date()
    generated_at = datetime.now(timezone.utc).isoformat()
    history_store.upsert_daily_rows("CN", trading_date, spots, updated_at=generated_at)
    clear_candidate_score_caches()
    log.info("Screening %d stocks …", len(spots))

    candidates = []
    skipped_data = 0

    for s in spots:
        price    = s["price"]
        turnover = s["turnover"]
        circ_mv  = s["circ_mv"]
        pct      = s["pct_change"]
        name     = s["name"]

        # Derive circ_mv in 亿
        circ_mv_yi: float | None = None
        if circ_mv is not None and price and price > 0:
            circ_mv_yi = round(circ_mv / 1e8, 2)

        # Derive total_shares in 亿 from total_mv
        total_mv   = s["total_mv"]
        total_sh_yi: float | None = None
        if total_mv is not None and price and price > 0:
            total_sh_yi = round(total_mv / price / 1e8, 2)

        row = {
            "name":      name,
            "price":     price,
            "turnover":  turnover,
            "circ_mv_yi": circ_mv_yi,
            "pct_change": pct,
            "is_st":     is_st(name),
        }

        passed, matched, reason = apply_rules(
            row,
            turnover_min=turnover_min,
            price_max=price_max,
            circ_mv_max=circ_mv_max,
            pct_max=pct_max,
            pct_min=pct_min,
            exclude_st=exclude_st,
        )

        if reason == "数据缺失":
            skipped_data += 1

        if not passed:
            continue

        candidates.append({
            "code":             s["code"],
            "name":             name,
            "market":           "CN",
            "current_price":    price,
            "turnover":         turnover,       # today's %
            "pct_change":       pct,            # today's %
            "circ_mv":          circ_mv_yi,     # 亿
            "total_shares":     total_sh_yi,    # 亿 (approx)
            "is_st":            is_st(name),
            "matched_rules":    matched,
            "candidate_reason": reason,
        })

    # Sort by turnover descending
    candidates.sort(key=lambda c: c["turnover"] or 0, reverse=True)

    log.info(
        "Screening done: %d candidates (skipped %d for missing data)",
        len(candidates), skipped_data,
    )
    return {
        "generated_at": generated_at,
        "trading_date": trading_date,   # e.g. "2026-04-17"
        "source":       "realtime",
        "total":        len(candidates),
        "thresholds": {
            "turnover_min": turnover_min,
            "price_max":    price_max,
            "circ_mv_max":  circ_mv_max,
            "pct_max":      pct_max,
            "pct_min":      pct_min,
            "exclude_st":   exclude_st,
        },
        "candidates": candidates,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_candidates(
    *,
    turnover_min: float = DEFAULT_TURNOVER_MIN,
    price_max:    float = DEFAULT_PRICE_MAX,
    circ_mv_max:  float = DEFAULT_CIRC_MV_MAX,
    pct_max:      float = DEFAULT_PCT_MAX,
    pct_min:      float = DEFAULT_PCT_MIN,
    exclude_st:   bool  = DEFAULT_EXCLUDE_ST,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Return candidate pool. Uses in-memory cache (TTL 30 min).
    Thread-safe: concurrent requests wait for the first fetch to complete.
    """
    global _cached_result, _cache_fetched_at

    with _cache_lock:
        if not force_refresh and _cache_fresh():
            log.debug("Returning cached candidates")
            return _cached_result  # type: ignore[return-value]

        log.info("Cache miss — fetching realtime data …")
        result = _run_screening(
            turnover_min=turnover_min,
            price_max=price_max,
            circ_mv_max=circ_mv_max,
            pct_max=pct_max,
            pct_min=pct_min,
            exclude_st=exclude_st,
        )
        _cached_result    = result
        _cache_fetched_at = time.monotonic()
        return result


def apply_query_filters(
    candidates: list[dict],
    *,
    turnover_min: float | None = None,
    turnover_max: float | None = None,
    price_max:    float | None = None,
    circ_mv_max:  float | None = None,
    pct_max:      float | None = None,
    pct_min:      float | None = None,
    exclude_st:   bool         = True,
) -> list[dict]:
    """Narrow the cached list with optional tighter per-request constraints."""
    out = []
    for c in candidates:
        if exclude_st and c.get("is_st"):
            continue
        if turnover_min is not None and (c["turnover"] or 0) < turnover_min:
            continue
        if turnover_max is not None and (c["turnover"] or 0) > turnover_max:
            continue
        if price_max is not None and (c["current_price"] or 0) >= price_max:
            continue
        if circ_mv_max is not None and c["circ_mv"] is not None and c["circ_mv"] >= circ_mv_max:
            continue
        if pct_max is not None and (c["pct_change"] or 0) >= pct_max:
            continue
        if pct_min is not None and (c["pct_change"] or 0) <= pct_min:
            continue
        out.append(c)
    return out
