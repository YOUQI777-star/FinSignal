from __future__ import annotations

import json
import logging
import threading
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

log = logging.getLogger(__name__)

from backend.ai.report_generator import generate_report_payload
from backend.auth.user_store import (
    init_db, register_user, login_user, get_user_by_token,
    logout_token, get_favorites, add_favorite, remove_favorite, update_favorite_name
)
from backend.config import APP_DEBUG, APP_HOST, APP_PORT, DATA_DIR, DEFAULT_CORS_ORIGINS
from backend.data_access.company_repository import CompanyRepository
from backend.data_access.local_store import LocalDataStore
from backend.data_access.turnover_history_store import TurnoverHistoryStore
from backend.graph.neo4j_client import Neo4jClient
from backend.rules.engine import RuleEngine
from backend.screening.screening_service import apply_query_filters, get_candidates
from backend.screening.candidate_scoring import attach_candidate_scores
from backend.screening.turnover_bootstrap import hydrate_single_code_turnover_history
from backend.screening.market_loader import get_recent_trading_dates
from backend.scrapers.cn_tushare import TushareCNClient, tushare_available

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


def _attach_candidate_score_payload(payload: dict, *, code: str) -> dict:
    score_seed = {
        "code": str(code).strip(),
        "name": payload.get("name"),
        "turnover": payload.get("turnover"),
        "pct_change": payload.get("pct_change"),
        "circ_mv": payload.get("circ_mv"),
        "current_price": payload.get("current_price") or payload.get("close"),
    }
    scored = attach_candidate_scores([score_seed])[0]
    return {
        **payload,
        "candidate_score": scored.get("candidate_score"),
        "score_formula": scored.get("score_formula"),
        "score_breakdown": scored.get("score_breakdown"),
        "history_metrics": scored.get("history_metrics"),
    }


def _favorite_name_needs_repair(item: dict) -> bool:
    saved_name = str(item.get("name") or "").strip()
    saved_code = str(item.get("code") or "").strip()
    return (not saved_name) or saved_name == saved_code


def _expected_turnover_dates(
    market: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
) -> list[str]:
    market = market.upper()
    if market != "CN":
        return []

    if days and not start_date and not end_date:
        return get_recent_trading_dates(days)

    if not start_date and not end_date:
        return []

    end = end_date or date.today().isoformat()
    start = start_date or (date.fromisoformat(end) - timedelta(days=30)).isoformat()

    if tushare_available():
        try:
            dates = TushareCNClient().get_trade_dates(start_date=start, end_date=end)
            return [d for d in dates if d >= start and d <= end]
        except Exception as exc:
            log.warning("Trade dates fallback to weekdays for %s→%s: %s", start, end, exc)

    expected: list[str] = []
    current = date.fromisoformat(start)
    last = date.fromisoformat(end)
    while current <= last:
        if current.weekday() < 5:
            expected.append(current.isoformat())
        current += timedelta(days=1)
    return expected


