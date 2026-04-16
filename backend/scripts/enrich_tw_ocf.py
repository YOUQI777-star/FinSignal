"""Rate-limited enrichment of operating_cash_flow for TW snapshots via FinMind.

TWSE OpenAPI does not expose a cash flow statement endpoint, so OCF must come
from FinMind. This script fetches only what's missing and writes it back to the
snapshot files. Run it as a background job to avoid hitting FinMind free-tier limits.

Usage:
    .venv/bin/python -m backend.scripts.enrich_tw_ocf
    .venv/bin/python -m backend.scripts.enrich_tw_ocf --delay 3.0 --limit 50
    .venv/bin/python -m backend.scripts.enrich_tw_ocf --dry-run
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from backend.config import DATA_DIR
from backend.scrapers.tw_twse import TwseClient


def _enrich_snapshot_ocf(snapshot: dict, client: TwseClient) -> bool:
    """Fetch OCF from FinMind and merge into snapshot annual records.
    Returns True if any OCF value was written.
    """
    code = snapshot["code"]
    annual = snapshot.get("financials", {}).get("annual", [])
    if not annual:
        return False

    finmind_annual = client._fetch_financial_annuals_from_finmind(code)
    ocf_by_period = {
        str(r.get("period", ""))[:4]: r.get("operating_cash_flow")
        for r in finmind_annual
    }

    changed = False
    for record in annual:
        period = str(record.get("period", ""))
        if record.get("operating_cash_flow") is None and ocf_by_period.get(period) is not None:
            record["operating_cash_flow"] = ocf_by_period[period]
            changed = True

    return changed


def run(
    delay: float = 2.0,
    limit: int = 0,
    dry_run: bool = False,
    data_dir: Path = DATA_DIR,
) -> dict[str, int]:
    client = TwseClient(data_dir=data_dir)
    tw_dir = data_dir / "tw"

    # collect candidates: companies that have annual data but no OCF in latest period
    candidates: list[tuple[Path, dict]] = []
    for path in sorted(tw_dir.glob("*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        annual = snapshot.get("financials", {}).get("annual", [])
        if annual and annual[0].get("operating_cash_flow") is None:
            candidates.append((path, snapshot))

    print(f"Companies missing OCF: {len(candidates)}")
    if limit:
        candidates = candidates[:limit]
        print(f"Processing first {limit} (--limit)")

    stats = {"updated": 0, "failed": 0, "no_data": 0, "total": len(candidates)}

    for idx, (path, snapshot) in enumerate(candidates):
        code = snapshot["code"]
        prefix = f"[{idx + 1}/{len(candidates)}] {code}"
        try:
            changed = _enrich_snapshot_ocf(snapshot, client)
            if changed:
                stats["updated"] += 1
                if not dry_run:
                    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"{prefix} enriched")
            else:
                stats["no_data"] += 1
                print(f"{prefix} no OCF in FinMind")
        except Exception as exc:
            stats["failed"] += 1
            print(f"{prefix} FAILED: {exc}")

        if idx < len(candidates) - 1:
            time.sleep(delay)

    print(f"\nDone ({'DRY RUN' if dry_run else 'files updated'}):")
    print(f"  Updated  : {stats['updated']}")
    print(f"  No data  : {stats['no_data']}")
    print(f"  Failed   : {stats['failed']}")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rate-limited TW OCF enrichment via FinMind."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to sleep between FinMind requests (default: 2.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max companies to process per run (0 = all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(delay=args.delay, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
