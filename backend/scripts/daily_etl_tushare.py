"""
daily_etl_tushare.py
--------------------
每日 ETL：从 Tushare 拉取最近 N 个交易日的 daily + daily_basic 数据，
同时写入 stock_daily_tushare 和 turnover_history（带 PE/PB）。

用法:
    # 拉今天数据（最常用，每个交易日盘后跑一次）
    python -m backend.scripts.daily_etl_tushare

    # 拉最近 7 天（补缺）
    python -m backend.scripts.daily_etl_tushare --days 7

    # 拉指定日期
    python -m backend.scripts.daily_etl_tushare --date 20260522
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from backend.config import DATA_DIR
from backend.data.tushare_history_loader import (
    _ensure_schema,
    _fetch_daily_for_date,
    _save_daily_rows,
    fetch_trade_calendar,
)
from backend.tushare_client import get_pro

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "turnover_history.db"


def _date_to_th_format(yyyymmdd: str) -> str:
    """20260522 -> 2026-05-22"""
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def backfill_turnover_history_from_sdt(date_yyyymmdd: str, db_path: Path = DB_PATH) -> tuple[int, int]:
    """
    对单个交易日：把 stock_daily_tushare 的 pe/pb/total_mv/pre_close/turnover_rate_f/volume_ratio
    同步到 turnover_history（如果该行已存在则 UPDATE，不存在则 INSERT）。

    Returns: (updated_count, inserted_count)
    """
    th_date = _date_to_th_format(date_yyyymmdd)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # UPDATE existing rows
        cursor.execute("""
            UPDATE turnover_history AS th
            SET pe = sdt.pe,
                pb = sdt.pb,
                total_mv = sdt.total_mv,
                pre_close = sdt.pre_close,
                turnover_rate_f = sdt.turnover_rate_f,
                volume_ratio = sdt.volume_ratio
            FROM stock_daily_tushare AS sdt
            WHERE th.code = sdt.code
              AND th.date = ?
              AND sdt.trade_date = ?
        """, (th_date, date_yyyymmdd))
        updated = cursor.rowcount

        # INSERT rows that exist in sdt but not in th
        cursor.execute("""
            INSERT INTO turnover_history (
                market, code, date, turnover_rate, updated_at,
                open, high, low, close, pct_change, volume, amount, circ_mv,
                pe, pb, total_mv, pre_close, turnover_rate_f, volume_ratio
            )
            SELECT 'CN', sdt.code, ?, sdt.turnover_rate,
                   datetime('now'),
                   sdt.open, sdt.high, sdt.low, sdt.close, sdt.pct_chg,
                   sdt.vol, sdt.amount, sdt.circ_mv,
                   sdt.pe, sdt.pb, sdt.total_mv, sdt.pre_close,
                   sdt.turnover_rate_f, sdt.volume_ratio
            FROM stock_daily_tushare sdt
            WHERE sdt.trade_date = ?
              AND NOT EXISTS (
                  SELECT 1 FROM turnover_history th2
                  WHERE th2.market = 'CN'
                    AND th2.code = sdt.code
                    AND th2.date = ?
              )
        """, (th_date, date_yyyymmdd, th_date))
        inserted = cursor.rowcount

        conn.commit()
        return updated, inserted
    finally:
        conn.close()


def sync_one_date(pro, date_yyyymmdd: str) -> dict:
    """拉一天的 Tushare 数据，写 sdt，再回填到 th。返回统计信息。"""
    log.info("Fetching %s from Tushare...", date_yyyymmdd)
    rows = _fetch_daily_for_date(pro, date_yyyymmdd)
    if not rows:
        log.warning("No data for %s (market closed or not yet published)", date_yyyymmdd)
        return {"date": date_yyyymmdd, "sdt_saved": 0, "th_updated": 0, "th_inserted": 0}

    sdt_saved = _save_daily_rows(rows)
    log.info("  → stock_daily_tushare: %d rows saved", sdt_saved)

    updated, inserted = backfill_turnover_history_from_sdt(date_yyyymmdd)
    log.info("  → turnover_history: %d updated, %d inserted", updated, inserted)

    return {
        "date": date_yyyymmdd,
        "sdt_saved": sdt_saved,
        "th_updated": updated,
        "th_inserted": inserted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily ETL: fetch Tushare data and sync to turnover_history.")
    parser.add_argument("--days", type=int, default=1,
                        help="Days back to sync (default 1 = just today). e.g. --days 7 fills last week.")
    parser.add_argument("--date", default=None,
                        help="Specific trading date YYYYMMDD (overrides --days).")
    parser.add_argument("--start-date", default=None,
                        help="Range start YYYYMMDD (used with --end-date).")
    parser.add_argument("--end-date", default=None,
                        help="Range end YYYYMMDD (used with --start-date).")
    args = parser.parse_args()

    _ensure_schema()
    pro = get_pro()

    if args.date:
        target_dates = [args.date]
    elif args.start_date and args.end_date:
        target_dates = fetch_trade_calendar(pro, args.start_date, args.end_date)
        log.info("Range covers %d trading days", len(target_dates))
    else:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=args.days * 2)).strftime("%Y%m%d")
        # use calendar to get only trading days
        all_dates = fetch_trade_calendar(pro, start, today)
        target_dates = all_dates[-args.days:] if all_dates else []

    if not target_dates:
        log.warning("No trading dates to sync")
        return

    log.info("Will sync %d date(s): %s", len(target_dates), ", ".join(target_dates))
    total = {"sdt_saved": 0, "th_updated": 0, "th_inserted": 0}
    for d in target_dates:
        stats = sync_one_date(pro, d)
        total["sdt_saved"] += stats["sdt_saved"]
        total["th_updated"] += stats["th_updated"]
        total["th_inserted"] += stats["th_inserted"]

    log.info("=" * 60)
    log.info("ETL DONE — total:")
    log.info("  stock_daily_tushare saved:    %d", total["sdt_saved"])
    log.info("  turnover_history updated:     %d", total["th_updated"])
    log.info("  turnover_history inserted:    %d", total["th_inserted"])


if __name__ == "__main__":
    main()
