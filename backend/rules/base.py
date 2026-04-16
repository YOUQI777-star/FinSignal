from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuleDefinition:
    signal_id: str
    name: str
    severity: str
    required_fields: tuple[str, ...]
    market_support: str
    availability: str
    description: str


def build_signal_result(
    *,
    rule: RuleDefinition,
    status: str,
    triggered: bool,
    message: str,
    value: Any = None,
    threshold: Any = None,
) -> dict[str, Any]:
    return {
        "signal_id": rule.signal_id,
        "name": rule.name,
        "severity": rule.severity,
        "status": status,
        "triggered": triggered,
        "message": message,
        "value": value,
        "threshold": threshold,
        "required_fields": list(rule.required_fields),
        "market_support": rule.market_support,
        "availability": rule.availability,
    }
