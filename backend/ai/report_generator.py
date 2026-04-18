from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Any

from backend.config import LLM_API_KEY, LLM_PROVIDER

log = logging.getLogger(__name__)

# DeepSeek is OpenAI-compatible; swap base URL for other providers.
_PROVIDER_URLS: dict[str, str] = {
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "openai":   "https://api.openai.com/v1/chat/completions",
}

_PROVIDER_MODELS: dict[str, str] = {
    "deepseek": "deepseek-chat",
    "openai":   "gpt-4o-mini",
}

# ── Phase 1: Structured reasoning ────────────────────────────────────────────

_PHASE1_SYSTEM = """你是一名专业的 A 股量化风险分析师。
你将收到一家上市公司的多层数据：财务规则信号、近年财务数据、实时候选池指标、历史换手率趋势。
请先进行内部结构化判断，输出一个 JSON 对象，不要输出任何文字说明。

JSON 字段定义：
{
  "stock_situation_type": 一句话定位该股当前状态，如"财务偏弱+盘面高度活跃"/"基本面稳健+温和放量"/"财务与盘面背离"/"低位持续活跃待验证"等,
  "financial_risk_level": "high" | "medium" | "low" | "unknown",
  "market_activity_level": "high" | "medium" | "low" | "none" （根据候选池和换手数据判断）,
  "turnover_pattern": "spike_only"（仅今日异动）| "multi_day_elevated"（持续多日活跃）| "accelerating"（活跃度在提速）| "cooling"（活跃度在降温）| "no_data",
  "evidence_alignment": "aligned"（财务与盘面共振）| "conflicting"（财务偏弱但盘面活跃，或财务好但盘面冷）| "neutral",
  "main_tension": 用一句话指出最核心的矛盾或张力，如"财务现金流持续承压，但市场资金持续关注"，不超过30字,
  "watch_points": 数组，列出2-3个最值得后续跟踪的具体观察点，每条不超过20字,
  "report_tone": "cautious"（谨慎）| "neutral"（中性）| "constructive"（相对积极但需观察）
}

每个判断必须有据可依，不得捏造。若某类数据缺失，在对应字段注明 unknown 或 no_data。"""


_PHASE2_SYSTEM = """你是一名专业的财务与公司治理风险分析师，擅长 A 股和台股上市公司分析。
你将收到：
1. 多层结构化数据（财务规则、近年财务、实时候选池、换手历史趋势）
2. 你的内部分析判断结果（JSON）

请根据以上内容，用中文撰写一份风险备忘录。

格式要求：
- 输出 Markdown，包含三个章节：## 当前状态定位、## 多源证据整合、## 核心矛盾与观察要点
- 总字数 500-700 字
- **每一个判断或结论，必须在句末用括号标注数据来源**，例如：
  （来源：F2规则）（来源：候选池实时）（来源：换手历史）（来源：财务数据）
  这一点非常重要，不得省略
- 语言专业客观，面向机构投资者
- 不得捏造任何数据或结论，数据缺失时直接说明

章节职责：
## 当前状态定位
  - 直接给出这家公司当前"更像什么状态"的判断（一句话定位 + 1-2段展开）
  - 说明财务风险等级 + 市场活跃度，并分别标注来源

## 多源证据整合
  - 财务规则：哪些触发、哪些正常、哪些数据缺失（来源：规则引擎）
  - 近年财务趋势：关键指标的变化方向（来源：财务数据）
  - 候选池实时（如有）：今日换手/涨幅/现价/流通市值（来源：候选池实时）
  - 换手历史趋势（如有）：近期换手形态是脉冲还是持续（来源：换手历史）
  - 明确指出各层证据是互相支持还是存在冲突

## 核心矛盾与观察要点
  - 当前最主要的矛盾是什么（一句话）
  - 列出2-3个具体的后续观察要点（不要泛泛说"持续关注"）"""


