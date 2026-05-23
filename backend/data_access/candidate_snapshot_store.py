"""
candidate_snapshot_store.py
---------------------------
Persists daily scored candidate snapshots to the same SQLite DB as
turnover_history.  Each row captures the model's judgment (scores +
price data) at the time of generation so downstream backtests can
never accidentally use future data.

Table: candidate_snapshot
Primary key: (trade_date, code)
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import DATA_DIR

log = logging.getLogger(__name__)


class CandidateSnapshotStore:
    """SQLite-backed store for daily candidate pool snapshots."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (DATA_DIR / "turnover_history.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ── internals ─────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candidate_snapshot (
                    trade_date                TEXT NOT NULL,
                    code                      TEXT NOT NULL,
                    name                      TEXT,
                    industry                  TEXT,
                    score                     REAL,
                    activity_score            REAL,
                    price_structure_score     REAL,
                    volume_price_score        REAL,
                    sector_resonance_score    REAL,
                    washout_recovery_bonus    REAL,
                    early_setup_bonus         REAL,
                    turnover_noise_penalty    REAL,
                    distribution_risk_penalty REAL,
                    close                     REAL,
                    turnover                  REAL,
                    pct_chg                   REAL,
                    circ_mv                   REAL,
                    rank                      INTEGER,
                    source                    TEXT DEFAULT 'realtime',
                    created_at                TEXT,
                    PRIMARY KEY (trade_date, code)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_candidate_snapshot_date
                ON candidate_snapshot (trade_date)
            """)
            # Migrations: add columns that may not exist in older DB versions
            existing = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(candidate_snapshot)"
                ).fetchall()
            }
            migrations = [
                ("source",             "TEXT DEFAULT 'realtime'"),
                ("score_v3",           "REAL"),
                ("score_v4",           "REAL"),
                ("score_version",      "TEXT"),
                ("sector_hot_flag",    "INTEGER"),
                ("reversal_risk_flag", "INTEGER"),
                ("wyckoff_phase",      "TEXT"),
                ("wyckoff_tags",       "TEXT"),
                # structure_v5 fields (NEW)
                ("score_v5",           "REAL"),
                ("structure_v5_score", "REAL"),
                ("structure_v5_tier",  "TEXT"),
                ("structure_v5_tags",  "TEXT"),
                ("structure_v5_reason","TEXT"),
                ("market_regime",      "TEXT"),
                ("regime_status",      "TEXT"),
                ("regime_weight",      "REAL"),
            ]
            for col, col_def in migrations:
                if col not in existing:
                    conn.execute(
                        f"ALTER TABLE candidate_snapshot ADD COLUMN {col} {col_def}"
                    )

    # ── public API ────────────────────────────────────────────────────────────

    def save_snapshot(
        self,
        candidates: list[dict[str, Any]],
        trade_date: str,
        *,
        source: str = "realtime",
    ) -> int:
        """
        Persist a list of scored candidates as the snapshot for trade_date.

        `candidates` must already have been processed by attach_candidate_scores()
        so that score_breakdown is populated.  Missing fields are stored as NULL.

        Returns: number of rows written (0 on empty input or DB error).
        Never raises — failure is logged as a warning so the caller's API
        response is not affected.
        """
        if not candidates or not trade_date:
            return 0

        created_at = datetime.now(timezone.utc).isoformat()
        # Re-sort by score desc → assign rank 1 = best
        sorted_c = sorted(
            candidates,
            key=lambda c: (c.get("candidate_score") or 0),
            reverse=True,
        )

        payload: list[tuple] = []
        for rank, c in enumerate(sorted_c, start=1):
            bd = c.get("score_breakdown") or {}
            hm = c.get("history_metrics") or {}
            entry_close = c.get("current_price") or hm.get("latest_close")
            payload.append((
                trade_date,
                str(c.get("code") or "").strip(),
                c.get("name"),
                c.get("industry") or hm.get("industry"),
                c.get("candidate_score"),
                bd.get("activity_base"),
                bd.get("price_structure"),
                bd.get("volume_price"),
                bd.get("sector_resonance"),
                bd.get("washout_recovery_bonus"),
                bd.get("early_setup_bonus"),
                bd.get("turnover_noise_penalty"),
                bd.get("distribution_risk_penalty"),
                entry_close,
                c.get("turnover"),
                c.get("pct_change"),
                c.get("circ_mv"),
                rank,
                source,
                created_at,
                # v3/v4 fields
                c.get("score_v3"),
                c.get("score_v4"),
                c.get("score_version"),
                int(bool(c.get("sector_hot_flag"))) if c.get("sector_hot_flag") is not None else None,
                int(bool(c.get("reversal_risk_flag"))) if c.get("reversal_risk_flag") is not None else None,
                # Wyckoff structure
                c.get("wyckoff_phase"),
                c.get("wyckoff_tags"),
                # structure_v5 fields (NEW)
                c.get("score_v5"),
                c.get("structure_v5_score"),
                c.get("structure_v5_tier"),
                ",".join(c.get("structure_v5_tags", [])) if c.get("structure_v5_tags") else None,
                c.get("structure_v5_reason"),
                c.get("market_regime"),
                c.get("regime_status"),
                c.get("regime_weight"),
            ))

        if not payload:
            return 0

        try:
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO candidate_snapshot (
                        trade_date, code, name, industry,
                        score, activity_score, price_structure_score,
                        volume_price_score, sector_resonance_score,
                        washout_recovery_bonus, early_setup_bonus,
                        turnover_noise_penalty, distribution_risk_penalty,
                        close, turnover, pct_chg, circ_mv, rank, source, created_at,
                        score_v3, score_v4, score_version,
                        sector_hot_flag, reversal_risk_flag,
                        wyckoff_phase, wyckoff_tags,
                        score_v5, structure_v5_score, structure_v5_tier,
                        structure_v5_tags, structure_v5_reason,
                        market_regime, regime_status, regime_weight
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
            return len(payload)
        except Exception as exc:
            log.warning("candidate_snapshot save failed for %s: %s", trade_date, exc)
            return 0

    def load_snapshots(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load rows sorted by trade_date ASC, rank ASC."""
        conditions: list[str] = []
        params: list[Any] = []
        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    trade_date, code, name, industry,
                    score, activity_score, price_structure_score,
                    volume_price_score, sector_resonance_score,
                    washout_recovery_bonus, early_setup_bonus,
                    turnover_noise_penalty, distribution_risk_penalty,
                    close, turnover, pct_chg, circ_mv, rank, source,
                    score_v3, score_v4, score_version,
                    sector_hot_flag, reversal_risk_flag,
                    wyckoff_phase, wyckoff_tags
                FROM candidate_snapshot{where}
                ORDER BY trade_date ASC, rank ASC
                """,
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def list_snapshot_dates(self) -> list[tuple[str, int]]:
        """Return [(trade_date, candidate_count)] for all saved dates."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trade_date, COUNT(*) n
                FROM candidate_snapshot
                GROUP BY trade_date
                ORDER BY trade_date ASC
                """
            ).fetchall()
        return [(r["trade_date"], r["n"]) for r in rows]

    def snapshot_exists(self, trade_date: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM candidate_snapshot WHERE trade_date = ? LIMIT 1",
                (trade_date,),
            ).fetchone()
        return row is not None
