"""
run_candidates.py
-----------------
Batch script: build the A-share candidates pool and write cache to
data/screening/candidates_cn.json.

Requires AKShare to be installed and network access to CN market data.

Usage:
    python -m backend.scripts.run_candidates
    python -m backend.scripts.run_candidates --price-max 8 --share-max 50
    python -m backend.scripts.run_candidates --no-exclude-st

Typical runtime: 3–8 minutes (depends on pre-filtered count and network).
Run once daily, e.g. after market close (~15:30 CST).
"""
from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build A-share candidates pool cache")
    parser.add_argument("--turnover-min",  type=float, default=1.0,  help="Min avg 10d turnover %% (default 1)")
    parser.add_argument("--turnover-max",  type=float, default=10.0, help="Max single-day turnover %% (default 10)")
    parser.add_argument("--price-max",     type=float, default=5.0,  help="Max price in yuan (default 5)")
    parser.add_argument("--share-max",     type=float, default=30.0, help="Max total shares in 亿 (default 30)")
    parser.add_argument("--pct-max",       type=float, default=15.0, help="Max 10d pct change %% (default 15)")
    parser.add_argument("--no-exclude-st", action="store_true",      help="Include ST stocks")
    parser.add_argument("--hist-delay",    type=float, default=0.25, help="Seconds between history API calls (default 0.25)")
    args = parser.parse_args()

    # Import here (not at module level) to keep startup fast
    from backend.screening.screening_service import build_candidates

    log.info("Starting candidates build …")
    log.info(
        "Thresholds: turnover %.1f%%–%.1f%% | price <%.1f | shares <%.1f亿 | 10d gain <%.1f%% | exclude_st=%s",
        args.turnover_min, args.turnover_max,
        args.price_max, args.share_max, args.pct_max,
        not args.no_exclude_st,
    )

    try:
        result = build_candidates(
            turnover_min = args.turnover_min,
            turnover_max = args.turnover_max,
            price_max    = args.price_max,
            share_max    = args.share_max,
            pct_max      = args.pct_max,
            exclude_st   = not args.no_exclude_st,
            hist_delay   = args.hist_delay,
        )
        log.info("Done. %d candidates saved. Generated at: %s", result["total"], result["generated_at"])
    except Exception as exc:
        log.error("Build failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