def _build_data_prompt(
    snapshot: dict[str, Any],
    signal_result: dict[str, Any],
    turnover_context: dict,
    candidate_context: dict,
) -> str:
    name     = snapshot.get("name", "未知公司")
    market   = snapshot.get("market", "")
    code     = snapshot.get("code", "")
    industry = snapshot.get("industry", "未知行业")
    summary  = signal_result.get("summary", {})

    # ── Signal lines ──
    signals = signal_result.get("financial_signals", []) + signal_result.get("governance_signals", [])
    signal_lines = []
    for s in signals:
        if s.get("triggered"):
            status = "⚠️ 触发"
        elif s.get("status") == "not_available":
            status = "— 数据缺失"
        else:
            status = "✓ 正常"
        line = f"  {status} [{s.get('signal_id','')}] {s.get('name', '')}: {s.get('message', '')}"
        if s.get("value") and isinstance(s["value"], dict):
            kv = ", ".join(f"{k}={v}" for k, v in list(s["value"].items())[:4])
            line += f"（{kv}）"
        signal_lines.append(line)

    # ── Recent financials ──
    annual = snapshot.get("financials", {}).get("annual", [])
    fin_lines = []
    for yr in annual[:3]:
        rev  = yr.get("revenue")
        np_  = yr.get("net_profit")
        ocf  = yr.get("operating_cash_flow")
        ta   = yr.get("total_assets")
        tl   = yr.get("total_liabilities")
        lev  = round(tl / ta, 3) if ta and tl else None
        parts = [f"期间={yr.get('period')}"]
        if rev  is not None: parts.append(f"营收={rev:,.0f}元")
        if np_  is not None: parts.append(f"净利润={np_:,.0f}元")
        if ocf  is not None: parts.append(f"经营现金流={ocf:,.0f}元")
        if lev  is not None: parts.append(f"资产负债率={lev:.1%}")
        fin_lines.append("  " + ", ".join(parts))

    # ── Candidate context ──
    cand_lines = []
    if candidate_context.get("in_candidates_pool"):
        cand_lines = [
            f"  今日在候选池中（来源：候选池实时）",
            f"  现价={candidate_context.get('current_price')}元",
            f"  今日换手率={candidate_context.get('turnover_today')}%",
            f"  今日涨幅={candidate_context.get('pct_change_today')}%",
            f"  流通市值={candidate_context.get('circ_mv_yi')}亿",
            f"  候选原因：{candidate_context.get('candidate_reason', '—')}",
            f"  财务风险等级（系统评估）：{candidate_context.get('financial_check', '无数据')}",
        ]
    elif candidate_context.get("in_candidates_pool") is False:
        cand_lines = ["  今日未出现在候选池（来源：候选池实时）"]
    else:
        cand_lines = ["  候选池数据不可用（市场非 CN 或接口异常）"]

    # ── Turnover trend ──
    tv = turnover_context
    if tv:
        trend_map = {
            "accelerating": "加速上升",
            "stable": "基本平稳",
            "cooling": "明显降温",
            "insufficient_data": "数据不足"
        }
        tv_lines = [
            f"  可用天数：{tv.get('days_available')}天（来源：换手历史）",
            f"  近10日均换手率：{tv.get('avg_turnover_10d')}%",
            f"  近5日均换手率：{tv.get('avg_turnover_5d')}%",
            f"  最新一日换手率：{tv.get('latest_turnover')}%",
            f"  换手趋势：{trend_map.get(tv.get('trend',''), tv.get('trend','未知'))}",
            f"  近期高活跃天数（>1.5x均值）：{tv.get('elevated_days')}天",
            f"  今日换手 vs 10日均值比：{tv.get('latest_vs_avg')}x",
        ]
    else:
        tv_lines = ["  暂无历史换手率数据"]

    sections = [
        f"## 公司基本信息",
        f"  名称：{name}（{market}:{code}）",
        f"  行业：{industry}",
        f"  触发信号数：{summary.get('triggered_count', 0)} / {summary.get('total_rules', 0)}",
        "",
        "## 规则引擎信号（来源：规则引擎）",
        *signal_lines,
        "",
        "## 近年财务数据（来源：财务数据，单位：元）",
        *(fin_lines if fin_lines else ["  暂无财务数据"]),
        "",
        "## 候选池实时数据",
        *cand_lines,
        "",
        "## 历史换手率趋势",
        *tv_lines,
    ]
    return "\n".join(sections)


