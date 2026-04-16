from __future__ import annotations

from typing import Any


CORE_FINANCIAL_FIELDS = (
    "revenue",
    "net_profit",
    "operating_cash_flow",
    "accounts_receivable",
    "inventory",
    "total_assets",
    "total_liabilities",
)


def annual_records(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return snapshot.get("financials", {}).get("annual", []) or []


def has_real_financials(snapshot: dict[str, Any]) -> bool:
    annual = annual_records(snapshot)
    if not annual:
        return False
    latest = annual[0]
    populated = sum(1 for field in CORE_FINANCIAL_FIELDS if latest.get(field) is not None)
    return populated >= 4


def snapshot_tier(snapshot: dict[str, Any]) -> str:
    if has_real_financials(snapshot):
        return "real_financial_available"
    if annual_records(snapshot):
        return "partial_financial_available"
    return "shell_only"
