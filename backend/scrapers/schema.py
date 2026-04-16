from __future__ import annotations

from typing import Any


def create_company_snapshot(
    *,
    market: str,
    code: str,
    name: str,
    currency: str,
    industry: str | None = None,
    name_en: str | None = None,
    financial_annual: list[dict[str, Any]] | None = None,
    governance: dict[str, Any] | None = None,
    equity_structure: list[dict[str, Any]] | None = None,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    company_id = f"{market}:{code}"
    return {
        "market": market,
        "code": code,
        "company_id": company_id,
        "name": name,
        "name_en": name_en,
        "industry": industry,
        "currency": currency,
        "financials": {
            "annual": financial_annual or [],
        },
        "governance": governance or {},
        "equity_structure": equity_structure or [],
        "coverage": coverage or {"available_rules": [], "missing_fields": []},
    }
