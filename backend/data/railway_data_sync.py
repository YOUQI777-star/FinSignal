"""
railway_data_sync.py
--------------------
Railway 部署专用：
  1. 启动时把 bootstrap_turnover_history.db (90 天种子数据) 复制到 Volume
  2. 提供 sync_today() 函数从 Tushare 拉当日数据写入 Volume DB
  3. 提供 purge_old_data() 控制 Volume 体积（默认保留 120 天）

设计原则：
  - 幂等：bootstrap 只在 Volume DB 不存在时执行
  - 容错：Tushare 拉取失败不影响 web 服务
  - 容量管控：每次同步后调用 purge，确保 Volume < 500MB
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

# Bootstrap file 跟着代码部署（在 /app/data/）
# Volume DB 在 /app/userdata/turnover_history.db (DATA_DIR 通过 APP_DATA_DIR 指向)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BOOTSTRAP_DB_PATH = PROJECT_ROOT / "data" / "bootstrap_turnover_history.db"

# 数据保留天数（默认 120 天，Volume 占用约 90MB）
DEFAULT_RETENTION_DAYS = 120


def seed_volume_from_bootstrap(volume_db_path: Path) -> dict:
    """
    启动时调用：如果 Volume DB 不存在或为空，从 bootstrap 文件初始化。

    Returns: dict with status info
    """
    if not BOOTSTRAP_DB_PATH.exists():
        log.info("No bootstrap file at %s, skipping seed", BOOTSTRAP_DB_PATH)
        return {"seeded": False, "reason": "bootstrap_not_found"}

    volume_db_path.parent.mkdir(parents=True, exist_ok=True)

    # 检查 Volume DB 是否已有数据
    if volume_db_path.exists():
        try:
            conn = sqlite3.connect(volume_db_path)
            row = conn.execute(
                "SELECT COUNT(*) FROM turnover_history WHERE pe IS NOT NULL"
            ).fetchone()
            conn.close()
            existing_pe_rows = row[0] if row else 0
        except sqlite3.OperationalError:
            existing_pe_rows = 0  # schema 不存在，需要重新 seed

        if existing_pe_rows > 1000:
            log.info(
                "Volume DB already has %d PE rows, skipping bootstrap",
                existing_pe_rows,
            )
            return {"seeded": False, "reason": "already_populated", "existing_pe_rows": existing_pe_rows}

    bootstrap_size_mb = BOOTSTRAP_DB_PATH.stat().st_size / 1024 / 1024
    log.info(
        "Seeding Volume DB from bootstrap (%.1f MB) → %s",
        bootstrap_size_mb, volume_db_path,
    )
    shutil.copy2(BOOTSTRAP_DB_PATH, volume_db_path)
    log.info("Bootstrap copy complete")

    # 校验
    conn = sqlite3.connect(volume_db_path)
    row = conn.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM turnover_history").fetchone()
    conn.close()
    return {
        "seeded": True,
        "rows": row[0],
        "earliest": row[1],
        "latest": row[2],
        "bootstrap_size_mb": round(bootstrap_size_mb, 2),
    }


def purge_old_data(volume_db_path: Path, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """
    删除 retention_days 之前的历史数据，控制 Volume 体积。

    Returns: 删除的行数
    """
    if not volume_db_path.exists():
        return 0

    cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(volume_db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM turnover_history WHERE date < ?", (cutoff_date,))
        deleted = cur.rowcount
        conn.commit()
        if deleted > 0:
            log.info("Purged %d rows older than %s", deleted, cutoff_date)
            # SQLite 不自动回收空间，需 VACUUM
            try:
                conn.execute("VACUUM")
                log.info("VACUUM complete")
            except Exception as e:
                log.warning("VACUUM failed: %s", e)
        return deleted
    finally:
        conn.close()


def sync_today_from_tushare(volume_db_path: Path) -> dict:
    """
    从 Tushare 拉取最新交易日的 daily + daily_basic 数据，写入 Volume DB。

    流程:
      1. 拉今日 Tushare 数据 (5500 stocks × 1 day, ~30s)
      2. INSERT OR REPLACE 到 turnover_history (带 PE/PB)

    Returns: dict with sync stats
    """
    # 导入 Tushare 客户端（如果未配置 token 会抛 RuntimeError）
    try:
        from backend.tushare_client import get_pro
        from backend.data.tushare_history_loader import _fetch_daily_for_date
    except Exception as e:
        return {"ok": False, "error": f"tushare import failed: {e}"}

    today = datetime.now().strftime("%Y%m%d")
    try:
        pro = get_pro()
    except Exception as e:
        return {"ok": False, "error": f"tushare token error: {e}"}

    log.info("Fetching %s from Tushare...", today)
    try:
        rows = _fetch_daily_for_date(pro, today)
    except Exception as e:
        return {"ok": False, "error": f"tushare fetch failed: {e}", "date": today}

    if not rows:
        # 可能今天不是交易日，或盘后数据还没出
        log.warning("No data returned for %s", today)
        return {"ok": True, "date": today, "rows_fetched": 0, "note": "market closed or data not yet published"}

    th_date = f"{today[:4]}-{today[4:6]}-{today[6:8]}"
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(volume_db_path)
    try:
        # 确保 schema 完整
        _ensure_th_schema(conn)

        # rows 是 sdt 格式的 tuple，要转换成 th 格式插入
        # sdt tuple 字段顺序 (见 tushare_history_loader._fetch_daily_for_date):
        # (trade_date, ts_code, code, open, high, low, close, pre_close,
        #  pct_chg, vol, amount, turnover_rate, turnover_rate_f, volume_ratio,
        #  pe, pb, total_mv, circ_mv, circ_mv_yi, created_at)
        payload = []
        for r in rows:
            (sdt_date, ts_code, code, open_, high, low, close, pre_close,
             pct_chg, vol, amount, turnover_rate, turnover_rate_f, volume_ratio,
             pe, pb, total_mv, circ_mv, circ_mv_yi, _) = r
            payload.append((
                "CN", code, th_date,
                turnover_rate, created_at,
                open_, high, low, close, pct_chg, vol, amount, circ_mv,
                pe, pb, total_mv, pre_close, turnover_rate_f, volume_ratio,
            ))

        conn.executemany("""
            INSERT INTO turnover_history (
                market, code, date, turnover_rate, updated_at,
                open, high, low, close, pct_change, volume, amount, circ_mv,
                pe, pb, total_mv, pre_close, turnover_rate_f, volume_ratio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(market, code, date) DO UPDATE SET
                turnover_rate = excluded.turnover_rate,
                updated_at = excluded.updated_at,
                open = excluded.open, high = excluded.high,
                low = excluded.low, close = excluded.close,
                pct_change = excluded.pct_change, volume = excluded.volume,
                amount = excluded.amount, circ_mv = excluded.circ_mv,
                pe = excluded.pe, pb = excluded.pb, total_mv = excluded.total_mv,
                pre_close = excluded.pre_close,
                turnover_rate_f = excluded.turnover_rate_f,
                volume_ratio = excluded.volume_ratio
        """, payload)
        conn.commit()
        rows_written = len(payload)
        log.info("Wrote %d rows for %s to Volume DB", rows_written, th_date)
    finally:
        conn.close()

    # 顺手清老数据
    purged = purge_old_data(volume_db_path)

    return {
        "ok": True,
        "date": th_date,
        "rows_fetched": rows_written,
        "rows_purged": purged,
    }


def _ensure_th_schema(conn: sqlite3.Connection) -> None:
    """确保 turnover_history 表 + 必要列存在（幂等）。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS turnover_history (
            market TEXT NOT NULL,
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            turnover_rate REAL,
            updated_at TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            pct_change REAL, volume REAL, amount REAL, circ_mv REAL,
            pe REAL, pb REAL, total_mv REAL, pre_close REAL,
            turnover_rate_f REAL, volume_ratio REAL,
            PRIMARY KEY (market, code, date)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_turnover_history_lookup ON turnover_history(market, code, date)"
    )
    # 老 DB 可能缺这些列（来自合并前的 schema）
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(turnover_history)")}
    for col, ctype in [
        ("pe", "REAL"), ("pb", "REAL"), ("total_mv", "REAL"),
        ("pre_close", "REAL"), ("turnover_rate_f", "REAL"), ("volume_ratio", "REAL"),
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE turnover_history ADD COLUMN {col} {ctype}")
            log.info("ALTER: added column %s", col)
