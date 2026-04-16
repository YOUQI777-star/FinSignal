from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import urllib3

from backend.config import DATA_DIR
from backend.scrapers.schema import create_company_snapshot


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TwseClient:
    """TW market data access backed by TWSE open endpoints with local fallback support."""

    market = "TW"
    currency = "TWD"
    company_list_url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    isin_list_url = "https://isin.twse.com.tw/isin/e_C_public.jsp?strMode=2"
    finmind_api_url = "https://api.finmindtrade.com/api/v3/data"
    openapi_base_url = "https://openapi.twse.com.tw/v1"
    openapi_amount_scale = 1000.0
    income_paths = (
        "/opendata/t187ap06_L_ci",
        "/opendata/t187ap06_L_mim",
        "/opendata/t187ap06_L_basi",
        "/opendata/t187ap06_L_bd",
        "/opendata/t187ap06_L_fh",
        "/opendata/t187ap06_L_ins",
    )
    balance_paths = (
        "/opendata/t187ap07_L_ci",
        "/opendata/t187ap07_L_mim",
        "/opendata/t187ap07_L_basi",
        "/opendata/t187ap07_L_bd",
        "/opendata/t187ap07_L_fh",
        "/opendata/t187ap07_L_ins",
    )

    def __init__(self, data_dir: Path | None = None, timeout: int = 20) -> None:
        self.data_dir = data_dir or DATA_DIR
        self.timeout = timeout
        self.last_source_mode = "unknown"
        self.last_live_provider = None
        self.last_error = None
        self._dataset_cache: dict[str, list[dict[str, Any]]] = {}
        self._company_list_cache: list[dict[str, Any]] | None = None

    def list_companies(self) -> list[dict[str, Any]]:
        if self._company_list_cache is not None:
            return self._company_list_cache

        try:
            records = self._fetch_company_list_from_twse()
            self.last_source_mode = "live"
            self.last_live_provider = "twse_openapi"
            self.last_error = None
            self._company_list_cache = records
            return records
        except Exception as exc:
            self.last_error = f"twse_openapi -> {type(exc).__name__}: {exc}"

        try:
            records = self._fetch_company_list_from_isin()
            self.last_source_mode = "live"
            self.last_live_provider = "twse_isin"
            self.last_error = None
            self._company_list_cache = records
            return records
        except Exception as exc:
            self.last_source_mode = "fallback"
            self.last_live_provider = None
            suffix = f" | twse_isin -> {type(exc).__name__}: {exc}"
            self.last_error = f"{self.last_error or ''}{suffix}".strip(" |")
            self._company_list_cache = self._load_demo_company_list()
            return self._company_list_cache

    def fetch_company_snapshot(self, code: str, require_live: bool = False) -> dict[str, Any]:
        company = next((item for item in self.list_companies() if item["code"] == code), None)
        if company is None:
            if require_live:
                raise RuntimeError(f"TWSE live company lookup failed for {code}")
            snapshot = self._load_local_snapshot(code)
            if snapshot is None:
                raise FileNotFoundError(f"No TW snapshot found for code {code}")
            return snapshot

        snapshot = self._load_local_snapshot(code)
        if snapshot is not None and not require_live:
            return snapshot

        official_error: Exception | None = None
        finmind_error: Exception | None = None

        try:
            annual = self._fetch_financial_annuals_from_twse_openapi(company["code"])
            annual = self._enrich_annuals_from_local_snapshot(company["code"], annual)
            return self._build_snapshot_from_annuals(company, annual)
        except Exception as exc:
            official_error = exc

        try:
            annual = self._fetch_financial_annuals_from_finmind(company["code"])
            annual = self._merge_annuals(annual, snapshot)
            self.last_live_provider = "finmind"
            self.last_error = None
            return self._build_snapshot_from_annuals(company, annual)
        except Exception as exc:
            finmind_error = exc
            if require_live:
                detail = []
                if official_error is not None:
                    detail.append(f"twse_openapi: {official_error}")
                detail.append(f"finmind: {finmind_error}")
                raise RuntimeError(f"TW live financial fetch failed for {code}: {' | '.join(detail)}") from exc
            if snapshot is not None:
                return snapshot
            return create_company_snapshot(
                market=self.market,
                code=company["code"],
                name=company["name"],
                name_en=company.get("name_en"),
                currency=self.currency,
                industry=company.get("industry"),
                financial_annual=[],
                governance={},
                equity_structure=[],
                coverage={"available_rules": [], "missing_fields": ["financials.annual", "governance"]},
            )

    def _build_snapshot_from_annuals(self, company: dict[str, Any], annual: list[dict[str, Any]]) -> dict[str, Any]:
        return create_company_snapshot(
            market=self.market,
            code=company["code"],
            name=company["name"],
            name_en=company.get("name_en"),
            currency=self.currency,
            industry=company.get("industry"),
            financial_annual=annual,
            governance={},
            equity_structure=[],
            coverage={
                "available_rules": ["F1", "F2", "F3"] if annual else [],
                "missing_fields": ["governance"] if annual else ["financials.annual", "governance"],
            },
        )

    def _fetch_financial_annuals_from_twse_openapi(self, code: str) -> list[dict[str, Any]]:
        income = self._find_openapi_row(code, self.income_paths)
        balance = self._find_openapi_row(code, self.balance_paths)

        if income is None and balance is None:
            raise ValueError(f"TWSE OpenAPI returned no financial rows for {code}")

        period_year = self._roc_year_to_gregorian((income or balance).get("年度"))
        season = str((income or balance).get("季別") or "").strip()
        if not period_year:
            raise ValueError(f"TWSE OpenAPI returned invalid annual period for {code}")

        as_of = self._season_as_of(period_year, season)
        annual = [
            {
                "period": str(period_year),
                "revenue": self._scaled_number(
                    self._pick_value(income, "營業收入", "收入", "收益", "利息淨收益"),
                ),
                "net_profit": self._scaled_number(
                    self._pick_value(
                        income,
                        "淨利（淨損）歸屬於母公司業主",
                        "本期淨利（淨損）",
                        "本期稅後淨利（淨損）",
                        "稅後淨利（淨損）",
                    )
                ),
                "operating_cash_flow": None,
                "accounts_receivable": self._scaled_number(
                    self._pick_value(balance, "應收帳款淨額", "應收帳款－淨額", "應收款項－淨額", "應收款項")
                ),
                "inventory": self._scaled_number(self._pick_value(balance, "存貨", "存貨－淨額")),
                "goodwill": self._scaled_number(self._pick_value(balance, "商譽")),
                "total_assets": self._scaled_number(self._pick_value(balance, "資產總額", "資產總計")),
                "total_liabilities": self._scaled_number(self._pick_value(balance, "負債總額", "負債總計")),
                "non_recurring_items": None,
                "related_party_revenue": None,
                "rd_capitalization_rate": None,
                "audit_opinion": None,
                "source": "twse_openapi",
                "unit": "base_currency",
                "as_of": as_of,
            }
        ]
        self.last_source_mode = "live"
        self.last_live_provider = "twse_openapi"
        self.last_error = None
        return annual

    def _find_openapi_row(self, code: str, paths: tuple[str, ...]) -> dict[str, Any] | None:
        rows: list[dict[str, Any]] = []
        for path in paths:
            for row in self._openapi_dataset(path):
                if str(row.get("公司代號") or "").strip().zfill(4) == code:
                    rows.append(row)
        if not rows:
            return None
        rows.sort(key=lambda item: self._statement_sort_key(item), reverse=True)
        return rows[0]

    def _openapi_dataset(self, path: str) -> list[dict[str, Any]]:
        if path in self._dataset_cache:
            return self._dataset_cache[path]

        response = self._request_with_ssl_fallback(f"{self.openapi_base_url}{path}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError(f"TWSE OpenAPI returned unexpected payload for {path}")
        self._dataset_cache[path] = payload
        return payload

    def _enrich_annuals_from_local_snapshot(self, code: str, annual: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not annual:
            return annual

        snapshot = self._load_local_snapshot(code)
        if not snapshot:
            return annual

        local_annual = snapshot.get("financials", {}).get("annual", [])
        local_by_period = {str(item.get("period")): item for item in local_annual}
        enriched: list[dict[str, Any]] = []
        for item in annual:
            merged = dict(item)
            fallback = local_by_period.get(item["period"])
            if fallback:
                for key in (
                    "operating_cash_flow",
                    "accounts_receivable",
                    "inventory",
                    "goodwill",
                    "audit_opinion",
                    "related_party_revenue",
                    "rd_capitalization_rate",
                    "non_recurring_items",
                ):
                    if merged.get(key) is None and fallback.get(key) is not None:
                        merged[key] = fallback[key]
                if any(merged.get(key) is not None for key in ("operating_cash_flow", "accounts_receivable", "inventory", "goodwill")):
                    merged["source"] = "twse_openapi+local"
            enriched.append(merged)

        return self._merge_annuals(enriched, snapshot)

    @staticmethod
    def _merge_annuals(primary: list[dict[str, Any]], snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
        annual_by_period = {str(item.get("period")): item for item in primary}
        if snapshot:
            for item in snapshot.get("financials", {}).get("annual", []):
                annual_by_period.setdefault(str(item.get("period")), item)
        return sorted(annual_by_period.values(), key=lambda item: str(item.get("period") or ""), reverse=True)

    @staticmethod
    def _pick_value(row: dict[str, Any] | None, *keys: str) -> Any:
        if not row:
            return None
        for key in keys:
            if key in row and row[key] not in ("", None):
                return row[key]
        return None

    @staticmethod
    def _statement_sort_key(row: dict[str, Any]) -> tuple[int, int]:
        year = TwseClient._roc_year_to_gregorian(row.get("年度")) or 0
        try:
            season = int(str(row.get("季別") or 0))
        except ValueError:
            season = 0
        return year, season

    @staticmethod
    def _roc_year_to_gregorian(value: Any) -> int | None:
        text = str(value or "").strip()
        if not text.isdigit():
            return None
        year = int(text)
        if year < 1911:
            year += 1911
        return year

    @staticmethod
    def _season_as_of(year: int, season: str) -> str:
        season_map = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}
        return f"{year}-{season_map.get(str(season).strip(), '12-31')}"

    def _fetch_financial_annuals_from_finmind(self, code: str) -> list[dict[str, Any]]:
        income_df = self._finmind_dataset("FinancialStatements", code)
        balance_df = self._finmind_dataset("BalanceSheet", code)
        cashflow_df = self._finmind_dataset("TaiwanCashFlowsStatement", code)

        income_map = self._finmind_pivot(income_df, annual_only=True)
        balance_map = self._finmind_pivot(balance_df, annual_only=True)
        cashflow_map = self._finmind_pivot(cashflow_df, annual_only=True)

        periods = sorted(set(income_map) | set(balance_map) | set(cashflow_map), reverse=True)
        annual: list[dict[str, Any]] = []
        for period in periods:
            income = income_map.get(period, {})
            balance = balance_map.get(period, {})
            cashflow = cashflow_map.get(period, {})
            annual.append(
                {
                    "period": period[:4],
                    "revenue": self._number(income.get("Revenue")),
                    "net_profit": self._number(
                        income.get("EquityAttributableToOwnersOfParent"),
                        income.get("IncomeAfterTaxes"),
                    ),
                    "operating_cash_flow": self._number(
                        cashflow.get("CashFlowsFromOperatingActivities"),
                        cashflow.get("NetCashInflowFromOperatingActivities"),
                    ),
                    "accounts_receivable": self._number(balance.get("AccountsReceivableNet")),
                    "inventory": self._number(balance.get("Inventories")),
                    "goodwill": self._number(balance.get("Goodwill")),
                    "total_assets": self._number(balance.get("TotalAssets")),
                    "total_liabilities": self._number(balance.get("Liabilities")),
                    "non_recurring_items": None,
                    "related_party_revenue": None,
                    "rd_capitalization_rate": None,
                    "audit_opinion": None,
                    "source": "finmind",
                    "unit": "base_currency",
                    "as_of": period,
                }
            )
        return annual

    def live_source_available(self) -> bool:
        try:
            records = self._fetch_company_list_from_twse()
            self.last_source_mode = "live" if records else "fallback"
            self.last_live_provider = "twse_openapi" if records else None
            self.last_error = None if records else "TWSE OpenAPI returned zero records."
            return bool(records)
        except Exception as exc:
            self.last_error = f"twse_openapi -> {type(exc).__name__}: {exc}"

        try:
            records = self._fetch_company_list_from_isin()
            self.last_source_mode = "live" if records else "fallback"
            self.last_live_provider = "twse_isin" if records else None
            self.last_error = None if records else "TWSE ISIN page returned zero records."
            return bool(records)
        except Exception as exc:
            self.last_source_mode = "fallback"
            self.last_live_provider = None
            suffix = f" | twse_isin -> {type(exc).__name__}: {exc}"
            self.last_error = f"{self.last_error or ''}{suffix}".strip(" |")
            return False

    def _fetch_company_list_from_isin(self) -> list[dict[str, Any]]:
        response = self._request_with_ssl_fallback(self.isin_list_url)
        response.raise_for_status()

        tables = pd.read_html(response.text)
        if not tables:
            raise ValueError("No tables found in TWSE ISIN response.")

        # The first table contains listed equity data including code, name, date listed, and industry.
        raw = tables[0].copy()
        raw.columns = [str(col).strip() for col in raw.columns]

        security_column = next((col for col in raw.columns if "Security Code" in col or "有價證券代號及名稱" in col), None)
        listed_column = next((col for col in raw.columns if "Date Listed" in col or "上市日" in col), None)
        industry_column = next((col for col in raw.columns if "Industrial Group" in col or "產業別" in col), None)
        market_column = next((col for col in raw.columns if "Market" in col or "市場別" in col), None)

        if security_column is None:
            raise ValueError("TWSE ISIN table does not contain a security code/name column.")

        records: list[dict[str, Any]] = []
        for _, row in raw.iterrows():
            security = str(row.get(security_column, "")).strip()
            if not security or security.lower() == "nan":
                continue
            if security.startswith("Security Code") or security.startswith("有價證券代號"):
                continue

            market_value = str(row.get(market_column, "")).strip() if market_column else ""
            if market_value and "TWSE" not in market_value.upper():
                continue

            code_name = security.replace("\u3000", " ").split()
            if not code_name:
                continue

            code = code_name[0].strip()
            if not code.isdigit():
                continue

            name_en = " ".join(code_name[1:]).strip() or None
            records.append(
                {
                    "code": code.zfill(4),
                    "name": name_en or code,
                    "name_en": name_en,
                    "industry": str(row.get(industry_column, "")).strip() if industry_column else None,
                    "status": "active",
                    "ipo_date": str(row.get(listed_column, "")).strip() if listed_column else None,
                }
            )

        if not records:
            raise ValueError("TWSE ISIN table returned zero listed companies.")
        return records

    def _fetch_company_list_from_twse(self) -> list[dict[str, Any]]:
        response = self._request_with_ssl_fallback(self.company_list_url)
        response.raise_for_status()
        payload = response.json()

        records: list[dict[str, Any]] = []
        for row in payload:
            code = str(row.get("公司代號") or row.get("Code") or "").strip()
            name = str(row.get("公司名稱") or row.get("Name") or "").strip()
            if not code or not name:
                continue
            records.append(
                {
                    "code": code.zfill(4),
                    "name": name,
                    "name_en": row.get("CompanyNameEnglish") or row.get("英文簡稱"),
                    "industry": row.get("產業別"),
                    "status": "active",
                    "ipo_date": row.get("上市日期"),
                }
            )
        return records

    def _load_demo_company_list(self) -> list[dict[str, Any]]:
        snapshots = self._load_all_local_snapshots()
        return [
            {
                "code": item["code"],
                "name": item["name"],
                "name_en": item.get("name_en"),
                "industry": item.get("industry"),
                "status": "active",
                "ipo_date": None,
            }
            for item in snapshots
        ]

    def _load_all_local_snapshots(self) -> list[dict[str, Any]]:
        market_dir = self.data_dir / "tw"
        snapshots: list[dict[str, Any]] = []
        for path in market_dir.glob("*.json"):
            with path.open("r", encoding="utf-8") as file:
                snapshots.append(json.load(file))
        return sorted(snapshots, key=lambda item: item["code"])

    def _load_local_snapshot(self, code: str) -> dict[str, Any] | None:
        path = self.data_dir / "tw" / f"{code}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _request_with_ssl_fallback(self, url: str) -> requests.Response:
        try:
            return requests.get(url, timeout=self.timeout)
        except requests.exceptions.SSLError:
            return requests.get(url, timeout=self.timeout, verify=False)

    def _finmind_dataset(self, dataset: str, code: str) -> pd.DataFrame:
        response = requests.get(
            self.finmind_api_url,
            params={"dataset": dataset, "stock_id": code, "date": "2000-01-01"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        if not data:
            raise ValueError(f"FinMind dataset {dataset} returned no rows for {code}")
        return pd.DataFrame(data)

    @staticmethod
    def _finmind_pivot(df: pd.DataFrame, annual_only: bool = True) -> dict[str, dict[str, Any]]:
        if annual_only:
            df = df[df["date"].astype(str).str.endswith("-12-31")]
        mapping: dict[str, dict[str, Any]] = {}
        for row in df.to_dict(orient="records"):
            period = str(row["date"])
            type_key = str(row["type"])
            mapping.setdefault(period, {})[type_key] = row.get("value")
        return mapping

    @staticmethod
    def _number(*values: Any) -> float | None:
        for value in values:
            if value is None:
                continue
            if isinstance(value, float) and pd.isna(value):
                continue
            try:
                return float(value)
            except Exception:
                continue
        return None

    def _scaled_number(self, *values: Any, scale: float | None = None) -> float | None:
        number = self._number(*values)
        if number is None:
            return None
        return number * (scale or self.openapi_amount_scale)
