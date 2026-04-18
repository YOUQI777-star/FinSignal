from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from backend.config import DATA_DIR


class TurnoverHistoryStore:
    """SQLite-backed daily turnover history store."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (DATA_DIR / "turnover_history.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turnover_history (
                    market TEXT NOT NULL,
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    turnover_rate REAL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (market, code, date)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_turnover_history_lookup
                ON turnover_history (market, code, date)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turnover_history_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def upsert_daily_rows(
        self,
        market: str,
        trading_date: str,
        rows: list[dict[str, Any]],
        *,
        updated_at: str,
    ) -> None:
        payload = [
            (
                market.upper(),
                str(row.get("code", "")).strip(),
                trading_date,
                row.get("turnover"),
                updated_at,
            )
            for row in rows
            if row.get("code")
        ]
        if not payload:
            return

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO turnover_history (market, code, date, turnover_rate, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(market, code, date) DO UPDATE SET
                    turnover_rate = excluded.turnover_rate,
                    updated_at = excluded.updated_at
                """,
                payload,
            )

    def upsert_records(self, records: list[dict[str, Any]]) -> None:
        payload = [
            (
                str(record.get("market", "")).upper(),
                str(record.get("code", "")).strip(),
                str(record.get("date", "")).strip(),
                record.get("turnover_rate"),
                str(record.get("updated_at", "")).strip(),
            )
            for record in records
            if record.get("market") and record.get("code") and record.get("date") and record.get("updated_at")
        ]
        if not payload:
            return

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO turnover_history (market, code, date, turnover_rate, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(market, code, date) DO UPDATE SET
                    turnover_rate = excluded.turnover_rate,
                    updated_at = excluded.updated_at
                """,
                payload,
            )

    def get_history(
        self,
        market: str,
        code: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        days: int | None = None,
    ) -> list[dict[str, Any]]:
        market = market.upper()
        code = code.strip()

        if days and not start_date and not end_date:
            end = date.today()
            start = end - timedelta(days=max(days * 2, days))
            start_date = start.isoformat()
            end_date = end.isoformat()

        query = """
            SELECT market, code, date, turnover_rate, updated_at
            FROM turnover_history
            WHERE market = ? AND code = ?
        """
        params: list[Any] = [market, code]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date ASC"

        with self._connect() as conn:
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]

        if days and len(rows) > days:
            rows = rows[-days:]
        return rows

    def get_meta(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM turnover_history_meta WHERE key = ?",
                (key,),
            ).fetchone()
        return str(row["value"]) if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO turnover_history_meta (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
