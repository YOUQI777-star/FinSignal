from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from backend.config import BASE_DIR, DATA_DIR


MASTER_DIR = BASE_DIR / "master"
MASTER_DB_PATH = MASTER_DIR / "company_master.db"


@dataclass(frozen=True)
class CompanyMasterRecord:
    code: str
    market: str
    name: str
    name_en: str | None = None
    industry_sw: str | None = None
    industry_twse: str | None = None
    status: str = "active"
    ipo_date: str | None = None
    updated_at: str = ""


def build_company_master(
    *,
    db_path: Path = MASTER_DB_PATH,
    include_cn: bool = True,
    include_tw: bool = True,
    require_live: bool = False,
) -> dict[str, int]:
    from backend.scrapers.cn_akshare import AkshareCNClient
    from backend.scrapers.tw_twse import TwseClient

    records: list[CompanyMasterRecord] = []
    updated_at = datetime.now(timezone.utc).isoformat()

    if include_cn:
        cn_client = AkshareCNClient()
        if require_live and not cn_client.live_source_available():
            raise RuntimeError("AKShare live company list is unavailable.")
        records.extend(
            CompanyMasterRecord(
                code=item["code"],
                market="CN",
                name=item["name"],
                industry_sw=item.get("industry"),
                status=item.get("status", "active"),
                ipo_date=item.get("ipo_date"),
                updated_at=updated_at,
            )
            for item in cn_client.list_companies()
        )

    if include_tw:
        tw_client = TwseClient()
        if require_live and not tw_client.live_source_available():
            raise RuntimeError("TWSE live company list is unavailable.")
        records.extend(
            CompanyMasterRecord(
                code=item["code"],
                market="TW",
                name=item["name"],
                name_en=item.get("name_en"),
                industry_twse=item.get("industry"),
                status=item.get("status", "active"),
                ipo_date=item.get("ipo_date"),
                updated_at=updated_at,
            )
            for item in tw_client.list_companies()
        )

    return write_master_db(db_path, records)


def write_master_db(db_path: Path, records: Iterable[CompanyMasterRecord]) -> dict[str, int]:
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS company_master (
                company_id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                market TEXT NOT NULL,
                name TEXT NOT NULL,
                name_en TEXT,
                industry_sw TEXT,
                industry_twse TEXT,
                status TEXT NOT NULL,
                ipo_date TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute("DELETE FROM company_master")

        count = 0
        market_counts: dict[str, int] = {}
        for record in records:
            company_id = f"{record.market}:{record.code}"
            cursor.execute(
                """
                INSERT INTO company_master (
                    company_id, code, market, name, name_en,
                    industry_sw, industry_twse, status, ipo_date, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    record.code,
                    record.market,
                    record.name,
                    record.name_en,
                    record.industry_sw,
                    record.industry_twse,
                    record.status,
                    record.ipo_date,
                    record.updated_at,
                ),
            )
            count += 1
            market_counts[record.market] = market_counts.get(record.market, 0) + 1

        connection.commit()
        return {"total": count, **market_counts}
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the company_master SQLite database.")
    parser.add_argument("--db-path", default=str(MASTER_DB_PATH), help="Output SQLite database path.")
    parser.add_argument("--cn-only", action="store_true", help="Only include CN market companies.")
    parser.add_argument("--tw-only", action="store_true", help="Only include TW market companies.")
    parser.add_argument("--require-live", action="store_true", help="Fail unless live upstream data sources are available.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_cn = not args.tw_only
    include_tw = not args.cn_only
    summary = build_company_master(
        db_path=Path(args.db_path),
        include_cn=include_cn,
        include_tw=include_tw,
        require_live=args.require_live,
    )
    print(f"company_master built at {Path(args.db_path)}")
    print(summary)


if __name__ == "__main__":
    main()
