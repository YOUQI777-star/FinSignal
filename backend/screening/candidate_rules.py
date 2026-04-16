"""
candidate_rules.py
------------------
Stateless filter logic for the candidates screening feature.

All six v1 conditions are AND-connected:
  C1  avg_turnover_10d > turnover_min  (default 1%)
  C2  max_turnover_10d < turnover_max  (default 10%)
  C3  current_price    < price_max     (default 5 yuan)
  C4  total_shares_yi  < share_max     (default 30 亿)
  C5  pct_change_10d   < pct_max       (default 15%)
  C6  not ST / *ST

A candidate passes only when ALL conditions are met.
`matched_rules` reports which C1/C3/C4 stand out as "interesting" signals
(not redundant info — just the distinguishing positives).
"""
from __future__ import annotations

import re

# Default thresholds (can be overridden per call)
DEFAULT_TURNOVER_MIN  = 1.0    # avg daily turnover > 1%
DEFAULT_TURNOVER_MAX  = 10.0   # max single-day turnover < 10%
DEFAULT_PRICE_MAX     = 5.0    # current price < 5 yuan
DEFAULT_SHARE_MAX     = 30.0   # total shares < 30 亿
DEFAULT_PCT_MAX       = 15.0   # 10-day gain < 15%
DEFAULT_EXCLUDE_ST    = True


_ST_PATTERN = re.compile(r"(^|\*)ST", re.IGNORECASE)


def is_st(name: str) -> bool:
    """Return True if the stock name indicates ST or *ST status."""
    return bool(_ST_PATTERN.search(name or ""))


def apply_rules(
    row: dict,
    *,
    turnover_min: float = DEFAULT_TURNOVER_MIN,
    turnover_max: float = DEFAULT_TURNOVER_MAX,
    price_max:    float = DEFAULT_PRICE_MAX,
    share_max:    float = DEFAULT_SHARE_MAX,
    pct_max:      float = DEFAULT_PCT_MAX,
    exclude_st:   bool  = DEFAULT_EXCLUDE_ST,
) -> tuple[bool, list[str], str]:
    """
    Apply all candidate rules to one stock row.

    row must contain:
        name, current_price, avg_turnover_10d, max_turnover_10d,
        pct_change_10d, total_shares_yi, is_st

    Returns:
        (passed: bool, matched_rules: list[str], candidate_reason: str)
    """
    name             = row.get("name", "")
    price            = row.get("current_price")
    avg_to           = row.get("avg_turnover_10d")
    max_to           = row.get("max_turnover_10d")
    pct              = row.get("pct_change_10d")
    shares           = row.get("total_shares_yi")
    stock_is_st      = row.get("is_st", False)

    # Guard: skip rows with missing critical fields
    if any(v is None for v in [price, avg_to, max_to, pct, shares]):
        return False, [], "数据缺失"

    failures: list[str] = []

    if exclude_st and stock_is_st:
        failures.append("ST")
    if avg_to <= turnover_min:
        failures.append(f"日均换手{avg_to:.2f}%≤{turnover_min}%")
    if max_to >= turnover_max:
        failures.append(f"单日换手{max_to:.2f}%≥{turnover_max}%")
    if price >= price_max:
        failures.append(f"价格{price:.2f}≥{price_max}元")
    if shares >= share_max:
        failures.append(f"股本{shares:.1f}亿≥{share_max}亿")
    if pct >= pct_max:
        failures.append(f"10日涨幅{pct:.1f}%≥{pct_max}%")

    if failures:
        return False, [], ""

    # Build matched_rules (the interesting positives)
    matched: list[str] = []
    if avg_to > turnover_min:
        matched.append("active_turnover")
    if price < price_max:
        matched.append("low_price")
    if shares < share_max:
        matched.append("small_cap")

    reason_parts = [
        f"日均换手{avg_to:.2f}%",
        f"现价{price:.2f}元",
        f"总股本{shares:.1f}亿",
    ]
    if pct >= 0:
        reason_parts.append(f"10日+{pct:.1f}%")
    else:
        reason_parts.append(f"10日{pct:.1f}%")

    return True, matched, " · ".join(reason_parts)
