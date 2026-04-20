from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any

from backend.data_access.master_store import MasterDataStore
from backend.data_access.turnover_history_store import TurnoverHistoryStore

history_store = TurnoverHistoryStore()
master_store = MasterDataStore()


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _score_turnover_quality(turnover: float | None) -> float:
    if turnover is None:
        return 0.0
    if turnover < 2:
        return 0.0
    if turnover <= 6:
        return 45 + (turnover - 2) * 6
    if turnover <= 15:
        return 69 + (turnover - 6) * 2
    if turnover <= 25:
        return 87 - (turnover - 15) * 1.5
    return max(45.0, 72 - (turnover - 25) * 1.2)


def _score_pct_health(pct_change: float | None) -> float:
    if pct_change is None:
        return 20.0
    abs_pct = abs(pct_change)
    if 0.5 <= pct_change <= 5.5:
        return 90 - abs(3.0 - pct_change) * 8
    if -2.0 <= pct_change < 0.5:
        return 60 - abs_pct * 10
    if 5.5 < pct_change <= 8.5:
        return 58 - (pct_change - 5.5) * 10
    return 18.0


def _score_circ_mv(circ_mv: float | None) -> float:
    if circ_mv is None:
        return 30.0
    if circ_mv <= 15:
        return 55 + circ_mv
    if circ_mv <= 45:
        return 85 - abs(circ_mv - 30) * 1.1
    if circ_mv <= 80:
        return 68 - (circ_mv - 45) * 0.7
    return 20.0


def _avg(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None


@lru_cache(maxsize=8192)
def _cached_history(code: str, history_days: int) -> tuple[dict[str, Any], ...]:
    return tuple(history_store.get_history("CN", code, days=history_days))


@lru_cache(maxsize=8192)
def _cached_company(code: str) -> dict[str, Any]:
    return master_store.get_company("CN", code) or {}


def clear_candidate_score_caches() -> None:
    _cached_history.cache_clear()
    _cached_company.cache_clear()


def build_candidate_metrics(candidate: dict[str, Any], *, history_days: int = 10) -> dict[str, Any]:
    code = str(candidate.get("code") or "").strip()
    history = list(_cached_history(code, history_days))
    turnover_rates = [float(row["turnover_rate"]) for row in history if row.get("turnover_rate") is not None]
    pct_changes = [float(row["pct_change"]) for row in history if row.get("pct_change") is not None]
    closes = [float(row["close"]) for row in history if row.get("close") is not None]

    active_days_5 = sum(1 for rate in turnover_rates[-5:] if rate >= 2.0)
    active_days_10 = sum(1 for rate in turnover_rates if rate >= 2.0)
    avg_turnover_5 = _avg(turnover_rates[-5:])
    avg_turnover_10 = _avg(turnover_rates)
    latest_turnover = turnover_rates[-1] if turnover_rates else candidate.get("turnover")
    latest_close = closes[-1] if closes else candidate.get("current_price")

    turnover_stability = 0.0
    if turnover_rates:
        max_rate = max(turnover_rates)
        min_rate = min(turnover_rates)
        if max_rate > 0:
            turnover_stability = 1 - ((max_rate - min_rate) / max_rate)

    short_return = 0.0
    if len(closes) >= 5 and closes[-5] not in (0, None):
        short_return = ((closes[-1] / closes[-5]) - 1) * 100

    avg_pct_5 = _avg(pct_changes[-5:]) or 0.0
    company = _cached_company(code)

    return {
        "history_days": len(history),
        "industry": company.get("industry"),
        "active_days_5": active_days_5,
        "active_days_10": active_days_10,
        "avg_turnover_5": round(avg_turnover_5, 2) if avg_turnover_5 is not None else None,
        "avg_turnover_10": round(avg_turnover_10, 2) if avg_turnover_10 is not None else None,
        "latest_turnover": round(float(latest_turnover), 2) if latest_turnover is not None else None,
        "turnover_stability": round(turnover_stability, 4),
        "short_return_5d": round(short_return, 2),
        "avg_pct_5": round(avg_pct_5, 2),
        "latest_close": latest_close,
    }


def attach_candidate_scores(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics_by_code: dict[str, dict[str, Any]] = {}
    industries: list[str] = []

    for candidate in candidates:
        metrics = build_candidate_metrics(candidate)
        code = str(candidate.get("code") or "")
        metrics_by_code[code] = metrics
        industry = metrics.get("industry")
        if industry:
            industries.append(str(industry))

    industry_counts = Counter(industries)

    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        code = str(candidate.get("code") or "")
        metrics = metrics_by_code.get(code, {})

        turnover_score = _score_turnover_quality(candidate.get("turnover"))
        pct_score = _score_pct_health(candidate.get("pct_change"))
        circ_mv_score = _score_circ_mv(candidate.get("circ_mv"))

        active_days_5 = int(metrics.get("active_days_5") or 0)
        active_days_10 = int(metrics.get("active_days_10") or 0)
        stability = float(metrics.get("turnover_stability") or 0.0)
        avg_turnover_5 = metrics.get("avg_turnover_5") or 0.0
        latest_turnover = metrics.get("latest_turnover") or candidate.get("turnover") or 0.0
        short_return_5d = float(metrics.get("short_return_5d") or 0.0)

        sustained_score = _clamp(
            active_days_5 * 12
            + active_days_10 * 4
            + stability * 28
            + min(float(avg_turnover_5), 12.0) * 1.5
        )
        structure_score = _clamp(
            50
            + min(max(short_return_5d, -8.0), 12.0) * 3
            + min(float(latest_turnover), 15.0) * 1.2
        )

        industry = metrics.get("industry")
        peer_count = industry_counts.get(str(industry), 0) if industry else 0
        industry_bonus = min(max(peer_count - 1, 0) * 6, 18)

        candidate_score = round(
            turnover_score * 0.28
            + pct_score * 0.14
            + circ_mv_score * 0.10
            + sustained_score * 0.30
            + structure_score * 0.18
            + industry_bonus,
            2,
        )

        enriched.append(
            {
                **candidate,
                "industry": industry,
                "candidate_score": candidate_score,
                "score_breakdown": {
                    "turnover_quality": round(turnover_score, 2),
                    "pct_health": round(pct_score, 2),
                    "circ_mv_fit": round(circ_mv_score, 2),
                    "sustained_activity": round(sustained_score, 2),
                    "structure_strength": round(structure_score, 2),
                    "industry_bonus": round(industry_bonus, 2),
                },
                "history_metrics": metrics,
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
