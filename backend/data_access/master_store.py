from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from backend.master.build_master import MASTER_DB_PATH


class MasterDataStore:
    """SQLite-backed access layer for company_master."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or MASTER_DB_PATH

    def get_company(self, market: str, code: str) -> dict[str, Any] | None:
        row = self._fetch_one(
            """
            SELECT
                company_id, code, market, name, name_en,
                industry_sw, industry_twse, status, ipo_date, updated_at
            FROM company_master
            WHERE market = ? AND code = ?
            """,
            (market.upper(), code),
        )
        return self._row_to_company(row) if row else None

    def search_companies(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        normalized = query.strip()
        if not normalized:
            return []

        pattern = f"%{normalized.lower()}%"
        rows = self._fetch_all(
            """
            SELECT
                company_id, code, market, name, name_en,
                industry_sw, industry_twse, status, ipo_date, updated_at
            FROM company_master
            WHERE lower(code) LIKE ?
               OR lower(name) LIKE ?
               OR lower(COALESCE(name_en, '')) LIKE ?
               OR lower(company_id) LIKE ?
            ORDER BY market, code
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, limit),
        )
        return [self._row_to_company(row) for row in rows]

    def list_company_codes(self, market: str) -> list[str]:
        rows = self._fetch_all(
            """
            SELECT code
            FROM company_master
            WHERE market = ?
            ORDER BY code
            """,
            (market.upper(),),
        )
        return [str(row["code"]) for row in rows]

    def _connect(self) -> sqlite3.Connection | None:
        if not self.db_path.exists():
            return None
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _fetch_one(self, query: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
        connection = self._connect()
        if connection is None:
            return None
        try:
            cursor = connection.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            connection.close()

    def _fetch_all(self, query: str, params: tuple[Any, ...]) -> list[sqlite3.Row]:
        connection = self._connect()
        if connection is None:
            return []
        try:
            cursor = connection.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            connection.close()

    @staticmethod
    def _row_to_company(row: sqlite3.Row) -> dict[str, Any]:
        market = row["market"]
        industry = row["industry_sw"] if market == "CN" else row["industry_twse"]
        return {
            "company_id": row["company_id"],
            "code": row["code"],
            "market": market,
            "name": row["name"],
            "name_en": row["name_en"],
            "industry": industry,
            "status": row["status"],
            "ipo_date": row["ipo_date"],
            "updated_at": row["updated_at"],
        }
