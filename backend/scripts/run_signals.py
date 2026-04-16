"""Batch-evaluate signals for all real_financial_available companies.

Reads every snapshot in data/cn/ and data/tw/, filters for real_financial_available
tier, runs the RuleEngine, and writes results to data/signals/.

Output files:
    data/signals/cn_signals.json  — list of signal results for each CN company
    data/signals/tw_signals.json  — list of signal results for each TW company
    data/signals/summary.json     — aggregated counts across both markets

Usage:
    .venv/bin/python -m backend.scripts.run_signals
    .venv/bin/python -m backend.scripts.run_signals --market CN
    .venv/bin/python -m backend.scripts.run_signals --market TW --triggered-only
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from backend.config import DATA_DIR
from backend.data_access.coverage import snapshot_tier
from backend.rules.engine import RuleEngine


def evaluate_market(
    market: str,
    engine: RuleEngine,
    data_dir: Path,
    triggered_only: bool = False,
) -> list[dict]:
    market_dir = data_dir / market.lower()
    results = []
    for path in sorted(market_dir.glob("*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if snapshot_tier(snapshot) != "real_financial_available":
            continue
        result = engine.evaluate(snapshot)
        if triggered_only and result["summary"]["triggered_count"] == 0:
            continue
        results.append(result)
    return results


def build_summary(market_results: dict[str, list[dict]]) -> dict:
    summary: dict = {"markets": {}}
    total_companies = total_triggered = 0
    signal_trigger_counts: Counter = Counter()

    for market, results in market_results.items():
        triggered_companies = sum(1 for r in results if r["summary"]["triggered_count"] > 0)
        total_companies += len(results)
        total_triggered += triggered_companies

        for result in results:
            for signal in result["financial_signals"] + result["governance_signals"]:
                if signal.get("triggered"):
                    signal_trigger_counts[signal["signal_id"]] += 1

        summary["markets"][market] = {
            "evaluated": len(results),
            "with_triggered_signals": triggered_companies,
        }

    summary["total_evaluated"] = total_companies
    summary["total_with_triggered"] = total_triggered
    summary["signal_trigger_counts"] = dict(signal_trigger_counts.most_common())
    return summary


def run(
    markets: list[str] | None = None,
    triggered_only: bool = False,
    data_dir: Path = DATA_DIR,
) -> dict:
    engine = RuleEngine()
    target_markets = markets or ["CN", "TW"]
    market_results: dict[str, list[dict]] = {}

    for market in target_markets:
        results = evaluate_market(market, engine, data_dir, triggered_only=triggered_only)
        market_results[market] = results
        triggered = sum(1 for r in results if r["summary"]["triggered_count"] > 0)
        print(f"{market}: {len(results)} evaluated, {triggered} with triggered signals")

    signals_dir = data_dir / "signals"
    signals_dir.mkdir(exist_ok=True)

    for market, results in market_results.items():
        out_path = signals_dir / f"{market.lower()}_signals.json"
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Saved {market} -> {out_path}")

    summary = build_summary(market_results)
    summary_path = signals_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Saved summary -> {summary_path}")

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-evaluate signals for all real_financial_available companies.")
    parser.add_argument(
        "--market",
        choices=["CN", "TW"],
        help="Evaluate a single market only (default: both)",
    )
    parser.add_argument(
        "--triggered-only",
        action="store_true",
        help="Only include companies with at least one triggered signal in output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    markets = [args.market] if args.market else None
    run(markets=markets, triggered_only=args.triggered_only)


if __name__ == "__main__":
    main()
