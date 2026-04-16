from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from backend.ai.report_generator import generate_report_payload
from backend.config import APP_DEBUG, APP_HOST, APP_PORT, DATA_DIR, DEFAULT_CORS_ORIGINS
from backend.data_access.company_repository import CompanyRepository
from backend.data_access.local_store import LocalDataStore
from backend.graph.neo4j_client import Neo4jClient
from backend.rules.engine import RuleEngine
from backend.screening.screening_service import apply_query_filters, load_from_cache

_SIGNALS_DIR = DATA_DIR / "signals"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": DEFAULT_CORS_ORIGINS}})

store = LocalDataStore()
repository = CompanyRepository(local_store=store)
rule_engine = RuleEngine()
graph_client = Neo4jClient()


def _load_signals_cache(market: str) -> dict[str, dict]:
    """Load pre-computed signals indexed by code. Returns empty dict if cache missing."""
    path = _SIGNALS_DIR / f"{market.lower()}_signals.json"
    if not path.exists():
        return {}
    results = json.loads(path.read_text(encoding="utf-8"))
    return {item["code"]: item for item in results}


@app.route("/api/health")
def health() -> tuple[dict, int]:
    return jsonify({"status": "ok"}), 200


@app.route("/api/company/<market>/<code>")
def get_company(market: str, code: str):
    company = repository.get_company_profile(market, code)
    if not company:
        return jsonify({"error": "Company profile not found"}), 404
    return jsonify(company), 200


@app.route("/api/signals/<market>/<code>")
def get_signals(market: str, code: str):
    fresh = request.args.get("fresh", "").lower() in ("1", "true")
    if not fresh:
        cache = _load_signals_cache(market)
        if code in cache:
            return jsonify(cache[code]), 200
    snapshot = store.get_company_snapshot(market, code)
    if not snapshot:
        return jsonify({"error": "Company snapshot not found"}), 404
    return jsonify(rule_engine.evaluate(snapshot)), 200


@app.route("/api/signals/top")
def get_top_signals():
    market = request.args.get("market", "").upper() or None
    limit = min(int(request.args.get("limit", 50)), 200)
    signal_id = request.args.get("signal_id", "").upper() or None

    markets = [market] if market else ["CN", "TW"]
    all_results = []
    for m in markets:
        cache = _load_signals_cache(m)
        all_results.extend(cache.values())

    if signal_id:
        def _has_signal(r: dict) -> bool:
            for sig in r.get("financial_signals", []) + r.get("governance_signals", []):
                if sig.get("signal_id") == signal_id and sig.get("triggered"):
                    return True
            return False
        all_results = [r for r in all_results if _has_signal(r)]
    else:
        all_results = [r for r in all_results if r.get("summary", {}).get("triggered_count", 0) > 0]

    all_results.sort(key=lambda r: r.get("summary", {}).get("triggered_count", 0), reverse=True)
    return jsonify({"total": len(all_results), "results": all_results[:limit]}), 200


@app.route("/api/graph/<market>/<code>")
def get_graph(market: str, code: str):
    return jsonify(graph_client.get_company_graph(market, code)), 200


@app.route("/api/compare")
def compare_companies():
    codes = request.args.get("codes", "")
    company_ids = [item.strip() for item in codes.split(",") if item.strip()]
    results = []
    for company_id in company_ids:
        try:
            market, code = company_id.split(":", 1)
        except ValueError:
            continue
        snapshot = store.get_company_snapshot(market, code)
        if not snapshot:
            continue
        results.append(rule_engine.evaluate(snapshot))
    return jsonify({"results": results}), 200


@app.route("/api/report/<market>/<code>", methods=["POST"])
def generate_report(market: str, code: str):
    snapshot = store.get_company_snapshot(market, code)
    if not snapshot:
        return jsonify({"error": "Company snapshot not found"}), 404
    signals = rule_engine.evaluate(snapshot)
    return jsonify(generate_report_payload(snapshot, signals)), 200


@app.route("/api/search")
def search_company():
    query = request.args.get("q", "")
    return jsonify({"results": repository.search_companies(query)}), 200


# ── Candidates ────────────────────────────────────────────────────────────────

def _float_param(name: str, default: float | None = None) -> float | None:
    val = request.args.get(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


@app.route("/api/candidates")
def get_candidates():
    """
    GET /api/candidates
    Returns cached candidate pool.  Query params allow narrowing the results:
        turnover_min  float   min avg 10d turnover % (default: cache threshold)
        turnover_max  float   max single-day turnover %
        price_max     float   max current price (yuan)
        share_max     float   max total shares (亿)
        pct_max       float   max 10d price change %
        exclude_st    0|1     exclude ST stocks (default 1)
        limit         int     max rows to return (default 200)
    """
    cache = load_from_cache()
    if cache is None:
        return jsonify({
            "error": "Candidates cache not found. Run: python -m backend.scripts.run_candidates",
            "hint":  "Cache is built by a batch script, not at request time.",
        }), 404

    candidates = cache.get("candidates", [])

    # Apply optional extra filters from query params
    exclude_st = request.args.get("exclude_st", "1") not in ("0", "false")
    candidates = apply_query_filters(
        candidates,
        turnover_min = _float_param("turnover_min"),
        turnover_max = _float_param("turnover_max"),
        price_max    = _float_param("price_max"),
        share_max    = _float_param("share_max"),
        pct_max      = _float_param("pct_max"),
        exclude_st   = exclude_st,
    )

    limit = min(int(request.args.get("limit", 200)), 500)

    return jsonify({
        "generated_at": cache.get("generated_at"),
        "thresholds":   cache.get("thresholds", {}),
        "total":        len(candidates),
        "results":      candidates[:limit],
    }), 200


@app.route("/api/candidates/CN/<code>")
def get_candidate_detail(code: str):
    """
    GET /api/candidates/CN/<code>
    Returns the cached candidate entry for one stock, plus a lightweight
    signal summary if signals cache is available.
    """
    cache = load_from_cache()
    if cache is None:
        return jsonify({"error": "Candidates cache not found"}), 404

    entry = next((c for c in cache.get("candidates", []) if c["code"] == code), None)
    if entry is None:
        return jsonify({"error": f"{code} is not in the current candidates pool"}), 404

    # Attach brief signal summary if available (non-blocking)
    signal_cache = _load_signals_cache("CN")
    if code in signal_cache:
        sig = signal_cache[code]
        entry = {
            **entry,
            "signal_summary": {
                "triggered_count": sig.get("summary", {}).get("triggered_count", 0),
                "total_rules":     sig.get("summary", {}).get("total_rules", 0),
            },
        }

    return jsonify(entry), 200


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)
