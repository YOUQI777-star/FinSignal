from __future__ import annotations

import argparse
import json

from backend.screening.turnover_bootstrap import hydrate_single_code_turnover_history


def main() -> None:
    parser = argparse.ArgumentParser(description="Hydrate turnover history for a single CN stock into SQLite.")
    parser.add_argument("--code", required=True, help="6-digit CN stock code")
    parser.add_argument("--days", type=int, default=10, help="Number of recent trading days to backfill")
    args = parser.parse_args()

    rows = hydrate_single_code_turnover_history(args.code, days=args.days)
    payload = {
        "code": args.code,
        "days": args.days,
        "total": len(rows),
        "latest": rows[-1] if rows else None,
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
