from __future__ import annotations

import argparse
import json

from backend.data_access.turnover_history_store import TurnoverHistoryStore
from backend.data_access.master_store import MasterDataStore
from backend.screening.candidate_rules import (
    DEFAULT_CIRC_MV_MAX,
    DEFAULT_EXCLUDE_ST,
    DEFAULT_PCT_MAX,
    DEFAULT_PCT_MIN,
    DEFAULT_PRICE_MAX,
    DEFAULT_TURNOVER_MIN,
    apply_rules,
    is_st,
)
from backend.screening.market_loader import get_recent_trading_dates
from backend.screening.screening_service import get_candidates
from backend.screening.turnover_bootstrap import bootstrap_structure_history


def _candidate_codes() -> list[str]:
    try:
        payload = get_candidates()
        return [
            str(item.get("code", "")).strip()
            for item in payload.get("candidates", [])
            if item.get("code")
        ]
    except Exception:
        return _candidate_codes_from_history()


def _candidate_codes_from_history() -> list[str]:
    store = TurnoverHistoryStore()
    trading_date = store.latest_date("CN")
    if not trading_date:
        dates = get_recent_trading_dates(1)
        if not dates:
            return []
        trading_date = dates[-1]
    master = MasterDataStore()
    rows = store.list_rows_for_date("CN", trading_date)
    codes: list[str] = []
    for row in rows:
        profile = master.get_company("CN", str(row.get("code", "")).strip()) or {}
        name = str(profile.get("name") or "")
        candidate_row = {
            "name": name,
            "price": row.get("close"),
            "turnover": row.get("turnover_rate"),
            "circ_mv_yi": _normalize_circ_mv_yi(row.get("circ_mv")),
            "pct_change": row.get("pct_change"),
            "is_st": is_st(name),
        }
        passed, _, _ = apply_rules(
            candidate_row,
            turnover_min=DEFAULT_TURNOVER_MIN,
            price_max=DEFAULT_PRICE_MAX,
            circ_mv_max=DEFAULT_CIRC_MV_MAX,
            pct_max=DEFAULT_PCT_MAX,
            pct_min=DEFAULT_PCT_MIN,
            exclude_st=DEFAULT_EXCLUDE_ST,
        )
        if passed:
            codes.append(str(row.get("code", "")).strip())
    return codes


def _normalize_circ_mv_yi(value) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric / 10000, 2) if numeric > 1000 else round(numeric, 2)


def _market_codes(market: str) -> list[str]:
    return MasterDataStore().list_company_codes(market)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap CN structure-scoring history from Tushare Pro into turnover_history.db")
    parser.add_argument("--market", default="CN", help="Market scope. v1 only supports CN.")
    parser.add_argument("--scope", choices=["candidates", "market"], default="candidates", help="Backfill latest candidates or the whole market master list.")
    parser.add_argument("--days", type=int, default=60, help="Recent trading days to backfill for structure scoring.")
    parser.add_argument("--max-codes", type=int, default=None, help="Optional cap for testing.")
    parser.add_argument("--retry-limit", type=int, default=3, help="Retry attempts per code.")
    parser.add_argument("--sleep-seconds", type=float, default=0.25, help="Pause between requests.")
    args = parser.parse_args()

    market = args.market.upper()
    if args.scope == "candidates":
        codes = _candidate_codes()
    else:
        codes = _market_codes(market)

    summary = bootstrap_structure_history(
        market=market,
        days=args.days,
        codes=codes,
        max_codes=args.max_codes,
        retry_limit=args.retry_limit,
        sleep_seconds=args.sleep_seconds,
        meta_scope=args.scope,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
