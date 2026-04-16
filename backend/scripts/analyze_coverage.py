from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from backend.config import DATA_DIR
from backend.data_access.coverage import CORE_FINANCIAL_FIELDS, annual_records, snapshot_tier


def analyze_market(market: str) -> dict:
    market_dir = DATA_DIR / market.lower()
    counts = Counter()
    field_counts = Counter()
    annual_nonempty = 0

    for path in market_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        tier = snapshot_tier(payload)
        counts[tier] += 1

        annual = annual_records(payload)
        if annual:
            annual_nonempty += 1
            latest = annual[0]
            for field in CORE_FINANCIAL_FIELDS:
                if latest.get(field) is not None:
                    field_counts[field] += 1

    total = sum(counts.values())
    return {
        "market": market.upper(),
        "total": total,
        "tiers": dict(counts),
        "annual_nonempty": annual_nonempty,
        "field_coverage": {
            field: {
                "count": field_counts[field],
                "ratio": round(field_counts[field] / total, 4) if total else 0,
            }
            for field in CORE_FINANCIAL_FIELDS
        },
    }


def main() -> None:
    result = {
        "CN": analyze_market("cn"),
        "TW": analyze_market("tw"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
