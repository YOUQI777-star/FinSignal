"""Bulk-enrich CN snapshots using EastMoney all-market financials.

Fetches balance sheet, income statement, and cash flow for all A-share companies
in a single batch call per year, then merges missing fields into existing snapshots.

Note on 2025: as of April 2026, only ~1660 companies have filed 2025 annual reports.
Use --include-2025 only when you want partial coverage of early-filers.

Usage:
    .venv/bin/python -m backend.scripts.bulk_enrich_cn
    .venv/bin/python -m backend.scripts.bulk_enrich_cn --years 2024 2023 2022
    .venv/bin/python -m backend.scripts.bulk_enrich_cn --include-2025
    .venv/bin/python -m backend.scripts.bulk_enrich_cn --dry-run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.config import DATA_DIR
from backend.data_access.coverage import CORE_FINANCIAL_FIELDS, snapshot_tier
from backend.scrapers.cn_akshare import AkshareCNClient

_ENRICH_FIELDS = (
    "revenue",
    "net_profit",
    "operating_cash_flow",
    "accounts_receivable",
    "inventory",
    "total_assets",
    "total_liabilities",
)

_DEFAULT_YEARS = [2024, 2023, 2022, 2021]


def _merge_em_into_snapshot(
    snapshot: dict,
    bulk_by_year: dict[int, dict[str, dict]],
) -> bool:
    """Merge EastMoney bulk records into snapshot. Returns True if snapshot was modified."""
    code = snapshot["code"]
    annual = snapshot.setdefault("financials", {}).setdefault("annual", [])
    by_period = {str(r.get("period")): r for r in annual}
    changed = False

    for year, bulk in bulk_by_year.items():
        em_record = bulk.get(code)
        if em_record is None:
            continue
        period = str(year)
        if period not in by_period:
            by_period[period] = em_record
            changed = True
        else:
            existing = by_period[period]
            for field in _ENRICH_FIELDS:
                if existing.get(field) is None and em_record.get(field) is not None:
                    existing[field] = em_record[field]
                    changed = True

    if changed:
        snapshot["financials"]["annual"] = sorted(
            by_period.values(),
            key=lambda r: str(r.get("period", "")),
            reverse=True,
        )
        # refresh coverage
        latest = snapshot["financials"]["annual"][0]
        populated = sum(1 for f in CORE_FINANCIAL_FIELDS if latest.get(f) is not None)
        snapshot["coverage"] = {
            "available_rules": ["F1", "F2", "F3"] if populated >= 4 else [],
            "missing_fields": ["governance"] + [f for f in CORE_FINANCIAL_FIELDS if latest.get(f) is None],
        }

    return changed


def run(
    years: list[int] = _DEFAULT_YEARS,
    data_dir: Path = DATA_DIR,
    dry_run: bool = False,
) -> dict[str, int]:
    client = AkshareCNClient(data_dir=data_dir)
    cn_dir = data_dir / "cn"

    print(f"Fetching EastMoney bulk data for years: {years}")
    bulk_by_year: dict[int, dict[str, dict]] = {}
    for year in years:
        print(f"  {year}... ", end="", flush=True)
        try:
            bulk_by_year[year] = client.fetch_bulk_annual_from_em(year)
            print(f"{len(bulk_by_year[year])} records")
        except Exception as exc:
            print(f"FAILED: {exc}")

    if not bulk_by_year:
        print("No bulk data fetched. Aborting.")
        return {"updated": 0, "skipped": 0, "total": 0}

    stats = {"updated": 0, "skipped": 0, "total": 0}
    snapshots = sorted(cn_dir.glob("*.json"))
    stats["total"] = len(snapshots)

    tier_before: dict[str, int] = {}
    tier_after: dict[str, int] = {}

    for path in snapshots:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        tier_before[snapshot_tier(snapshot)] = tier_before.get(snapshot_tier(snapshot), 0) + 1

        changed = _merge_em_into_snapshot(snapshot, bulk_by_year)
        tier_after[snapshot_tier(snapshot)] = tier_after.get(snapshot_tier(snapshot), 0) + 1

        if changed:
            stats["updated"] += 1
            if not dry_run:
                path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            stats["skipped"] += 1

    print(f"\nResults ({'DRY RUN — no files written' if dry_run else 'files updated'}):")
    print(f"  Total snapshots : {stats['total']}")
    print(f"  Updated         : {stats['updated']}")
    print(f"  Unchanged       : {stats['skipped']}")
    print(f"\nTier before: {tier_before}")
    print(f"Tier after : {tier_after}")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk-enrich CN snapshots from EastMoney all-market financials.")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        metavar="YEAR",
        help=f"Years to fetch (default: {_DEFAULT_YEARS}). Overrides --include-2025.",
    )
    parser.add_argument(
        "--include-2025",
        action="store_true",
        help="Prepend 2025 to the year list. Note: as of April 2026 only ~1660 companies have filed.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print stats without writing files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    years = args.years or list(_DEFAULT_YEARS)
    if args.include_2025 and 2025 not in years:
        years = [2025] + years
    run(years=years, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
