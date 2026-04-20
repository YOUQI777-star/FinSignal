from __future__ import annotations

from collections import Counter
from functools import lru_cache
from statistics import median
from typing import Any

from backend.data_access.master_store import MasterDataStore
from backend.data_access.turnover_history_store import TurnoverHistoryStore

history_store = TurnoverHistoryStore()
master_store = MasterDataStore()


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _avg(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None


def _trimmed_mean(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) <= 2:
        return _avg(ordered)
    return _avg(ordered[1:-1])


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_circ_mv_yi(value: Any) -> float | None:
    numeric = _safe_float(value)
    if numeric is None:
        return None
    return round(numeric / 10000, 2) if numeric > 1000 else round(numeric, 2)


@lru_cache(maxsize=8192)
def _cached_history(code: str, history_days: int) -> tuple[dict[str, Any], ...]:
    return tuple(history_store.get_history("CN", code, days=history_days))


@lru_cache(maxsize=8192)
def _cached_company(code: str) -> dict[str, Any]:
    return master_store.get_company("CN", code) or {}


def clear_candidate_score_caches() -> None:
    _cached_history.cache_clear()
    _cached_company.cache_clear()


def _streak(values: list[bool]) -> int:
    longest = 0
    current = 0
    for item in values:
        if item:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _higher_lows(lows: list[float]) -> float:
    if len(lows) < 4:
        return 0.0
    pairs = sum(1 for idx in range(1, len(lows)) if lows[idx] >= lows[idx - 1] * 0.985)
    return pairs / max(len(lows) - 1, 1)


def _higher_highs(highs: list[float]) -> float:
    if len(highs) < 4:
        return 0.0
    pairs = sum(1 for idx in range(1, len(highs)) if highs[idx] >= highs[idx - 1] * 0.99)
    return pairs / max(len(highs) - 1, 1)


def _score_activity(metrics: dict[str, Any]) -> float:
    active_days_10 = metrics.get("active_days_10") or 0
    streak_10 = metrics.get("active_streak_10") or 0
    turnover_median = metrics.get("turnover_median_10") or 0.0
    turnover_trimmed = metrics.get("turnover_trimmed_mean_10") or 0.0
    trend = metrics.get("activity_trend") or 0.0

    return round(_clamp(
        active_days_10 * 6.5
        + streak_10 * 7.5
        + min(turnover_median, 12.0) * 2.2
        + min(turnover_trimmed, 12.0) * 1.8
        + max(min(trend * 18, 16), -10)
        + 6,
    ), 2)


def _score_price_structure(metrics: dict[str, Any]) -> float:
    close_to_20d_high = metrics.get("close_to_20d_high") or 0.0
    close_to_60d_high = metrics.get("close_to_60d_high") or 0.0
    breakout_strength = metrics.get("breakout_strength") or 0.0
    higher_lows = metrics.get("higher_lows_ratio_10") or 0.0
    higher_highs = metrics.get("higher_highs_ratio_10") or 0.0
    ma_alignment = 1.0 if metrics.get("ma_bullish_alignment") else 0.0

    return round(_clamp(
        close_to_20d_high * 26
        + close_to_60d_high * 18
        + breakout_strength * 20
        + higher_lows * 16
        + higher_highs * 12
        + ma_alignment * 8,
    ), 2)


def _score_volume_price(metrics: dict[str, Any]) -> float:
    up_volume_ratio = metrics.get("up_volume_ratio_10") or 0.0
    controlled_pullback_ratio = metrics.get("controlled_pullback_ratio_10") or 0.0
    amount_trend = metrics.get("amount_trend") or 0.0
    heavy_distribution_days = metrics.get("heavy_distribution_days_10") or 0
    long_upper_shadow_days = metrics.get("long_upper_shadow_days_10") or 0

    score = (
        28
        + up_volume_ratio * 28
        + controlled_pullback_ratio * 20
        + max(min(amount_trend * 22, 18), -12)
        - heavy_distribution_days * 10
        - long_upper_shadow_days * 5
    )
    return round(_clamp(score), 2)


def _score_sector_resonance(
    metrics: dict[str, Any],
    *,
    industry_count: int,
    industry_turnover_avg: float,
    industry_pct_avg: float,
    leader_presence: bool,
) -> float:
    own_turnover = metrics.get("latest_turnover") or 0.0
    own_short_return = metrics.get("short_return_5d") or 0.0

    score = (
        min(max(industry_count - 1, 0), 5) * 12
        + min(industry_turnover_avg, 10.0) * 2.4
        + max(min(industry_pct_avg, 5.0), -2.0) * 4.5
        + (10 if leader_presence else 0)
        + (8 if own_turnover >= industry_turnover_avg and own_short_return >= 0 else 0)
    )
    return round(_clamp(score), 2)


def build_candidate_metrics(candidate: dict[str, Any], *, history_days: int = 60) -> dict[str, Any]:
    code = str(candidate.get("code") or "").strip()
    history = list(_cached_history(code, history_days))
    company = _cached_company(code)

    turnover_rates = [_safe_float(row.get("turnover_rate")) for row in history]
    turnover_rates = [value for value in turnover_rates if value is not None]
    pct_changes = [_safe_float(row.get("pct_change")) for row in history]
    pct_changes = [value for value in pct_changes if value is not None]
    closes = [_safe_float(row.get("close")) for row in history]
    closes = [value for value in closes if value is not None]
    highs = [_safe_float(row.get("high")) for row in history]
    highs = [value for value in highs if value is not None]
    lows = [_safe_float(row.get("low")) for row in history]
    lows = [value for value in lows if value is not None]
    amounts = [_safe_float(row.get("amount")) for row in history]
    amounts = [value for value in amounts if value is not None]

    turnover_10 = turnover_rates[-10:]
    turnover_20 = turnover_rates[-20:]
    closes_10 = closes[-10:]
    closes_20 = closes[-20:]
    closes_60 = closes[-60:]
    highs_10 = highs[-10:]
    highs_20 = highs[-20:]
    highs_60 = highs[-60:]
    lows_10 = lows[-10:]
    lows_20 = lows[-20:]
    amounts_10 = amounts[-10:]

    latest_turnover = turnover_rates[-1] if turnover_rates else _safe_float(candidate.get("turnover"))
    latest_close = closes[-1] if closes else _safe_float(candidate.get("current_price")) or _safe_float(candidate.get("close"))
    latest_pct_change = pct_changes[-1] if pct_changes else _safe_float(candidate.get("pct_change"))
    latest_circ_mv = next(
        (_normalize_circ_mv_yi(row.get("circ_mv")) for row in reversed(history) if _normalize_circ_mv_yi(row.get("circ_mv")) is not None),
        _normalize_circ_mv_yi(candidate.get("circ_mv")),
    )

    active_flags_10 = [value >= 2.0 for value in turnover_10]
    active_days_10 = sum(1 for value in active_flags_10 if value)
    active_days_5 = sum(1 for value in turnover_10[-5:] if value >= 2.0)
    active_streak_10 = _streak(active_flags_10)
    turnover_median_10 = median(turnover_10) if turnover_10 else None
    turnover_trimmed_mean_10 = _trimmed_mean(turnover_10)
    first_half_avg = _avg(turnover_10[:5]) or 0.0
    second_half_avg = _avg(turnover_10[-5:]) or 0.0
    activity_trend = ((second_half_avg - first_half_avg) / first_half_avg) if first_half_avg > 0 else (0.35 if second_half_avg > 0 else 0.0)

    high_20 = max(highs_20) if highs_20 else None
    high_60 = max(highs_60) if highs_60 else high_20
    low_20 = min(lows_20) if lows_20 else None
    close_to_20d_high = (latest_close / high_20) if latest_close and high_20 else 0.0
    close_to_60d_high = (latest_close / high_60) if latest_close and high_60 else close_to_20d_high
    range_position_20 = (
        (latest_close - low_20) / (high_20 - low_20)
        if latest_close is not None and low_20 is not None and high_20 not in (None, low_20)
        else 0.0
    )

    recent_high_10 = max(highs_10[:-1]) if len(highs_10) > 1 else high_20
    breakout_strength = (
        (latest_close - recent_high_10) / recent_high_10
        if latest_close is not None and recent_high_10 not in (None, 0)
        else 0.0
    )
    breakout_strength = max(min(breakout_strength * 8 + range_position_20 * 0.6, 1.0), 0.0)

    ma5 = _avg(closes[-5:]) or latest_close or 0.0
    ma10 = _avg(closes[-10:]) or ma5
    ma20 = _avg(closes[-20:]) or ma10
    ma_bullish_alignment = bool(ma5 >= ma10 >= ma20 > 0)

    amount_median_10 = median(amounts_10) if amounts_10 else 0.0
    up_volume_days = 0
    controlled_pullback_days = 0
    heavy_distribution_days = 0
    long_upper_shadow_days = 0

    recent_rows = history[-10:]
    for idx, row in enumerate(recent_rows):
        close = _safe_float(row.get("close"))
        open_ = _safe_float(row.get("open"))
        high = _safe_float(row.get("high"))
        low = _safe_float(row.get("low"))
        amount = _safe_float(row.get("amount")) or 0.0
        pct = _safe_float(row.get("pct_change")) or 0.0
        prev_close = _safe_float(recent_rows[idx - 1].get("close")) if idx > 0 else None
        is_up = (
            close is not None and prev_close is not None and close >= prev_close
        ) or pct > 0
        if is_up and amount >= amount_median_10:
            up_volume_days += 1

        if pct < 0 and amount < amount_median_10 and low is not None:
            support = min(lows_10) if lows_10 else low
            if low >= support * 0.985:
                controlled_pullback_days += 1

        if pct <= -3 and amount >= amount_median_10 * 1.2:
            heavy_distribution_days += 1

        if high is not None and close is not None and open_ is not None and low is not None:
            body_top = max(close, open_)
            full_range = max(high - low, 0.0001)
            upper_shadow = high - body_top
            if upper_shadow / full_range >= 0.45 and pct >= 0:
                long_upper_shadow_days += 1

    amount_first_half = _avg(amounts_10[:5]) or 0.0
    amount_second_half = _avg(amounts_10[-5:]) or 0.0
    amount_trend = ((amount_second_half - amount_first_half) / amount_first_half) if amount_first_half > 0 else 0.0

    short_return = 0.0
    if len(closes) >= 5 and closes[-5] not in (0, None):
        short_return = ((closes[-1] / closes[-5]) - 1) * 100

    return {
        "history_days": len(history),
        "industry": company.get("industry"),
        "active_days_5": active_days_5,
        "active_days_10": active_days_10,
        "active_streak_10": active_streak_10,
        "turnover_median_10": round(float(turnover_median_10), 2) if turnover_median_10 is not None else None,
        "turnover_trimmed_mean_10": round(float(turnover_trimmed_mean_10), 2) if turnover_trimmed_mean_10 is not None else None,
        "activity_trend": round(activity_trend, 4),
        "latest_turnover": round(float(latest_turnover), 2) if latest_turnover is not None else None,
        "latest_close": round(float(latest_close), 2) if latest_close is not None else None,
        "latest_pct_change": round(float(latest_pct_change), 2) if latest_pct_change is not None else None,
        "latest_circ_mv": round(float(latest_circ_mv), 2) if latest_circ_mv is not None else None,
        "close_to_20d_high": round(close_to_20d_high, 4),
        "close_to_60d_high": round(close_to_60d_high, 4),
        "range_position_20": round(range_position_20, 4),
        "breakout_strength": round(breakout_strength, 4),
        "higher_lows_ratio_10": round(_higher_lows(lows_10), 4),
        "higher_highs_ratio_10": round(_higher_highs(highs_10), 4),
        "ma_bullish_alignment": ma_bullish_alignment,
        "up_volume_ratio_10": round(up_volume_days / max(len(recent_rows), 1), 4),
        "controlled_pullback_ratio_10": round(controlled_pullback_days / max(len(recent_rows), 1), 4),
        "heavy_distribution_days_10": heavy_distribution_days,
        "long_upper_shadow_days_10": long_upper_shadow_days,
        "amount_trend": round(amount_trend, 4),
        "short_return_5d": round(short_return, 2),
        "avg_turnover_20": round(_avg(turnover_20) or 0.0, 2),
    }


def attach_candidate_scores(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics_by_code: dict[str, dict[str, Any]] = {}
    industry_stats: dict[str, dict[str, float]] = {}

    industry_bucket: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        metrics = build_candidate_metrics(candidate)
        code = str(candidate.get("code") or "")
        metrics_by_code[code] = metrics
        industry = str(metrics.get("industry") or "").strip()
        if industry:
            industry_bucket.setdefault(industry, []).append({"candidate": candidate, "metrics": metrics})

    for industry, entries in industry_bucket.items():
        turnover_values = [entry["metrics"].get("latest_turnover") or 0.0 for entry in entries]
        pct_values = [entry["metrics"].get("latest_pct_change") or 0.0 for entry in entries]
        leader_presence = any((entry["metrics"].get("short_return_5d") or 0.0) >= 4 for entry in entries)
        industry_stats[industry] = {
            "count": float(len(entries)),
            "turnover_avg": float(_avg(turnover_values) or 0.0),
            "pct_avg": float(_avg(pct_values) or 0.0),
            "leader_presence": 1.0 if leader_presence else 0.0,
        }

    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        code = str(candidate.get("code") or "")
        metrics = metrics_by_code.get(code, {})
        industry = str(metrics.get("industry") or "").strip()
        current_industry_stats = industry_stats.get(
            industry,
            {"count": 1.0, "turnover_avg": metrics.get("latest_turnover") or 0.0, "pct_avg": metrics.get("latest_pct_change") or 0.0, "leader_presence": 0.0},
        )

        activity_score = _score_activity(metrics)
        price_structure_score = _score_price_structure(metrics)
        volume_price_score = _score_volume_price(metrics)
        sector_resonance_score = _score_sector_resonance(
            metrics,
            industry_count=int(current_industry_stats["count"]),
            industry_turnover_avg=float(current_industry_stats["turnover_avg"]),
            industry_pct_avg=float(current_industry_stats["pct_avg"]),
            leader_presence=bool(current_industry_stats["leader_presence"]),
        )

        candidate_score = round(
            activity_score * 0.30
            + price_structure_score * 0.30
            + volume_price_score * 0.25
            + sector_resonance_score * 0.15,
            2,
        )

        enriched.append(
            {
                **candidate,
                "industry": industry,
                "turnover": candidate.get("turnover") if candidate.get("turnover") is not None else metrics.get("latest_turnover"),
                "pct_change": candidate.get("pct_change") if candidate.get("pct_change") is not None else metrics.get("latest_pct_change"),
                "circ_mv": candidate.get("circ_mv") if candidate.get("circ_mv") is not None else metrics.get("latest_circ_mv"),
                "candidate_score": candidate_score,
                "score_model": "structure_v2",
                "score_formula": (
                    f"{candidate_score:.2f} = "
                    f"{activity_score:.1f}×0.30 + "
                    f"{price_structure_score:.1f}×0.30 + "
                    f"{volume_price_score:.1f}×0.25 + "
                    f"{sector_resonance_score:.1f}×0.15"
                ),
                "score_breakdown": {
                    "activity_base": round(activity_score, 2),
                    "price_structure": round(price_structure_score, 2),
                    "volume_price": round(volume_price_score, 2),
                    "sector_resonance": round(sector_resonance_score, 2),
                },
                "history_metrics": {
                    **metrics,
                    "industry_candidate_count": int(current_industry_stats["count"]),
                    "industry_turnover_avg": round(float(current_industry_stats["turnover_avg"]), 2),
                    "industry_pct_avg": round(float(current_industry_stats["pct_avg"]), 2),
                },
            }
        )

    enriched.sort(
        key=lambda item: (
            -(item.get("candidate_score") or 0),
            -(item.get("turnover") or 0),
            item.get("code") or "",
        )
    )
    return enriched
