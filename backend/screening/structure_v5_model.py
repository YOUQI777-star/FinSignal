"""
structure_v5_model.py
---------------------
Early accumulation ranking model based on Conservative_PE50 parameters.
Includes market regime detection and 5-component scoring system.
"""

import logging
import statistics
from typing import Tuple, List, Dict, Optional

log = logging.getLogger(__name__)

# Conservative_PE50 fixed parameters (immutable)
STRUCTURE_V5_PARAMS = {
    "turnover_ratio_threshold": 1.5,
    "today_turnover_max": 8,
    "avg_turnover_20d_max": 3,
    "position_60d_max": 0.7,
    "return_5d_max": 12,
    "pe_max": 30,
    "pb_max": 3,
    "circ_mv_max_yi": 80,
}


def classify_market_regime(
    prices: List[float],
    volumes: Optional[List[float]] = None
) -> Tuple[str, str, float]:
    """
    Classify current market regime based on price trends.

    Args:
        prices: List of historical closing prices (at least 200 points)
        volumes: Optional volume data (not used in basic version)

    Returns:
        (regime, regime_status_text, regime_weight)
        - regime: 'uptrend' | 'sideways' | 'downtrend'
        - regime_status: human-readable description
        - regime_weight: 0.0 (downtrend) | 0.3 (sideways) | 1.0 (uptrend)
    """
    if not prices or len(prices) < 200:
        return "unknown", "Insufficient data for regime classification", 0.5

    # Calculate 200-day SMA
    sma_200 = statistics.mean(prices[-200:])

    # Current price
    current = prices[-1]

    # Recent trend (last 20 days)
    recent_prices = prices[-20:]
    recent_avg = statistics.mean(recent_prices)

    # Volatility (last 60 days)
    volatility_60 = calculate_volatility(prices[-60:])
    baseline_volatility = 0.025  # 2.5% daily volatility

    # Determine regime
    if current > sma_200 and recent_avg > sma_200 * 0.99 and volatility_60 < baseline_volatility:
        # Uptrend: price above SMA200, recent trend positive, low volatility
        regime = "uptrend"
        regime_status = "Market in uptrend with rising momentum"
        regime_weight = 1.0
    elif current < sma_200 and recent_avg < sma_200 * 1.01 and volatility_60 > baseline_volatility * 1.5:
        # Downtrend: price below SMA200, recent trend negative, high volatility
        regime = "downtrend"
        regime_status = "Market in downtrend with elevated risk"
        regime_weight = 0.0
    else:
        # Sideways: mixed conditions
        regime = "sideways"
        regime_status = "Market consolidating, mixed signals"
        regime_weight = 0.3

    return regime, regime_status, regime_weight


def calculate_volatility(prices: List[float]) -> float:
    """Calculate daily log returns volatility."""
    if len(prices) < 2:
        return 0.0

    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            ret = abs((prices[i] - prices[i-1]) / prices[i-1])
            returns.append(ret)

    if not returns:
        return 0.0

    return statistics.stdev(returns) if len(returns) > 1 else statistics.mean(returns)


