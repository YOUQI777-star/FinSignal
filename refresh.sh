#!/usr/bin/env bash
# ============================================================
# Daily refresh: TW OCF enrichment → re-run signals cache
# Usage: ./refresh.sh
# Run once per day; FinMind free tier allows ~100 requests/day.
# ============================================================
set -e
cd "$(dirname "$0")"

echo "=== [1/3] Capturing today's CN turnover snapshot ==="
.venv/bin/python -m backend.scripts.capture_turnover_snapshot --force-refresh

echo ""
echo "=== [2/3] Enriching TW OCF (FinMind, up to 100 companies) ==="
.venv/bin/python -m backend.scripts.enrich_tw_ocf --limit 100 --delay 1.5

echo ""
echo "=== [3/3] Regenerating signals cache ==="
.venv/bin/python -m backend.scripts.run_signals --market TW
.venv/bin/python -m backend.scripts.run_signals --market CN

echo ""
echo "=== Done ==="
.venv/bin/python -c "
import json, pathlib
tw_dir = pathlib.Path('data/tw')
missing = sum(1 for p in tw_dir.glob('*.json')
    if not any(a.get('operating_cash_flow') is not None
               for a in json.loads(p.read_text()).get('financials',{}).get('annual',[])))
print(f'TW OCF remaining: {missing} / 1081')
with open('data/signals/summary.json') as f:
    s = json.load(f)
print('Signal summary:', json.dumps(s, ensure_ascii=False))
"
