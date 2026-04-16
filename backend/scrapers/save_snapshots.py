from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from backend.config import DATA_DIR
from backend.data_access.coverage import snapshot_tier
from backend.master.build_master import MASTER_DB_PATH
from backend.scrapers.cn_akshare import AkshareCNClient
from backend.scrapers.tw_twse import TwseClient


def load_company_master(db_path: Path, market: str | None = None) -> list[dict[str, str]]:
    if not db_path.exists():
        raise FileNotFoundError(f"company_master database not found: {db_path}")

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.cursor()
        if market:
            cursor.execute(
                """
                SELECT company_id, market, code, name
                FROM company_master
                WHERE market = ?
                ORDER BY code
                """,
                (market.upper(),),
            )
        else:
            cursor.execute(
                """
                SELECT company_id, market, code, name
                FROM company_master
                ORDER BY market, code
                """
            )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def save_snapshot(snapshot: dict, output_dir: Path) -> Path:
    market = snapshot["market"].lower()
    code = snapshot["code"]
    market_dir = output_dir / market
    market_dir.mkdir(parents=True, exist_ok=True)
    path = market_dir / f"{code}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=2)
    return path


def snapshot_exists(output_dir: Path, market: str, code: str) -> bool:
    return (output_dir / market.lower() / f"{code}.json").exists()


def existing_snapshot_tier(output_dir: Path, market: str, code: str) -> str | None:
    path = output_dir / market.lower() / f"{code}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return snapshot_tier(payload)


def write_sync_report(output_dir: Path, market: str | None, report: dict) -> Path:
    report_dir = output_dir / "sync_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    suffix = market.lower() if market else "all"
    path = report_dir / f"{suffix}_latest.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return path


def run_full_snapshot_sync(
    *,
    db_path: Path = MASTER_DB_PATH,
    output_dir: Path = DATA_DIR,
    market: str | None = None,
    require_live: bool = False,
    skip_existing: bool = False,
    refresh_shell_only: bool = False,
) -> dict[str, int]:
    companies = load_company_master(db_path, market=market)
    cn_client = AkshareCNClient(data_dir=output_dir)
    tw_client = TwseClient(data_dir=output_dir)

    summary = {"total": len(companies), "saved": 0, "failed": 0, "skipped": 0}
    failures: list[dict[str, str]] = []

    for company in companies:
        if refresh_shell_only:
            tier = existing_snapshot_tier(output_dir, company["market"], company["code"])
            if tier not in (None, "shell_only"):
                summary["skipped"] += 1
                continue
        if skip_existing and snapshot_exists(output_dir, company["market"], company["code"]):
            summary["skipped"] += 1
            continue
        try:
            if company["market"] == "CN":
                try:
                    snapshot = cn_client.fetch_company_snapshot(company["code"], require_live=require_live)
                except Exception:
                    snapshot = cn_client.fetch_company_snapshot_with_baostock_fallback(company["code"])
            else:
                snapshot = tw_client.fetch_company_snapshot(company["code"], require_live=require_live)
            save_snapshot(snapshot, output_dir)
            summary["saved"] += 1
        except Exception as exc:
            summary["failed"] += 1
            failures.append(
                {
                    "company_id": company["company_id"],
                    "market": company["market"],
                    "code": company["code"],
                    "name": company["name"],
                    "error": str(exc),
                }
            )
            print(f"[FAILED] {company['company_id']} {company['name']}: {exc}")

    report = {"summary": summary, "failures": failures}
    report_path = write_sync_report(output_dir, market, report)
    summary["report_path"] = str(report_path)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save normalized company snapshots from company_master.")
    parser.add_argument("--db-path", default=str(MASTER_DB_PATH), help="Path to company_master database.")
    parser.add_argument("--output-dir", default=str(DATA_DIR), help="Directory to write company snapshots.")
    parser.add_argument("--market", choices=["CN", "TW"], help="Only sync a single market.")
    parser.add_argument("--require-live", action="store_true", help="Fail snapshot sync if live upstream data is unavailable.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip companies whose snapshot JSON already exists.")
    parser.add_argument("--refresh-shell-only", action="store_true", help="Only refresh companies whose existing snapshot tier is shell_only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_full_snapshot_sync(
        db_path=Path(args.db_path),
        output_dir=Path(args.output_dir),
        market=args.market,
        require_live=args.require_live,
        skip_existing=args.skip_existing,
        refresh_shell_only=args.refresh_shell_only,
    )
    print(summary)


if __name__ == "__main__":
    main()