def _merge_turnover_rows_with_expected_dates(rows: list[dict], expected_dates: list[str], *, market: str, code: str) -> list[dict]:
    rows_by_date = {
        str(row.get("date")): dict(row)
        for row in rows
        if row.get("date")
    }
    merged: list[dict] = []
    for trading_date in expected_dates:
        row = rows_by_date.get(trading_date)
        if row:
            merged.append({
                **row,
                "date": trading_date,
                "has_data": row.get("turnover_rate") is not None,
                "data_status": "available" if row.get("turnover_rate") is not None else "missing",
            })
        else:
            merged.append({
                "market": market,
                "code": code,
                "date": trading_date,
                "turnover_rate": None,
                "open": None,
                "high": None,
                "low": None,
                "close": None,
                "pct_change": None,
                "volume": None,
                "amount": None,
                "circ_mv": None,
                "updated_at": None,
                "has_data": False,
                "data_status": "missing",
            })
    return merged


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
            payload = cache[code]
            if market.upper() == "CN":
                payload = _attach_candidate_score_payload(payload, code=code)
            return jsonify(payload), 200
    snapshot = store.get_company_snapshot(market, code)
    if not snapshot:
        return jsonify({"error": "Company snapshot not found"}), 404
    payload = rule_engine.evaluate(snapshot)
    if market.upper() == "CN":
        payload = _attach_candidate_score_payload(payload, code=code)
    return jsonify(payload), 200


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

    enriched_results = []
    for result in all_results:
        if result.get("market") == "CN":
            entry = attach_candidate_scores([result])[0]
            result = {
                **result,
                "candidate_score": entry.get("candidate_score"),
                "score_formula": entry.get("score_formula"),
                "score_breakdown": entry.get("score_breakdown"),
                "history_metrics": entry.get("history_metrics"),
            }
        enriched_results.append(result)

    enriched_results.sort(
        key=lambda r: (
            -(r.get("summary", {}).get("triggered_count", 0)),
            -(r.get("candidate_score") or 0),
            r.get("market") or "",
            r.get("code") or "",
        )
    )
    return jsonify({"total": len(enriched_results), "results": enriched_results[:limit]}), 200


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


