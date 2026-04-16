from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from backend.config import DATA_DIR
from backend.scrapers.cn_baostock import BaoStockCNClient
from backend.scrapers.schema import create_company_snapshot

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover - optional dependency for local development
    ak = None


class AkshareCNClient:
    """CN market data access backed by AKShare with local fallback support."""

    market = "CN"
    currency = "CNY"

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DATA_DIR
        self.last_source_mode = "unknown"
        self.last_live_provider = None
        self.last_error = None

    def list_companies(self) -> list[dict[str, Any]]:
        if ak is not None:
            try:
                records = self._fetch_company_list_from_akshare()
                self.last_source_mode = "live"
                self.last_live_provider = "akshare"
                self.last_error = None
                return records
            except Exception as exc:
                self.last_source_mode = "fallback"
                self.last_live_provider = None
                self.last_error = f"{type(exc).__name__}: {exc}"
        else:
            self.last_source_mode = "fallback"
            self.last_live_provider = None
            self.last_error = "AKShare is not installed."
        return self._load_demo_company_list()

    def fetch_company_snapshot(self, code: str, require_live: bool = False) -> dict[str, Any]:
        if ak is not None:
            try:
                snapshot = self._fetch_snapshot_from_akshare(code)
                self.last_source_mode = "live"
                self.last_live_provider = "akshare"
                self.last_error = None
                return snapshot
            except Exception as exc:
                self.last_source_mode = "fallback"
                self.last_live_provider = None
                self.last_error = f"{type(exc).__name__}: {exc}"
        else:
            self.last_source_mode = "fallback"
            self.last_live_provider = None
            self.last_error = "AKShare is not installed."

        if require_live:
            raise RuntimeError(f"AKShare live snapshot fetch failed for {code}")

        snapshot = self._load_local_snapshot(code)
        if snapshot is None:
            raise FileNotFoundError(f"No CN snapshot found for code {code}")
        return snapshot

    def live_source_available(self) -> bool:
        if ak is None:
            self.last_source_mode = "fallback"
            return False
        try:
            records = self._fetch_company_list_from_akshare()
            self.last_source_mode = "live" if records else "fallback"
            self.last_live_provider = "akshare" if records else None
            self.last_error = None if records else "AKShare returned zero records."
            return bool(records)
        except Exception as exc:
            self.last_source_mode = "fallback"
            self.last_live_provider = None
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False

    def _fetch_company_list_from_akshare(self) -> list[dict[str, Any]]:
        stock_info = ak.stock_info_a_code_name()
        records: list[dict[str, Any]] = []
        for row in stock_info.to_dict(orient="records"):
            code = str(row.get("code") or row.get("证券代码") or "").strip()
            name = str(row.get("name") or row.get("证券简称") or "").strip()
            if not code or not name:
                continue
            records.append(
                {
                    "code": code.zfill(6),
                    "name": name,
                    "industry": None,
                    "status": "active",
                    "ipo_date": None,
                }
            )
        return records

    def _fetch_snapshot_from_akshare(self, code: str) -> dict[str, Any]:
        company = next((item for item in self.list_companies() if item["code"] == code), None)
        if company is None:
            raise ValueError(f"Company code not found in AKShare listing: {code}")

        stock_id = self._to_sina_stock_id(code)
        balance_df = ak.stock_financial_report_sina(stock=stock_id, symbol="资产负债表")
        income_df = ak.stock_financial_report_sina(stock=stock_id, symbol="利润表")
        cashflow_df = ak.stock_financial_report_sina(stock=stock_id, symbol="现金流量表")
        annual = self._build_annual_financials(balance_df, income_df, cashflow_df)
        if not annual:
            raise ValueError(f"No annual financial rows parsed from Sina statements for {code}")

        return create_company_snapshot(
            market=self.market,
            code=company["code"],
            name=company["name"],
            currency=self.currency,
            industry=company.get("industry"),
            financial_annual=annual,
            governance={},
            equity_structure=[],
            coverage={
                "available_rules": ["F1", "F2", "F3"],
                "missing_fields": ["governance"],
            },
        )

    def _build_annual_financials(self, balance_df, income_df, cashflow_df) -> list[dict[str, Any]]:
        balance_rows = self._annual_rows(balance_df)
        income_rows = self._annual_rows(income_df)
        cashflow_rows = self._annual_rows(cashflow_df)

        income_by_period = {row["报告日"]: row for row in income_rows}
        cashflow_by_period = {row["报告日"]: row for row in cashflow_rows}

        annual: list[dict[str, Any]] = []
        for period, balance_row in balance_by_period(balance_rows).items():
            income_row = income_by_period.get(period, {})
            cashflow_row = cashflow_by_period.get(period, {})
            annual.append(
                {
                    "period": period[:4],
                    "revenue": self._value(income_row, "营业总收入", "营业收入"),
                    "net_profit": self._value(income_row, "归属于母公司所有者的净利润", "归母净利润", "净利润"),
                    "operating_cash_flow": self._value(cashflow_row, "经营活动产生的现金流量净额"),
                    "accounts_receivable": self._value(balance_row, "应收账款", "应收票据及应收账款"),
                    "inventory": self._value(balance_row, "存货"),
                    "goodwill": self._value(balance_row, "商誉"),
                    "total_assets": self._value(balance_row, "资产总计"),
                    "total_liabilities": self._value(balance_row, "负债合计"),
                    "non_recurring_items": None,
                    "related_party_revenue": None,
                    "rd_capitalization_rate": None,
                    "audit_opinion": None,
                    "source": "akshare_sina",
                    "unit": "base_currency",
                    "as_of": self._format_as_of(period),
                }
            )
        return sorted(annual, key=lambda item: item["period"], reverse=True)

    def _load_demo_company_list(self) -> list[dict[str, Any]]:
        snapshots = self._load_all_local_snapshots()
        return [
            {
                "code": item["code"],
                "name": item["name"],
                "industry": item.get("industry"),
                "status": "active",
                "ipo_date": None,
            }
            for item in snapshots
        ]

    def _load_all_local_snapshots(self) -> list[dict[str, Any]]:
        market_dir = self.data_dir / "cn"
        snapshots: list[dict[str, Any]] = []
        for path in market_dir.glob("*.json"):
            with path.open("r", encoding="utf-8") as file:
                snapshots.append(json.load(file))
        return sorted(snapshots, key=lambda item: item["code"])

    def _load_local_snapshot(self, code: str) -> dict[str, Any] | None:
        path = self.data_dir / "cn" / f"{code}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def fetch_company_snapshot_with_baostock_fallback(self, code: str) -> dict[str, Any]:
        company = next((item for item in self.list_companies() if item["code"] == code), None)
        if company is None:
            raise ValueError(f"Company code not found in AKShare listing: {code}")

        annual = BaoStockCNClient().fetch_annual_financials(code)
        if not annual:
            raise RuntimeError(f"BaoStock partial fallback returned no annual records for {code}")

        return create_company_snapshot(
            market=self.market,
            code=company["code"],
            name=company["name"],
            currency=self.currency,
            industry=company.get("industry"),
            financial_annual=annual,
            governance={},
            equity_structure=[],
            coverage={
                "available_rules": ["F2"],
                "missing_fields": [
                    "governance",
                    "accounts_receivable",
                    "inventory",
                    "total_assets",
                    "total_liabilities",
                ],
            },
        )

    def fetch_bulk_annual_from_em(self, year: int) -> dict[str, dict[str, Any]]:
        """Fetch all CN-market annual financials for a given year via EastMoney bulk endpoints.

        Returns a mapping of zero-padded 6-digit code -> annual record dict.
        One call covers ~5000+ companies; use this for bulk enrichment instead of per-company fetches.
        """
        if ak is None:
            raise RuntimeError("AKShare is not installed.")
        date_str = f"{year}1231"
        try:
            balance_df = ak.stock_zcfz_em(date=date_str)
            income_df = ak.stock_lrb_em(date=date_str)
            cashflow_df = ak.stock_xjll_em(date=date_str)
        except Exception as exc:
            raise RuntimeError(f"EastMoney bulk fetch failed for {year}: {exc}") from exc

        balance_by_code = {str(row.get("股票代码", "")).zfill(6): row for row in balance_df.to_dict("records")}
        income_by_code = {str(row.get("股票代码", "")).zfill(6): row for row in income_df.to_dict("records")}
        cashflow_by_code = {str(row.get("股票代码", "")).zfill(6): row for row in cashflow_df.to_dict("records")}

        all_codes = set(balance_by_code) | set(income_by_code) | set(cashflow_by_code)
        result: dict[str, dict[str, Any]] = {}
        for code in all_codes:
            b = balance_by_code.get(code, {})
            i = income_by_code.get(code, {})
            c = cashflow_by_code.get(code, {})
            result[code] = {
                "period": str(year),
                "revenue": self._value(i, "营业总收入"),
                "net_profit": self._value(i, "净利润"),
                "operating_cash_flow": self._value(c, "经营性现金流-现金流量净额"),
                "accounts_receivable": self._value(b, "资产-应收账款"),
                "inventory": self._value(b, "资产-存货"),
                "goodwill": None,
                "total_assets": self._value(b, "资产-总资产"),
                "total_liabilities": self._value(b, "负债-总负债"),
                "non_recurring_items": None,
                "related_party_revenue": None,
                "rd_capitalization_rate": None,
                "audit_opinion": None,
                "source": "akshare_em_bulk",
                "unit": "base_currency",
                "as_of": f"{year}-12-31",
            }
        return result

    @staticmethod
    def _annual_rows(df) -> list[dict[str, Any]]:
        if df is None or getattr(df, "empty", True):
            return []
        rows = []
        for row in df.to_dict(orient="records"):
            report_date = str(row.get("报告日", "")).strip()
            if len(report_date) == 8 and report_date.endswith("1231"):
                rows.append(row)
        return rows

    @staticmethod
    def _value(row: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = row.get(key)
            if value is None:
                continue
            if isinstance(value, float) and math.isnan(value):
                continue
            if isinstance(value, str):
                stripped = value.replace(",", "").strip()
                if not stripped or stripped.lower() == "nan":
                    continue
                try:
                    return float(stripped)
                except ValueError:
                    continue
            if isinstance(value, (int, float)):
                return float(value)
        return None

    @staticmethod
    def _format_as_of(period: str) -> str:
        return f"{period[:4]}-{period[4:6]}-{period[6:8]}"

    @staticmethod
    def _to_sina_stock_id(code: str) -> str:
        return f"sh{code}" if code.startswith(("6", "9")) else f"sz{code}"


def balance_by_period(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["报告日"]: row for row in rows}
