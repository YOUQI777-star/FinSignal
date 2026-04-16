from __future__ import annotations

from typing import Any

from backend.rules.base import RuleDefinition, build_signal_result


G1 = RuleDefinition(
    signal_id="G1",
    name="大股东高比例质押",
    severity="high",
    required_fields=("governance.pledge_ratio",),
    market_support="CN",
    availability="partial",
    description="Controlling shareholder pledge ratio is above 50%.",
)

G3 = RuleDefinition(
    signal_id="G3",
    name="两职合一且独董不足",
    severity="high",
    required_fields=("governance.chairman_is_ceo", "governance.independent_director_ratio"),
    market_support="CN+TW",
    availability="stable",
    description="Chairman also acts as CEO while independent director ratio is below one-third.",
)


def evaluate_g1(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("market") != "CN":
        return build_signal_result(
            rule=G1,
            status="not_applicable",
            triggered=False,
            message="This rule is currently only applied to CN market companies.",
        )

    pledge_ratio = snapshot.get("governance", {}).get("pledge_ratio")
    if not isinstance(pledge_ratio, (int, float)):
        return build_signal_result(
            rule=G1,
            status="not_available",
            triggered=False,
            message="Pledge ratio is missing.",
        )

    triggered = pledge_ratio > 0.5
    return build_signal_result(
        rule=G1,
        status="ok" if not triggered else "triggered",
        triggered=triggered,
        message="Pledge ratio exceeds 50%." if triggered else "No excessive pledge ratio detected.",
        value=pledge_ratio,
        threshold=0.5,
    )


def evaluate_g3(snapshot: dict[str, Any]) -> dict[str, Any]:
    governance = snapshot.get("governance", {})
    chairman_is_ceo = governance.get("chairman_is_ceo")
    independent_ratio = governance.get("independent_director_ratio")

    if not isinstance(chairman_is_ceo, bool) or not isinstance(independent_ratio, (int, float)):
        return build_signal_result(
            rule=G3,
            status="not_available",
            triggered=False,
            message="Chairman/CEO flag and independent director ratio are required.",
        )

    triggered = chairman_is_ceo and independent_ratio < (1 / 3)
    return build_signal_result(
        rule=G3,
        status="ok" if not triggered else "triggered",
        triggered=triggered,
        message="Chairman-CEO duality is present and independent director ratio is below one-third." if triggered else "Board independence rule not triggered.",
        value={
            "chairman_is_ceo": chairman_is_ceo,
            "independent_director_ratio": round(independent_ratio, 4),
        },
        threshold={"chairman_is_ceo": True, "independent_director_ratio": "< 0.3333"},
    )


GOVERNANCE_RULES = [evaluate_g1, evaluate_g3]
