from __future__ import annotations

import argparse
import json

from backend.config import DATA_DIR
from backend.data_access.turnover_history_store import TurnoverHistoryStore
from backend.screening.turnover_bootstrap import bootstrap_structure_history
from backend.scripts.bootstrap_structure_history import _candidate_codes, _market_codes
from backend.screening.screening_service import get_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture today's CN snapshot and optionally top up structure history.")
    parser.add_argument("--market", default="CN", help="Market scope. v1 only supports CN.")
    parser.add_argument("--force-refresh", action="store_true", help="Force realtime refresh when capturing today's snapshot.")
    parser.add_argument("--skip-structure", action="store_true", help="Only capture today's snapshot, skip Tushare history top-up.")
    parser.add_argument("--structure-scope", choices=["candidates", "market"], default="candidates", help="Which code universe to top up for structure history.")
    parser.add_argument("--structure-days", type=int, default=60, help="Recent trading days to keep complete for structure scoring.")
    parser.add_argument("--max-codes", type=int, default=None, help="Optional cap for testing.")
    parser.add_argument("--retry-limit", type=int, default=3, help="Retry attempts per code for history top-up.")
    parser.add_argument("--sleep-seconds", type=float, default=0.1, help="Pause between Tushare history requests.")
    args = parser.parse_args()

    market = args.market.upper()
    if market != "CN":
        raise ValueError("Only CN is supported for daily maintenance in v1")

    snapshot = get_candidates(force_refresh=args.force_refresh)
    trading_date = str(snapshot.get("trading_date") or "")
    store = TurnoverHistoryStore()
    snapshot_stats = store.date_stats(market, trading_date) if trading_date else {}

    payload: dict[str, object] = {
        "data_dir": str(DATA_DIR),
        "snapshot": {
            "trading_date": trading_date,
            "generated_at": snapshot.get("generated_at"),
            "total_candidates": snapshot.get("total"),
            "source": snapshot.get("source"),
            "stats": snapshot_stats,
        },
    }

    if not args.skip_structure:
        codes = _candidate_codes() if args.structure_scope == "candidates" else _market_codes(market)
        payload["structure"] = bootstrap_structure_history(
            market=market,
            days=args.structure_days,
            codes=codes,
            max_codes=args.max_codes,
            retry_limit=args.retry_limit,
            sleep_seconds=args.sleep_seconds,
            meta_scope=f"daily_{args.structure_scope}",
        )

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
