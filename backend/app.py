from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

log = logging.getLogger(__name__)

from backend.ai.report_generator import generate_report_payload
from backend.auth.user_store import (
    init_db, register_user, login_user, get_user_by_token,
    logout_token, get_favorites, add_favorite, remove_favorite
)
from backend.config import APP_DEBUG, APP_HOST, APP_PORT, DATA_DIR, DEFAULT_CORS_ORIGINS
from backend.data_access.company_repository import CompanyRepository
from backend.data_access.local_store import LocalDataStore
from backend.data_access.turnover_history_store import TurnoverHistoryStore
from backend.graph.neo4j_client import Neo4jClient
from backend.rules.engine import RuleEngine
from backend.screening.screening_service import apply_query_filters, get_candidates
from backend.screening.turnover_bootstrap import hydrate_single_code_turnover_history

_SIGNALS_DIR = DATA_DIR / "signals"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": DEFAULT_CORS_ORIGINS}})

init_db()


def _get_current_user():
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    return get_user_by_token(token) if token else None

store = LocalDataStore()
repository = CompanyRepository(local_store=store)
rule_engine = RuleEngine()
graph_client = Neo4jClient()
turnover_history_store = TurnoverHistoryStore()


def _load_signals_cache(market: str) -> dict[str, dict]:
    """Load pre-computed signals indexed by code. Returns empty dict if cache missing."""
    path = _SIGNALS_DIR / f"{market.lower()}_signals.json"
    if not path.exists():
        return {}
    results = json.loads(path.read_text(encoding="utf-8"))
    return {item["code"]: item for item in results}


def _extract_triggered_signal_ids(signal_result: dict | None) -> list[str]:
    if not signal_result:
        return []
    triggered: list[str] = []
    for sig in signal_result.get("financial_signals", []) + signal_result.get("governance_signals", []):
        if sig.get("triggered"):
            signal_id = sig.get("signal_id")
            if signal_id:
                triggered.append(str(signal_id))
    return triggered


def _build_financial_check(signal_result: dict | None) -> dict[str, object]:
    if not signal_result:
        return {
            "status": "no_data",
            "triggered_signals": [],
            "triggered_count": 0,
        }

    triggered_signals = _extract_triggered_signal_ids(signal_result)
    triggered_count = len(triggered_signals)

    if triggered_count >= 2:
        status = "high_risk"
    elif triggered_count == 1:
        status = "warning"
    else:
        status = "pass"

    return {
        "status": status,
        "triggered_signals": triggered_signals,
        "triggered_count": triggered_count,
    }


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


