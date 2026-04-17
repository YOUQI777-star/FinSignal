"""
candidate_rules.py
------------------
Stateless filter logic — realtime single-day version.

Conditions (all AND):
  C1  turnover       > turnover_min   today's turnover % > 2%
  C2  price          < price_max      < 20 yuan
  C3  circ_mv_yi     < circ_mv_max    流通市值 < 80 亿
  C4  pct_change     < pct_max        today < +9%   (排除接近涨停)
  C5  pct_change     > pct_min        today > -9%   (排除接近跌停)
  C6  not ST / *ST
"""
from __future__ import annotations

import re

# Defaults
DEFAULT_TURNOVER_MIN  = 2.0    # today turnover > 2%
DEFAULT_PRICE_MAX     = 20.0   # price < 20 yuan
DEFAULT_CIRC_MV_MAX   = 80.0   # 流通市值 < 80 亿
DEFAULT_PCT_MAX       = 9.0    # today gain < 9%
DEFAULT_PCT_MIN       = -9.0   # today drop > -9%
DEFAULT_EXCLUDE_ST    = True

_ST_RE = re.compile(r"(^|\s|\*)[Ss][Tt]")


def is_st(name: str) -> bool:
    return bool(_ST_RE.search(name or ""))


def apply_rules(
    row: dict,
    *,
    turnover_min: float = DEFAULT_TURNOVER_MIN,
    price_max:    float = DEFAULT_PRICE_MAX,
    circ_mv_max:  float = DEFAULT_CIRC_MV_MAX,
    pct_max:      float = DEFAULT_PCT_MAX,
    pct_min:      float = DEFAULT_PCT_MIN,
    exclude_st:   bool  = DEFAULT_EXCLUDE_ST,
) -> tuple[bool, list[str], str]:
    """
    Returns (passed, matched_rules, candidate_reason).
    row fields: name, price, turnover, circ_mv_yi, pct_change, is_st
    """
    price      = row.get("price")
    turnover   = row.get("turnover")
    circ_mv    = row.get("circ_mv_yi")
    pct        = row.get("pct_change")
    stock_is_st = row.get("is_st", False)

    # Skip if any critical field missing
    if any(v is None for v in [price, turnover, circ_mv, pct]):
        return False, [], "数据缺失"

    if exclude_st and stock_is_st:
        return False, [], "ST"
    if turnover <= turnover_min:
        return False, [], f"换手{turnover:.2f}%≤{turnover_min}%"
    if price >= price_max:
        return False, [], f"价格{price:.2f}≥{price_max}元"
    if circ_mv >= circ_mv_max:
        return False, [], f"流通市值{circ_mv:.1f}亿≥{circ_mv_max}亿"
    if pct >= pct_max:
        return False, [], f"涨幅{pct:.1f}%≥{pct_max}%"
    if pct <= pct_min:
        return False, [], f"跌幅{pct:.1f}%≤{pct_min}%"

    matched = ["active_turnover"]
    if price < 10:
        matched.append("low_price")
    if circ_mv < 30:
        matched.append("micro_cap")

    reason = (
        f"换手{turnover:.2f}% · "
        f"现价{price:.2f}元 · "
        f"流通市值{circ_mv:.1f}亿 · "
        f"今日{pct:+.1f}%"
    )
    return True, matched, reason
