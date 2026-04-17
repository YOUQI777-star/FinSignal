"""
screening_service.py
--------------------
Orchestrates the candidate screening pipeline and manages the cache file.

Cache location: data/screening/candidates_cn.json

Public API:
    build_candidates(...)      -> writes cache, returns summary dict
    load_from_cache()          -> reads cache, returns dict or None
    apply_query_filters(...)   -> client-side filtering on cached data
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from backend.config import DATA_DIR
from backend.screening.candidate_rules import (
    DEFAULT_PCT_MAX,
    DEFAULT_PRICE_MAX,
    DEFAULT_SHARE_MAX,
    DEFAULT_TURNOVER_MAX,
    DEFAULT_TURNOVER_MIN,
    apply_rules,
    is_st,
)
from backend.screening.market_loader import fetch_all_spot, fetch_hist_10d

log = logging.getLogger(__name__)

CACHE_PATH = DATA_DIR / "screening" / "candidates_cn.json"


# ---------------------------------------------------------------------------
# Build (called by batch script only — never at request time)
# ---------------------------------------------------------------------------

def build_candidates(
    *,
    turnover_min: float = DEFAULT_TURNOVER_MIN,
    turnover_max: float = DEFAULT_TURNOVER_MAX,
    price_max:    float = DEFAULT_PRICE_MAX,
    share_max:    float = DEFAULT_SHARE_MAX,
    pct_max:      float = DEFAULT_PCT_MAX,
    exclude_st:   bool  = True,
    hist_delay:   float = 0.25,   # seconds between per-stock history calls
) -> dict[str, Any]:
    """
    Full screening pipeline:
      1. Fetch all A-share spot data (single AKShare call)
      2. Pre-filter by price + name (fast, no extra API calls)
      3. For pre-filtered stocks, fetch 10-day history
      4. Apply all 6 rules
      5. Write cache file
    Returns a summary dict.
    """
    spots = fetch_all_spot()
    log.info("Total A-share stocks: %d", len(spots))

    # --- Pre-filter: price < price_max, not ST (cheap checks) ---
    pre_filtered: list[dict] = []
    for s in spots:
        try:
            price = float(s.get("price") or 0)
        except (TypeError, ValueError):
            continue
        import math
        if math.isnan(price) or price <= 0 or price >= price_max:
            continue
        name = str(s.get("name") or "")
        if exclude_st and is_st(name):
            continue
        # Approximate total shares from total market cap / price
        try:
            total_mv = float(s.get("total_mv") or 0)
            total_shares_yi = total_mv / price / 1e8  # 亿 shares
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if total_shares_yi >= share_max:
            continue
        try:
            circ_mv = float(s.get("circ_mv") or 0)
            circ_mv_yi = circ_mv / 1e8           # 亿 yuan
            float_shares_yi = circ_mv / price / 1e8
        except (TypeError, ValueError, ZeroDivisionError):
            circ_mv_yi = None
            float_shares_yi = None

        pre_filtered.append({
            "code":            str(s["code"]).zfill(6),
            "name":            name,
            "market":          "CN",
            "current_price":   round(price, 4),
            "total_shares_yi": round(total_shares_yi, 2),
            "float_shares_yi": round(float_shares_yi, 2) if float_shares_yi is not None else None,
            "circ_mv_yi":      round(circ_mv_yi, 2) if circ_mv_yi is not None else None,
            "is_st":           is_st(name),
            "turnover_today":  s.get("turnover_today"),
            "pct_change_today": s.get("pct_change_today"),
        })

    log.info("Pre-filtered (price + size): %d stocks", len(pre_filtered))

    # --- Fetch history and apply all rules ---
    candidates: list[dict] = []
    total = len(pre_filtered)
    for i, row in enumerate(pre_filtered, 1):
        if i % 50 == 0:
            log.info("  Progress: %d / %d …", i, total)

        hist = fetch_hist_10d(row["code"])
        if hist is None:
            continue

        full_row = {
            **row,
            "avg_turnover_10d": hist["avg_turnover_10d"],
            "max_turnover_10d": hist["max_turnover_10d"],
            "pct_change_10d":   hist["pct_change_10d"],
        }

        passed, matched, reason = apply_rules(
            full_row,
            turnover_min=turnover_min,
            turnover_max=turnover_max,
            price_max=price_max,
            share_max=share_max,
            pct_max=pct_max,
            exclude_st=exclude_st,
        )
        if not passed:
            continue

        candidates.append({
            "code":             full_row["code"],
            "name":             full_row["name"],
            "market":           "CN",
            "current_price":    full_row["current_price"],
            "avg_turnover_10d": full_row["avg_turnover_10d"],
            "max_turnover_10d": full_row["max_turnover_10d"],
            "pct_change_10d":   full_row["pct_change_10d"],
            "total_shares":     full_row["total_shares_yi"],   # 亿
            "float_shares":     full_row["float_shares_yi"],   # 亿, may be None
            "circ_mv":          full_row["circ_mv_yi"],        # 亿 yuan, may be None
            "is_st":            full_row["is_st"],
            "matched_rules":    matched,
            "candidate_reason": reason,
            # candidate_score: v1 uses avg_turnover as sort key
            # future: composite score (volume profile, price structure, etc.)
        })

        time.sleep(hist_delay)

    # Sort by avg turnover descending
    candidates.sort(key=lambda c: c["avg_turnover_10d"], reverse=True)

    cache = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total":        len(candidates),
        "thresholds": {
            "turnover_min": turnover_min,
            "turnover_max": turnover_max,
            "price_max":    price_max,
            "share_max":    share_max,
            "pct_max":      pct_max,
            "exclude_st":   exclude_st,
        },
        "candidates": candidates,
    }

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Use allow_nan=False to catch issues, but first sanitize NaN → None
    import math

    def _sanitize(obj):
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    cache = _sanitize(cache)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Cache written: %s  (%d candidates)", CACHE_PATH, len(candidates))
    return {"total": len(candidates), "generated_at": cache["generated_at"]}


# ---------------------------------------------------------------------------
# Read (called by Flask API — fast, no AKShare)
# ---------------------------------------------------------------------------

def load_from_cache() -> dict[str, Any] | None:
    """Read candidates cache. Returns None if file does not exist."""
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Failed to read candidates cache: %s", exc)
        return None


def apply_query_filters(
    candidates: list[dict],
    *,
    turnover_min: float | None = None,
    turnover_max: float | None = None,
    price_max:    float | None = None,
    share_max:    float | None = None,
    pct_max:      float | None = None,
    exclude_st:   bool         = True,
) -> list[dict]:
    """
    Apply optional additional filters on the cached candidates list.
    All params are optional — None means "no additional constraint".
    """
    out: list[dict] = []
    for c in candidates:
        if exclude_st and c.get("is_st"):
            continue
        if turnover_min is not None and c["avg_turnover_10d"] < turnover_min:
            continue
        if turnover_max is not None and c["max_turnover_10d"] >= turnover_max:
            continue
        if price_max is not None and c["current_price"] >= price_max:
            continue
        if share_max is not None and c["total_shares"] >= share_max:
            continue
        if pct_max is not None and c["pct_change_10d"] >= pct_max:
            continue
        out.append(c)
    return out