def calculate_structure_v5_score(
    metrics: Dict,
    pe: Optional[float],
    pb: Optional[float],
    circ_mv: Optional[float],
    position_60d: float,
    market_regime: str,
    regime_weight: float
) -> Tuple[float, str, List[str], str, Dict[str, float]]:
    """
    Calculate structure_v5 score using 5-component system.

    Components:
    - Base Quality (0-25): pe/pb quality, trend positioning
    - Inflection Detection (0-25): turnover spike, momentum change
    - Valuation Strength (0-20): valuation multiples, market cap tier
    - Price Extension (0-20): position in 60-day range
    - Market Cap Alignment (0-10): size tier appropriateness

    Args:
        metrics: Dict of calculated stock metrics (from candidate_scoring)
        pe: PE ratio (or None)
        pb: PB ratio (or None)
        circ_mv: Circulating market cap in 万 (10,000 CNY)
        position_60d: Position in 60-day high-low range (0-1)
        market_regime: Current market regime
        regime_weight: Market regime weight factor

    Returns:
        (score, tier, tags, reason)
        - score: 0-100 numeric score
        - tier: 'A', 'B', 'C', or 'D'
        - tags: List of applicable tags
        - reason: Human-readable explanation
    """

    score = 0.0
    tags = []
    components = {"base_quality": 0.0, "inflection": 0.0, "valuation": 0.0, "extension": 0.0, "alignment": 0.0}

    # ===== HARD GATES (Conservative_PE50 hard conditions, fail = score 0) =====
    # v5 is designed for "low baseline → rising turnover" early accumulation.
    # If any hard condition is violated, this stock is not a v5 candidate at all.
    hard_fail_reason = None

    today_turnover = metrics.get("latest_turnover")
    avg_turnover_20 = metrics.get("avg_turnover_20")
    pct_change = metrics.get("latest_pct_change")

    # Gate 1: today's turnover must be ≤ 8% (cap, avoid blowoff days)
    if today_turnover is not None and today_turnover > STRUCTURE_V5_PARAMS["today_turnover_max"]:
        hard_fail_reason = f"today_turnover={today_turnover:.1f}% > {STRUCTURE_V5_PARAMS['today_turnover_max']}%"

    # Gate 2: 20-day average turnover must be < 3% (low baseline requirement)
    elif avg_turnover_20 is not None and avg_turnover_20 >= STRUCTURE_V5_PARAMS["avg_turnover_20d_max"]:
        hard_fail_reason = f"avg_turnover_20={avg_turnover_20:.1f}% >= {STRUCTURE_V5_PARAMS['avg_turnover_20d_max']}%"

    # Gate 3: PE constraint
    elif pe is None or pe <= 0:
        hard_fail_reason = "pe missing or non-positive (cannot evaluate value)"
    elif pe >= STRUCTURE_V5_PARAMS["pe_max"]:
        hard_fail_reason = f"pe={pe:.1f} >= {STRUCTURE_V5_PARAMS['pe_max']}"

    # Gate 4: PB constraint
    elif pb is None or pb <= 0:
        hard_fail_reason = "pb missing or non-positive"
    elif pb >= STRUCTURE_V5_PARAMS["pb_max"]:
        hard_fail_reason = f"pb={pb:.1f} >= {STRUCTURE_V5_PARAMS['pb_max']}"

    # Gate 5: market cap constraint
    elif circ_mv is None:
        hard_fail_reason = "circ_mv missing"
    elif (circ_mv / 10000.0) >= STRUCTURE_V5_PARAMS["circ_mv_max_yi"]:
        hard_fail_reason = f"circ_mv={circ_mv/10000.0:.1f}亿 >= {STRUCTURE_V5_PARAMS['circ_mv_max_yi']}亿"

    # Gate 6: position in 60d range — must be in lower half (≤ 70%)
    elif position_60d is not None and position_60d > STRUCTURE_V5_PARAMS["position_60d_max"]:
        hard_fail_reason = f"position_60d={position_60d:.2f} > {STRUCTURE_V5_PARAMS['position_60d_max']}"

    # Gate 7: turnover inflection ratio — today must be ≥ 1.5× 20d avg
    elif (
        today_turnover is not None and avg_turnover_20 is not None
        and avg_turnover_20 > 0
        and today_turnover < avg_turnover_20 * STRUCTURE_V5_PARAMS["turnover_ratio_threshold"]
    ):
        hard_fail_reason = (
            f"turnover_ratio={today_turnover/avg_turnover_20:.2f}× < "
            f"{STRUCTURE_V5_PARAMS['turnover_ratio_threshold']}× (no inflection)"
        )

    # Gate 8: extreme single-day move filter — v5 wants accumulation, not blowoffs/crashes
    elif pct_change is not None and abs(pct_change) >= 7.0:
        hard_fail_reason = f"pct_change={pct_change:+.1f}% (|move| ≥ 7%, not accumulation)"

    if hard_fail_reason:
        tags.append("v5_fail")
        return 0.0, "D", tags, f"REJECTED: {hard_fail_reason}", components

    # ===== COMPONENT 1: Base Quality (0-25) =====
    base_quality = 0.0

    # PE quality (0-10 points)
    if pe and 0 < pe < 30:
        if pe < 15:
            base_quality += 10.0
            tags.append("low_pe")
        elif pe < 20:
            base_quality += 8.0
            tags.append("moderate_pe")
        else:
            base_quality += 5.0
    elif pe is None or pe <= 0:
        base_quality += 7.0  # Unknown PE, neutral
    else:
        base_quality += 0.0  # Too high PE

    # PB quality (0-10 points)
    if pb and 0 < pb < 3:
        if pb < 1.5:
            base_quality += 10.0
            tags.append("low_pb")
        elif pb < 2.5:
            base_quality += 7.0
            tags.append("moderate_pb")
        else:
            base_quality += 3.0
    elif pb is None or pb <= 0:
        base_quality += 5.0
    else:
        base_quality += 0.0

    # Trend positioning (0-5 points)
    if position_60d < 0.3:
        base_quality += 5.0
        tags.append("low_position")
    elif position_60d < 0.5:
        base_quality += 3.0

    components["base_quality"] = base_quality
    score += base_quality

    # ===== COMPONENT 2: Inflection Detection (0-25) =====
    inflection = 0.0

    # Turnover inflection: today's turnover vs 10d median (turnover_spike_ratio)
    # This is the v5 core signal: low baseline → rising turnover
    spike_ratio = metrics.get("turnover_spike_ratio") or 0.0
    if isinstance(spike_ratio, (int, float)) and spike_ratio > 1.0:
        # 1.0×=平价, 1.5×=拐点起步, 3×=明显放量
        # 给分: spike=1.0→0, 1.5→7.5, 2.0→15 (cap)
        inflection += min((spike_ratio - 1.0) * 15.0, 15.0)
        if spike_ratio >= 1.5:
            tags.append("turnover_rising")

    # Activity trend: 后5日均值 vs 前5日均值 (range typically -1 to +3)
    activity_trend = metrics.get("activity_trend") or 0.0
    if isinstance(activity_trend, (int, float)) and activity_trend > 0:
        # Positive trend means activity accelerating
        inflection += min(activity_trend * 5.0, 10.0)  # Max 10 points
        if activity_trend > 0.3:
            tags.append("momentum_building")

    components["inflection"] = inflection
    score += inflection

    # ===== COMPONENT 3: Valuation Strength (0-20) =====
    valuation = 0.0

    # PE multiple scoring (0-10)
    if pe and 0 < pe < 30:
        # Lower PE gets more points (early accumulation = cheaper)
        valuation += max(10 - (pe / 3), 0)
        tags.append(f"pe_{int(pe)}")
    elif pe is None:
        valuation += 5.0

    # Market cap tier (0-10)
    if circ_mv:
        circ_mv_yi = circ_mv / 10000.0
        if circ_mv_yi < 50:
            valuation += 10.0
            tags.append("small_cap")
        elif circ_mv_yi < 100:
            valuation += 8.0
            tags.append("mid_cap")
        elif circ_mv_yi < 150:
            valuation += 6.0
        else:
            valuation += 4.0

    components["valuation"] = valuation
    score += valuation

    # ===== COMPONENT 4: Price Extension (0-20) =====
    extension = 0.0

    if position_60d is not None:
        if position_60d < 0.2:
            extension += 20.0
            tags.append("near_60d_low")
        elif position_60d < 0.4:
            extension += 15.0
            tags.append("low_extension")
        elif position_60d < 0.6:
            extension += 10.0
        else:
            extension += 5.0

    components["extension"] = extension
    score += extension

    # ===== COMPONENT 5: Market Cap Alignment (0-10) =====
    alignment = 0.0

    # Early accumulation best suited for small-to-mid cap
    if circ_mv:
        circ_mv_yi = circ_mv / 10000.0
        if 10 < circ_mv_yi < 150:
            alignment += 10.0
            tags.append("ideal_size")
        elif 5 < circ_mv_yi < 300:
            alignment += 7.0
            tags.append("suitable_size")
        else:
            alignment += 3.0

    components["alignment"] = alignment
    score += alignment

    # ===== Tier Mapping =====
    if score >= 80:
        tier = "A"
    elif score >= 60:
        tier = "B"
    elif score >= 40:
        tier = "C"
    else:
        tier = "D"

    # Build reason string
    top_components = sorted(components.items(), key=lambda x: x[1], reverse=True)
    reason = f"Tier {tier}: {top_components[0][0].replace('_', ' ')} dominant "
    if len(tags) > 0:
        reason += f"({', '.join(tags[:3])})"
    else:
        reason += "(generic early accumulation signal)"

    return score, tier, tags, reason, components


