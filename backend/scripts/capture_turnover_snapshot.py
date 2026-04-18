from __future__ import annotations

import argparse
import json

from backend.screening.screening_service import get_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture today's CN turnover snapshot into turnover_history.db.")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force a fresh realtime fetch instead of using the in-memory cache.",
    )
    args = parser.parse_args()

    result = get_candidates(force_refresh=args.force_refresh)
    payload = {
        "trading_date": result.get("trading_date"),
        "generated_at": result.get("generated_at"),
        "total_candidates": result.get("total"),
        "source": result.get("source"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
