from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import baostock as bs


@dataclass(frozen=True)
class BaoStockAnnualRecord:
    period: str
    revenue: float | None
    net_profit: float | None
    operating_cash_flow: float | None
    accounts_receivable: float | None = None
    inventory: float | None = None
    goodwill: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None


class BaoStockCNClient:
    """Partial CN financial fallback built on BaoStock summary endpoints."""

    def __init__(self) -> None:
        self._logged_in = False

    def fetch_annual_financials(self, code: str, years: int = 6) -> list[dict[str, Any]]:
        self._login()
        try:
            market_code = self._to_baostock_code(code)
            annual: list[dict[str, Any]] = []
            for year in range(2025, 2025 - years, -1):
                record = self._fetch_year_record(market_code, year)
                if record is None:
                    continue
                annual.append(
                    {
                        "period": record.period,
                        "revenue": record.revenue,
                        "net_profit": record.net_profit,
                        "operating_cash_flow": record.operating_cash_flow,
                        "accounts_receivable": record.accounts_receivable,
                        "inventory": record.inventory,
                        "goodwill": record.goodwill,
                        "total_assets": record.total_assets,
                        "total_liabilities": record.total_liabilities,
                        "non_recurring_items": None,
                        "related_party_revenue": None,
                        "rd_capitalization_rate": None,
                        "audit_opinion": None,
                        "source": "baostock_partial",
                        "unit": "base_currency",
                        "as_of": f"{record.period}-12-31",
                    }
                )
            return annual
        finally:
            self._logout()

    def _fetch_year_record(self, code: str, year: int) -> BaoStockAnnualRecord | None:
        profit = self._query_one(bs.query_profit_data, code=code, year=year, quarter=4)
        cash = self._query_one(bs.query_cash_flow_data, code=code, year=year, quarter=4)
        if profit is None:
            return None

        revenue = self._float(profit.get("MBRevenue"))
        net_profit = self._float(profit.get("netProfit"))
        operating_cash_flow = None
        if cash and revenue is not None:
            cfo_to_or = self._float(cash.get("CFOToOR"))
            if cfo_to_or is not None:
                operating_cash_flow = revenue * cfo_to_or

        stat_date = profit.get("statDate")
        period = str(stat_date)[:4] if stat_date else str(year)
        return BaoStockAnnualRecord(
            period=period,
            revenue=revenue,
            net_profit=net_profit,
            operating_cash_flow=operating_cash_flow,
        )

    @staticmethod
    def _query_one(func, **kwargs) -> dict[str, str] | None:
        rs = func(**kwargs)
        if rs.error_code != "0":
            return None
        rows: list[dict[str, str]] = []
        while rs.next():
            rows.append(dict(zip(rs.fields, rs.get_row_data())))
        return rows[0] if rows else None

    def _login(self) -> None:
        if self._logged_in:
            return
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"BaoStock login failed: {lg.error_msg}")
        self._logged_in = True

    def _logout(self) -> None:
        if self._logged_in:
            bs.logout()
            self._logged_in = False

    @staticmethod
    def _to_baostock_code(code: str) -> str:
        return f"sh.{code}" if code.startswith(("6", "9")) else f"sz.{code}"

    @staticmethod
    def _float(value: str | None) -> float | None:
        if value in (None, "", "None"):
            return None
        try:
            return float(value)
        except ValueError:
            return None