def _build_turnover_context(market: str, code: str) -> dict:
    """
    Pull last 10 days of turnover history and compress into summary features
    for the report prompt. Returns empty dict if no data available.
    """
    try:
        rows = turnover_history_store.get_history(market, code, days=10)
        if not rows:
            return {}
        rates = [r["turnover_rate"] for r in rows if r.get("turnover_rate") is not None]
        if not rates:
            return {}

        avg_10d = round(sum(rates) / len(rates), 2)
        avg_5d  = round(sum(rates[-5:]) / len(rates[-5:]), 2) if len(rates) >= 5 else avg_10d
        latest  = rates[-1]

        # Trend: compare last 3 days vs first half
        if len(rates) >= 6:
            early = sum(rates[:len(rates)//2]) / (len(rates)//2)
            late  = sum(rates[len(rates)//2:]) / (len(rates) - len(rates)//2)
            if late > early * 1.3:
                trend = "accelerating"
            elif late < early * 0.7:
                trend = "cooling"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        elevated_days = sum(1 for r in rates if r > avg_10d * 1.5)
        latest_vs_avg = round(latest / avg_10d, 2) if avg_10d else None

        return {
            "days_available":   len(rates),
            "avg_turnover_10d": avg_10d,
            "avg_turnover_5d":  avg_5d,
            "latest_turnover":  latest,
            "trend":            trend,            # accelerating / stable / cooling
            "elevated_days":    elevated_days,    # days > 1.5x avg
            "latest_vs_avg":    latest_vs_avg,    # e.g. 2.1 means today is 2.1x the 10d avg
        }
    except Exception as exc:
        log.warning("Turnover context build failed for %s:%s — %s", market, code, exc)
        return {}


def _build_candidate_context(market: str, code: str) -> dict:
    """
    Check if the stock is currently in the candidates pool and return realtime metrics.
    """
    if market.upper() != "CN":
        return {}
    try:
        from backend.screening.screening_service import get_candidates
        pool = get_candidates(force_refresh=False)
        candidates = pool.get("candidates", [])
        match = next((c for c in candidates if c.get("code") == code), None)
        if not match:
            return {"in_candidates_pool": False}
        signal_cache = _load_signals_cache("CN")
        fc = _build_financial_check(signal_cache.get(code))
        return {
            "in_candidates_pool": True,
            "current_price":      match.get("current_price"),
            "turnover_today":     match.get("turnover"),
            "pct_change_today":   match.get("pct_change"),
            "circ_mv_yi":         match.get("circ_mv"),
            "candidate_reason":   match.get("candidate_reason"),
            "financial_check":    fc.get("status"),
        }
    except Exception as exc:
        log.warning("Candidate context build failed for %s:%s — %s", market, code, exc)
        return {}


@app.route("/api/report/<market>/<code>", methods=["POST"])
def generate_report(market: str, code: str):
    snapshot = store.get_company_snapshot(market, code)
    if not snapshot:
        return jsonify({"error": "Company snapshot not found"}), 404
    signals = rule_engine.evaluate(snapshot)

    # Enrich with realtime context
    turnover_ctx  = _build_turnover_context(market, code)
    candidate_ctx = _build_candidate_context(market, code)

    return jsonify(generate_report_payload(
        snapshot, signals,
        turnover_context=turnover_ctx,
        candidate_context=candidate_ctx,
    )), 200


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

    candidates = attach_candidate_scores(candidates)

    page = _int_param("page", 1, minimum=1)
    page_size_default = _int_param("limit", 100, minimum=1, maximum=500)
    page_size = _int_param("page_size", page_size_default, minimum=1, maximum=500)
    signal_cache = _load_signals_cache("CN")
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

    entry = attach_candidate_scores([entry])[0]

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
    expected_dates = _expected_turnover_dates(
        market,
        start_date=start_date,
        end_date=end_date,
        days=day_count,
    )
    hydration = {
        "attempted": False,
        "status": "not_needed",
        "reason": None,
    }
    needs_hydration = False
    if market == "CN":
        if not rows:
            needs_hydration = True
        elif day_count and len(rows) < day_count:
            needs_hydration = True
        elif expected_dates and len({row.get("date") for row in rows if row.get("date")}) < len(expected_dates):
            needs_hydration = True

    if needs_hydration:
        hydration["attempted"] = True
        hydration["status"] = "hydrating"
        try:
            rows = hydrate_single_code_turnover_history(
                code,
                market=market,
                days=day_count or 10,
                start_date=start_date,
                end_date=end_date,
            )
            hydration["status"] = "success"
        except Exception as exc:
            hydration["status"] = "failed"
            hydration["reason"] = str(exc)
            expected_rows = _merge_turnover_rows_with_expected_dates([], expected_dates, market=market, code=code) if expected_dates else []
            return jsonify({
                "market": market,
                "code": code,
                "start_date": start_date,
                "end_date": end_date,
                "days": day_count,
                "total": len(expected_rows),
                "results": expected_rows,
                "hydration": hydration,
                "summary": {
                    "available_points": 0,
                    "missing_points": len(expected_rows),
                    "zero_value_points": 0,
                },
                "display_status": "fetch_failed",
            }), 503
    merged_rows = _merge_turnover_rows_with_expected_dates(rows, expected_dates, market=market, code=code) if expected_dates else [
        {
            **row,
            "has_data": row.get("turnover_rate") is not None,
            "data_status": "available" if row.get("turnover_rate") is not None else "missing",
        }
        for row in rows
    ]
    available_points = [row for row in merged_rows if row.get("has_data")]
    zero_value_points = sum(1 for row in available_points if float(row.get("turnover_rate") or 0) == 0.0)
    missing_points = sum(1 for row in merged_rows if not row.get("has_data"))
    if not available_points:
        display_status = "empty"
    elif missing_points:
        display_status = "partial"
    else:
        display_status = "ready"
    return jsonify({
        "market": market,
        "code": code,
        "start_date": start_date,
        "end_date": end_date,
        "days": day_count,
        "total": len(merged_rows),
        "results": merged_rows,
        "hydration": hydration,
        "summary": {
            "available_points": len(available_points),
            "missing_points": missing_points,
            "zero_value_points": zero_value_points,
        },
        "display_status": display_status,
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
    results = []
    for item in get_favorites(user["id"]):
        if _favorite_name_needs_repair(item):
            company = repository.get_company_profile(item.get("market", ""), item.get("code", ""))
            if company and company.get("name"):
                corrected_name = str(company["name"]).strip()
                item = {**item, "name": corrected_name}
                update_favorite_name(user["id"], item.get("market", ""), item.get("code", ""), corrected_name)
        results.append(item)
    return jsonify({"results": results})


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
    if not name or str(name).strip() == str(code).strip():
        company = repository.get_company_profile(market, code)
        if company and company.get("name"):
            name = company["name"]
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