def check_structure_v5_conditions(
    pe: Optional[float],
    pb: Optional[float],
    circ_mv: Optional[float],
    today_turnover: float,
    avg_turnover_20d: float,
    position_60d: float,
) -> Tuple[bool, str]:
    """
    Check if stock meets structure_v5 candidate conditions (Conservative_PE50 params).

    Args:
        pe: PE ratio
        pb: PB ratio
        circ_mv: Circulating market cap in 万
        today_turnover: Today's turnover rate (%)
        avg_turnover_20d: 20-day average turnover (%)
        position_60d: Position in 60-day range (0-1)

    Returns:
        (passes_conditions, reason_if_failed)
    """

    # PE filter
    if pe is None or pe <= 0 or pe >= STRUCTURE_V5_PARAMS["pe_max"]:
        return False, f"PE outside range [1, {STRUCTURE_V5_PARAMS['pe_max']})"

    # PB filter
    if pb is None or pb <= 0 or pb >= STRUCTURE_V5_PARAMS["pb_max"]:
        return False, f"PB outside range [1, {STRUCTURE_V5_PARAMS['pb_max']})"

    # Market cap filter
    if circ_mv is None:
        return False, "Missing circulating market cap data"

    circ_mv_yi = circ_mv / 10000.0
    if circ_mv_yi >= STRUCTURE_V5_PARAMS["circ_mv_max_yi"]:
        return False, f"Market cap >= {STRUCTURE_V5_PARAMS['circ_mv_max_yi']}亿"

    # Turnover filters
    if avg_turnover_20d >= STRUCTURE_V5_PARAMS["avg_turnover_20d_max"]:
        return False, f"20d avg turnover >= {STRUCTURE_V5_PARAMS['avg_turnover_20d_max']}%"

    if today_turnover > STRUCTURE_V5_PARAMS["today_turnover_max"]:
        return False, f"Today's turnover > {STRUCTURE_V5_PARAMS['today_turnover_max']}%"

    # Inflection filter
    turnover_ratio = today_turnover / avg_turnover_20d if avg_turnover_20d > 0 else 0
    if turnover_ratio <= STRUCTURE_V5_PARAMS["turnover_ratio_threshold"]:
        return False, f"Turnover ratio < {STRUCTURE_V5_PARAMS['turnover_ratio_threshold']}"

    # Position filter
    if position_60d > STRUCTURE_V5_PARAMS["position_60d_max"]:
        return False, f"Position in 60d range > {STRUCTURE_V5_PARAMS['position_60d_max']}"

    return True, "Passed all structure_v5 conditions"