def _call_llm(system: str, user: str, *, json_mode: bool = False) -> str:
    provider = (LLM_PROVIDER or "deepseek").lower()
    url   = _PROVIDER_URLS.get(provider, _PROVIDER_URLS["deepseek"])
    model = _PROVIDER_MODELS.get(provider, _PROVIDER_MODELS["deepseek"])

    body: dict[str, Any] = {
        "model":       model,
        "messages":    [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens":  1024,
        "temperature": 0.25,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _fallback_report(snapshot: dict[str, Any], signal_result: dict[str, Any]) -> str:
    triggered = [
        s["name"]
        for s in signal_result.get("financial_signals", []) + signal_result.get("governance_signals", [])
        if s.get("triggered")
    ]
    name   = snapshot.get("name", "未知公司")
    market = snapshot.get("market", "")
    code   = snapshot.get("code", "")
    count  = signal_result.get("summary", {}).get("triggered_count", 0)
    lines  = [
        f"# {name} 风险摘要",
        "",
        f"- 市场：{market}　代码：{code}",
        f"- 触发信号数：{count}",
        "",
    ]
    if triggered:
        lines += ["## 触发信号", *[f"- {t}" for t in triggered], ""]
    lines += ["## 说明", "（LLM 服务暂时不可用，以上为规则引擎结构化摘要）"]
    return "\n".join(lines)


def generate_report_payload(
    snapshot: dict[str, Any],
    signal_result: dict[str, Any],
    *,
    turnover_context: dict | None = None,
    candidate_context: dict | None = None,
) -> dict[str, Any]:
    turnover_context  = turnover_context  or {}
    candidate_context = candidate_context or {}

    name = snapshot.get("name", "未知公司")
    triggered = [
        s["name"]
        for s in signal_result.get("financial_signals", []) + signal_result.get("governance_signals", [])
        if s.get("triggered")
    ]

    if not LLM_API_KEY:
        return {
            "company_id":      snapshot.get("company_id"),
            "title":           f"{name} 风险摘要",
            "highlights":      triggered,
            "report_markdown": _fallback_report(snapshot, signal_result),
            "source":          "fallback (no api key)",
        }

    data_prompt = _build_data_prompt(
        snapshot, signal_result,
        turnover_context, candidate_context,
    )

    try:
        # ── Phase 1: structured reasoning ──
        phase1_raw = _call_llm(_PHASE1_SYSTEM, data_prompt, json_mode=True)
        try:
            reasoning = json.loads(phase1_raw)
        except json.JSONDecodeError:
            reasoning = {}
            log.warning("Phase 1 JSON parse failed, continuing without reasoning object")

        # ── Phase 2: report generation ──
        phase2_user = "\n\n".join([
            "## 原始数据",
            data_prompt,
            "## 你的内部分析判断（第一阶段输出）",
            json.dumps(reasoning, ensure_ascii=False, indent=2),
            "请根据以上内容生成风险备忘录，每个判断句末注明数据来源。",
        ])
        report_markdown = _call_llm(_PHASE2_SYSTEM, phase2_user)
        source = "llm_two_phase"

    except Exception as exc:
        log.warning("LLM call failed: %s — falling back to rule summary", exc)
        report_markdown = _fallback_report(snapshot, signal_result)
        source = f"fallback ({exc})"

    return {
        "company_id":      snapshot.get("company_id"),
        "title":           f"{name} 风险摘要",
        "highlights":      triggered,
        "report_markdown": report_markdown,
        "source":          source,
    }
