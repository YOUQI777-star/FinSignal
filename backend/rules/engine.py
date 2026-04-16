from __future__ import annotations

from collections import Counter
from typing import Any

from backend.data_access.coverage import snapshot_tier
from backend.rules.financial_rules import FINANCIAL_RULES
from backend.rules.governance_rules import GOVERNANCE_RULES


class RuleEngine:
    """Evaluate financial and governance rules against a normalized snapshot."""

    def __init__(self) -> None:
        self.financial_rules = FINANCIAL_RULES
        self.governance_rules = GOVERNANCE_RULES

    def evaluate(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        tier = snapshot_tier(snapshot)
        financial_results = [rule(snapshot) for rule in self.financial_rules]
        governance_results = [rule(snapshot) for rule in self.governance_rules]
        all_results = financial_results + governance_results

        counts = Counter(result["status"] for result in all_results)
        triggered = [result for result in all_results if result["triggered"]]

        return {
            "company_id": snapshot.get("company_id"),
            "market": snapshot.get("market"),
            "code": snapshot.get("code"),
            "name": snapshot.get("name"),
            "summary": {
                "total_rules": len(all_results),
                "triggered_count": len(triggered),
                "status_counts": dict(counts),
                "snapshot_tier": tier,
            },
            "financial_signals": financial_results,
            "governance_signals": governance_results,
        }
