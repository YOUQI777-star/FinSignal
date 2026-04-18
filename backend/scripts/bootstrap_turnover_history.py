from __future__ import annotations

import argparse

from backend.screening.turnover_bootstrap import bootstrap_recent_turnover_history_for_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap recent CN turnover history for latest fulfilled candidates into SQLite.")
    parser.add_argument("--days", type=int, default=10, help="Number of recent trading days to backfill.")
    parser.add_argument("--max-codes", type=int, default=None, help="Optional code cap for testing.")
    parser.add_argument("--retry-limit", type=int, default=3, help="Retry attempts per code.")
    parser.add_argument("--sleep-seconds", type=float, default=0.8, help="Pause between requests.")
    args = parser.parse_args()

    bootstrap_recent_turnover_history_for_candidates(
        days=args.days,
        max_codes=args.max_codes,
        retry_limit=args.retry_limit,
        sleep_seconds=args.sleep_seconds,
    )


if __name__ == "__main__":
    main()
