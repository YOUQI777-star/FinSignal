from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.config import SNAPSHOT_DATA_DIR


class LocalDataStore:
    """Simple filesystem-backed store for company and signal snapshots."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or SNAPSHOT_DATA_DIR

    def get_company_snapshot(self, market: str, code: str) -> dict[str, Any] | None:
        path = self.data_dir / market.lower() / f"{code}.json"
        return self._load_json(path)

    def get_signal_snapshot(self, market: str, code: str) -> dict[str, Any] | None:
        path = self.data_dir / "signals" / market.lower() / f"{code}.json"
        return self._load_json(path)

    def search_companies(self, query: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        normalized_query = query.strip().lower()
        if not normalized_query:
            return results

        for market in ("cn", "tw"):
            market_dir = self.data_dir / market
            if not market_dir.exists():
                continue
            for path in market_dir.glob("*.json"):
                payload = self._load_json(path)
                if not payload:
                    continue
                haystacks = [
                    str(payload.get("code", "")).lower(),
                    str(payload.get("name", "")).lower(),
                    str(payload.get("name_en", "")).lower(),
                    str(payload.get("company_id", "")).lower(),
                ]
                if any(normalized_query in value for value in haystacks):
                    results.append(
                        {
                            "company_id": payload.get("company_id"),
                            "market": payload.get("market"),
                            "code": payload.get("code"),
                            "name": payload.get("name"),
                            "industry": payload.get("industry"),
                        }
                    )
        return sorted(results, key=lambda item: (item["market"], item["code"]))

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
