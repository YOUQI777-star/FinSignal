from __future__ import annotations

from typing import Any

from backend.data_access.local_store import LocalDataStore
from backend.data_access.master_store import MasterDataStore


class CompanyRepository:
    """Unified access layer combining company_master and local snapshots."""

    def __init__(
        self,
        master_store: MasterDataStore | None = None,
        local_store: LocalDataStore | None = None,
    ) -> None:
        self.master_store = master_store or MasterDataStore()
        self.local_store = local_store or LocalDataStore()

    def get_company_profile(self, market: str, code: str) -> dict[str, Any] | None:
        master_company = self.master_store.get_company(market, code)
        snapshot = self.local_store.get_company_snapshot(market, code)

        if master_company is None and snapshot is None:
            return None

        if master_company is None:
            return snapshot

        if snapshot is None:
            return {
                **master_company,
                "currency": "CNY" if market.upper() == "CN" else "TWD",
                "financials": {"annual": []},
                "governance": {},
                "equity_structure": [],
                "coverage": {"available_rules": [], "missing_fields": ["financials.annual", "governance"]},
            }

        merged = dict(snapshot)
        merged["company_id"] = master_company["company_id"]
        merged["market"] = master_company["market"]
        merged["code"] = master_company["code"]
        merged["name"] = master_company["name"]
        merged["name_en"] = master_company["name_en"] or snapshot.get("name_en")
        merged["industry"] = master_company["industry"] or snapshot.get("industry")
        merged["status"] = master_company["status"]
        merged["ipo_date"] = master_company["ipo_date"]
        merged["master_updated_at"] = master_company["updated_at"]
        return merged

    def search_companies(self, query: str) -> list[dict[str, Any]]:
        master_results = self.master_store.search_companies(query)
        if master_results:
            return master_results
        return self.local_store.search_companies(query)
