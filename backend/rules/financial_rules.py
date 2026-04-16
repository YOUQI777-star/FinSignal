from __future__ import annotations

from typing import Any

from backend.rules.base import RuleDefinition, build_signal_result


F1 = RuleDefinition(
    signal_id="F1",
    name="应收账款异常增长",
    severity="high",
    required_fields=("financials.annual",),
    market_support="CN+TW",
    availability="stable",
    description="AR-to-revenue ratio expands by more than 30% year-over-year, indicating receivables are accumulating faster than revenue regardless of growth direction.",
)

F2 = RuleDefinition(
    signal_id="F2",
    name="现金流与利润背离",
    severity="high",
    required_fields=("financials.annual",),
    market_support="CN+TW",
    availability="stable",
    description="Operating cash flow stays negative while net profit remains positive.",
)


def evaluate_f1(snapshot: dict[str, Any]) -> dict[str, Any]:
    annual = snapshot.get("financials", {}).get("annual", [])
    if len(annual) < 2:
        return build_signal_result(
            rule=F1,
            status="not_available",
            triggered=False,
            message="At least two annual periods are required to compare growth rates.",
        )

    current, previous = annual[0], annual[1]
    previous_revenue = previous.get("revenue")
    previous_ar = previous.get("accounts_receivable")
    current_revenue = current.get("revenue")
    current_ar = current.get("accounts_receivable")

    if not all(isinstance(value, (int, float)) and value > 0 for value in (previous_revenue, previous_ar, current_revenue, current_ar)):
        return build_signal_result(
            rule=F1,
            status="not_available",
            triggered=False,
            message="Revenue and accounts receivable values must be present and positive for two consecutive periods.",
        )

    prev_ratio = previous_ar / previous_revenue
    curr_ratio = current_ar / current_revenue
    ratio_change = curr_ratio / prev_ratio
    triggered = ratio_change > 1.3

    return build_signal_result(
        rule=F1,
        status="triggered" if triggered else "ok",
        triggered=triggered,
        message=f"AR-to-revenue ratio expanded by {ratio_change - 1:.1%} YoY, suggesting receivables are accumulating." if triggered else "No abnormal AR accumulation relative to revenue.",
        value={
            "current_ar_to_revenue": round(curr_ratio, 4),
            "previous_ar_to_revenue": round(prev_ratio, 4),
            "ratio_change": round(ratio_change, 4),
        },
        threshold="AR/revenue ratio expands > 30% YoY",
    )


def evaluate_f2(snapshot: dict[str, Any]) -> dict[str, Any]:
    annual = snapshot.get("financials", {}).get("annual", [])
    if len(annual) < 2:
        return build_signal_result(
            rule=F2,
            status="not_available",
            triggered=False,
            message="At least two annual periods are required.",
        )

    latest_two = annual[:2]
    if not all(
        isinstance(item.get("operating_cash_flow"), (int, float))
        and isinstance(item.get("net_profit"), (int, float))
        for item in latest_two
    ):
        return build_signal_result(
            rule=F2,
            status="not_available",
            triggered=False,
            message="Operating cash flow and net profit are required for two periods.",
        )

    triggered = all(item["operating_cash_flow"] < 0 and item["net_profit"] > 0 for item in latest_two)
    return build_signal_result(
        rule=F2,
        status="ok" if not triggered else "triggered",
        triggered=triggered,
        message="Operating cash flow stayed negative for two years while profits remained positive." if triggered else "Cash flow and profit profile looks consistent on this rule.",
        value=[
            {
                "period": item.get("period"),
                "operating_cash_flow": item.get("operating_cash_flow"),
                "net_profit": item.get("net_profit"),
            }
            for item in latest_two
        ],
        threshold="2 consecutive years of negative OCF with positive net profit",
    )


F3 = RuleDefinition(
    signal_id="F3",
    name="资产负债率持续偏高",
    severity="medium",
    required_fields=("financials.annual",),
    market_support="CN+TW",
    availability="stable",
    description="Debt-to-assets ratio exceeds 70% for two consecutive years.",
)

F4 = RuleDefinition(
    signal_id="F4",
    name="毛利率骤降",
    severity="medium",
    required_fields=("financials.annual",),
    market_support="CN+TW",
    availability="stable",
    description="Gross margin proxy (net profit / revenue) drops by more than 10 percentage points year-over-year.",
)


def evaluate_f3(snapshot: dict[str, Any]) -> dict[str, Any]:
    annual = snapshot.get("financials", {}).get("annual", [])
    if len(annual) < 2:
        return build_signal_result(
            rule=F3,
            status="not_available",
            triggered=False,
            message="At least two annual periods are required.",
        )

    latest_two = annual[:2]
    ratios = []
    for item in latest_two:
        assets = item.get("total_assets")
        liabilities = item.get("total_liabilities")
        if not isinstance(assets, (int, float)) or not isinstance(liabilities, (int, float)) or assets <= 0:
            return build_signal_result(
                rule=F3,
                status="not_available",
                triggered=False,
                message="total_assets and total_liabilities are required for two periods.",
            )
        ratios.append(liabilities / assets)

    triggered = all(r > 0.7 for r in ratios)
    return build_signal_result(
        rule=F3,
        status="triggered" if triggered else "ok",
        triggered=triggered,
        message="Debt-to-assets ratio exceeded 70% for two consecutive years." if triggered else "Debt-to-assets ratio is within acceptable range.",
        value=[
            {"period": item.get("period"), "debt_to_assets": round(r, 4)}
            for item, r in zip(latest_two, ratios)
        ],
        threshold="debt_to_assets > 0.70 for 2 consecutive years",
    )


def evaluate_f4(snapshot: dict[str, Any]) -> dict[str, Any]:
    annual = snapshot.get("financials", {}).get("annual", [])
    if len(annual) < 2:
        return build_signal_result(
            rule=F4,
            status="not_available",
            triggered=False,
            message="At least two annual periods are required.",
        )

    current, previous = annual[0], annual[1]
    fields = ("revenue", "net_profit")
    for item in (current, previous):
        for f in fields:
            if not isinstance(item.get(f), (int, float)) or item[f] == 0:
                return build_signal_result(
                    rule=F4,
                    status="not_available",
                    triggered=False,
                    message="revenue and net_profit are required for two periods.",
                )

    prev_margin = previous["net_profit"] / previous["revenue"]
    curr_margin = current["net_profit"] / current["revenue"]
    drop = prev_margin - curr_margin
    triggered = drop > 0.10

    return build_signal_result(
        rule=F4,
        status="triggered" if triggered else "ok",
        triggered=triggered,
        message=f"Net margin dropped by {drop:.1%} year-over-year." if triggered else "No significant margin deterioration detected.",
        value={
            "current_margin": round(curr_margin, 4),
            "previous_margin": round(prev_margin, 4),
            "drop": round(drop, 4),
        },
        threshold="margin drop > 10 percentage points",
    )


FINANCIAL_RULES = [evaluate_f1, evaluate_f2, evaluate_f3, evaluate_f4]