def _int_param(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    val = request.args.get(name)
    try:
        parsed = int(val) if val is not None else default
    except ValueError:
        parsed = default
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


@app.route("/api/candidates")
def api_get_candidates():
    """
    GET /api/candidates
    Realtime screening — fetches AKShare spot data, cached in memory 30 min.
    First request of the day takes ~30-60s; subsequent requests are instant.

    Query params (all optional — narrow the default thresholds):
        turnover_min  float  today's turnover > N%  (default 2)
        turnover_max  float  today's turnover <= N% (optional)
        price_max     float  price < N yuan          (default 20)
        circ_mv_max   float  流通市值 < N 亿         (default 80)
        pct_max       float  today gain < N%         (default 9)
        pct_min       float  today drop > N%         (default -9)
        exclude_st    0|1    exclude ST              (default 1)
        page         int     page number             (default 1)
        page_size    int     rows per page           (default 100)
        limit        int     legacy alias for page_size
        refresh       0|1    force cache refresh     (default 0)
    """
    exclude_st    = request.args.get("exclude_st", "1") not in ("0", "false")
    force_refresh = request.args.get("refresh", "0") in ("1", "true")

    try:
        data = get_candidates(
            turnover_min  = _float_param("turnover_min", 2.0),
            price_max     = _float_param("price_max",   20.0),
            circ_mv_max   = _float_param("circ_mv_max", 80.0),
            pct_max       = _float_param("pct_max",      9.0),
            pct_min       = _float_param("pct_min",     -9.0),
            exclude_st    = exclude_st,
            force_refresh = force_refresh,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503

    candidates = data.get("candidates", [])

    # Apply any tighter per-request filters
    candidates = apply_query_filters(
        candidates,
        turnover_min = _float_param("turnover_min"),
        turnover_max = _float_param("turnover_max"),
        price_max    = _float_param("price_max"),
        circ_mv_max  = _float_param("circ_mv_max"),
        pct_max      = _float_param("pct_max"),
        pct_min      = _float_param("pct_min"),
        exclude_st   = exclude_st,
    )

    page = _int_param("page", 1, minimum=1)
    page_size_default = _int_param("limit", 100, minimum=1, maximum=500)
    page_size = _int_param("page_size", page_size_default, minimum=1, maximum=500)
    signal_cache = _load_signals_cache("CN")

    candidates.sort(key=lambda c: (-(c.get("turnover") or 0), c.get("code") or ""))
    total = len(candidates)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    enriched = []
    for candidate in candidates[start_idx:end_idx]:
        signal_result = signal_cache.get(candidate["code"])
        enriched.append({
            **candidate,
            "financial_check": _build_financial_check(signal_result),
        })

    return jsonify({
        "generated_at": data.get("generated_at"),
        "trading_date": data.get("trading_date"),
        "source":       data.get("source", "realtime"),
        "thresholds":   data.get("thresholds", {}),
        "total":        total,
        "page":         page,
        "page_size":    page_size,
        "total_pages":  total_pages,
        "results":      enriched,
    }), 200


@app.route("/api/candidates/CN/<code>")
def get_candidate_detail(code: str):
    """
    GET /api/candidates/CN/<code>
    Returns the realtime candidate entry for one stock.
    """
    try:
        data = get_candidates()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503

    entry = next((c for c in data.get("candidates", []) if c["code"] == code), None)
    if entry is None:
        return jsonify({"error": f"{code} is not in the current candidates pool"}), 404

    # Attach brief signal summary if available (non-blocking)
    signal_cache = _load_signals_cache("CN")
    sig = signal_cache.get(code)
    entry = {
        **entry,
        "financial_check": _build_financial_check(sig),
    }
    if sig:
        entry["signal_summary"] = {
            "triggered_count": sig.get("summary", {}).get("triggered_count", 0),
            "total_rules":     sig.get("summary", {}).get("total_rules", 0),
        }

    return jsonify(entry), 200


@app.route("/api/turnover-history/<market>/<code>")
def get_turnover_history(market: str, code: str):
    market = market.upper()
    days = request.args.get("days")
    start_date = request.args.get("start")
    end_date = request.args.get("end")
    try:
        day_count = int(days) if days else None
    except ValueError:
        day_count = None

    rows = turnover_history_store.get_history(
        market,
        code,
        start_date=start_date,
        end_date=end_date,
        days=day_count,
    )
    if not rows and market == "CN":
        try:
            rows = hydrate_single_code_turnover_history(
                code,
                market=market,
                days=day_count or 10,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 503
    return jsonify({
        "market": market,
        "code": code,
        "start_date": start_date,
        "end_date": end_date,
        "days": day_count,
        "total": len(rows),
        "results": rows,
    }), 200


@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    try:
        user = register_user(email, password)
        token = login_user(email, password)
        return jsonify({"token": token, "user": {"email": user["email"]}}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 409


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    token = login_user(email, password)
    if not token:
        return jsonify({"error": "Invalid email or password"}), 401
    return jsonify({"token": token, "user": {"email": email}}), 200


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token:
        logout_token(token)
    return jsonify({"ok": True}), 200


@app.route("/api/me")
def me():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"email": user["email"]})


@app.route("/api/me/favorites")
def favorites_list():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"results": get_favorites(user["id"])})


@app.route("/api/me/favorites", methods=["POST"])
def favorites_add():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    market = body.get("market", "").upper()
    code = body.get("code", "")
    name = body.get("name", "")
    if not market or not code:
        return jsonify({"error": "market and code required"}), 400
    add_favorite(user["id"], market, code, name)
    return jsonify({"ok": True}), 201


@app.route("/api/me/favorites/<market>/<code>", methods=["DELETE"])
def favorites_remove(market, code):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    remove_favorite(user["id"], market, code)
    return jsonify({"ok": True}), 200


def _prewarm_candidates() -> None:
    """Background thread: warm the AKShare candidates cache at startup.
    This way the first user request returns from cache instead of waiting 60-150s."""
    try:
        log.info("[prewarm] Starting AKShare candidates pre-fetch …")
        get_candidates()
        log.info("[prewarm] Candidates cache ready.")
    except Exception as exc:
        log.warning("[prewarm] Pre-fetch failed (non-fatal): %s", exc)


# Pre-warm on startup — runs in background so gunicorn can accept requests immediately
threading.Thread(target=_prewarm_candidates, daemon=True, name="prewarm").start()


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)
