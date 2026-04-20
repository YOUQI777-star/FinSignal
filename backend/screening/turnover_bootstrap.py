from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from backend.data_access.turnover_history_store import TurnoverHistoryStore
from backend.screening.candidate_scoring import clear_candidate_score_caches
from backend.screening.market_loader import fetch_turnover_history_for_code, get_recent_trading_dates

log = logging.getLogger(__name__)

BOOTSTRAP_META_KEY = "bootstrap_cn_candidates_recent_10d_until"
STRUCTURE_BOOTSTRAP_META_PREFIX = "bootstrap_cn_structure_60d"


def hydrate_single_code_turnover_history(
    code: str,
    *,
    market: str = "CN",
    days: int = 10,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Fetch and persist turnover history for one stock, then return stored rows."""
    market = market.upper()
    if market != "CN":
        raise ValueError("Only CN turnover history hydration is supported in v1")

    store = TurnoverHistoryStore()
    if start_date or end_date:
        recent_dates = get_recent_trading_dates(max(days, 30))
        start = start_date or (recent_dates[0] if recent_dates else "")
        end = end_date or (recent_dates[-1] if recent_dates else "")
        expected_dates = {d for d in recent_dates if (not start or d >= start) and (not end or d <= end)}
    else:
        recent_dates = get_recent_trading_dates(days)
        if not recent_dates:
            return []
        start = recent_dates[0]
        end = recent_dates[-1]
        expected_dates = set(recent_dates)

    updated_at = datetime.now(timezone.utc).isoformat()
    rows = fetch_turnover_history_for_code(code, start_date=start, end_date=end)
    records = [
        {
            "market": market,
            "code": str(code).strip(),
            "date": row["date"],
            "turnover_rate": row["turnover_rate"],
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "pct_change": row.get("pct_change"),
            "volume": row.get("volume"),
            "amount": row.get("amount"),
            "circ_mv": row.get("circ_mv"),
            "updated_at": updated_at,
        }
        for row in rows
        if not expected_dates or row.get("date") in expected_dates
    ]
    store.upsert_records(records)
    clear_candidate_score_caches()
    return store.get_history(
        market,
        str(code).strip(),
        start_date=start_date,
        end_date=end_date,
        days=days if not (start_date or end_date) else None,
    )


def bootstrap_recent_turnover_history_for_candidates(
    *,
    market: str = "CN",
    days: int = 10,
    max_codes: int | None = None,
    retry_limit: int = 3,
    sleep_seconds: float = 0.8,
) -> None:
    market = market.upper()
    if market != "CN":
        raise ValueError("Only CN turnover bootstrap is supported in v1")

    store = TurnoverHistoryStore()
    dates = get_recent_trading_dates(days)
    if not dates:
        log.warning("[turnover-bootstrap] No trading dates available; skip.")
        return

    from backend.screening.screening_service import get_candidates

    candidate_payload = get_candidates()
    candidate_rows = candidate_payload.get("candidates", [])
    latest_date = str(candidate_payload.get("trading_date") or dates[-1])
    if store.get_meta(BOOTSTRAP_META_KEY) == latest_date:
        log.info("[turnover-bootstrap] Candidate turnover history already bootstrapped through %s.", latest_date)
        return

    codes = sorted({str(row.get("code", "")).strip() for row in candidate_rows if row.get("code")})
    if max_codes is not None:
        codes = codes[:max_codes]
    if not codes:
        log.warning("[turnover-bootstrap] No fulfilled %s candidate codes found for %s.", market, latest_date)
        return

    start_date = dates[0]
    end_date = dates[-1]
    updated_at = datetime.now(timezone.utc).isoformat()

    log.info(
        "[turnover-bootstrap] Bootstrapping %s %dd turnover history for %d fulfilled candidates on %s (%s → %s) ...",
        market,
        days,
        len(codes),
        latest_date,
        start_date,
        end_date,
    )

    success = 0
    failed = 0
    for idx, code in enumerate(codes, start=1):
        code_ok = False
        last_exc: Exception | None = None
        for attempt in range(1, retry_limit + 1):
            try:
                rows = fetch_turnover_history_for_code(code, start_date=start_date, end_date=end_date)
                records = [
                    {
                        "market": market,
                        "code": code,
                        "date": row["date"],
                        "turnover_rate": row["turnover_rate"],
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "close": row.get("close"),
                        "pct_change": row.get("pct_change"),
                        "volume": row.get("volume"),
                        "amount": row.get("amount"),
                        "circ_mv": row.get("circ_mv"),
                        "updated_at": updated_at,
                    }
                    for row in rows
                    if row.get("date") in dates
                ]
                store.upsert_records(records)
                clear_candidate_score_caches()
                success += 1
                code_ok = True
                break
            except Exception as exc:
                last_exc = exc
                if attempt < retry_limit:
                    time.sleep(sleep_seconds * attempt)
        if not code_ok:
            failed += 1
            if failed <= 10:
                log.warning("[turnover-bootstrap] %s failed after %d attempts: %s", code, retry_limit, last_exc)

        if idx % 200 == 0 or idx == len(codes):
            log.info(
                "[turnover-bootstrap] progress %d/%d | success=%d failed=%d",
                idx,
                len(codes),
                success,
                failed,
            )
        time.sleep(sleep_seconds)

    if success > 0:
        store.set_meta(BOOTSTRAP_META_KEY, latest_date)
    log.info(
        "[turnover-bootstrap] Done. success=%d failed=%d latest_date=%s",
        success,
        failed,
        latest_date,
    )


def bootstrap_structure_history(
    *,
    market: str = "CN",
    days: int = 60,
    codes: list[str] | None = None,
    max_codes: int | None = None,
    retry_limit: int = 3,
    sleep_seconds: float = 0.25,
    meta_scope: str = "custom",
) -> dict[str, object]:
    market = market.upper()
    if market != "CN":
        raise ValueError("Only CN structure bootstrap is supported in v1")

    store = TurnoverHistoryStore()
    recent_dates = get_recent_trading_dates(days)
    if not recent_dates:
        raise RuntimeError("No trading dates available for structure bootstrap")

    if not codes:
        raise ValueError("No codes provided for structure bootstrap")

    normalized_codes = sorted({str(code).strip() for code in codes if str(code).strip()})
    if max_codes is not None:
        normalized_codes = normalized_codes[:max_codes]
    if not normalized_codes:
        raise ValueError("No valid codes provided for structure bootstrap")

    latest_date = recent_dates[-1]
    start_date = recent_dates[0]
    end_date = recent_dates[-1]
    meta_key = f"{STRUCTURE_BOOTSTRAP_META_PREFIX}_{meta_scope}_{days}d_until"
    updated_at = datetime.now(timezone.utc).isoformat()

    log.info(
        "[structure-bootstrap] market=%s scope=%s days=%d codes=%d range=%s→%s",
        market,
        meta_scope,
        days,
        len(normalized_codes),
        start_date,
        end_date,
    )

    success = 0
    failed = 0
    for idx, code in enumerate(normalized_codes, start=1):
        code_ok = False
        last_exc: Exception | None = None
        for attempt in range(1, retry_limit + 1):
            try:
                rows = fetch_turnover_history_for_code(code, start_date=start_date, end_date=end_date)
                records = [
                    {
                        "market": market,
                        "code": code,
                        "date": row["date"],
                        "turnover_rate": row.get("turnover_rate"),
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "close": row.get("close"),
                        "pct_change": row.get("pct_change"),
                        "volume": row.get("volume"),
                        "amount": row.get("amount"),
                        "circ_mv": row.get("circ_mv"),
                        "updated_at": updated_at,
                    }
                    for row in rows
                    if row.get("date") in recent_dates
                ]
                store.upsert_records(records)
                success += 1
                code_ok = True
                break
            except Exception as exc:
                last_exc = exc
                if attempt < retry_limit:
                    time.sleep(sleep_seconds * attempt)
        if not code_ok:
            failed += 1
            if failed <= 10:
                log.warning("[structure-bootstrap] %s failed after %d attempts: %s", code, retry_limit, last_exc)

        if idx % 200 == 0 or idx == len(normalized_codes):
            log.info(
                "[structure-bootstrap] progress %d/%d | success=%d failed=%d",
                idx,
                len(normalized_codes),
                success,
                failed,
            )
        time.sleep(sleep_seconds)

    clear_candidate_score_caches()
    if success > 0:
        store.set_meta(meta_key, latest_date)
    summary = {
        "market": market,
        "scope": meta_scope,
        "days": days,
        "total": len(normalized_codes),
        "success": success,
        "failed": failed,
        "start_date": start_date,
        "end_date": end_date,
        "meta_key": meta_key,
    }
    log.info("[structure-bootstrap] Done %s", summary)
    return summary
