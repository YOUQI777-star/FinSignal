from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any

from backend.config import LLM_API_KEY, LLM_PROVIDER


# DeepSeek is OpenAI-compatible; swap base URL for other providers.
_PROVIDER_URLS: dict[str, str] = {
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "openai":   "https://api.openai.com/v1/chat/completions",
}

_PROVIDER_MODELS: dict[str, str] = {
    "deepseek": "deepseek-chat",
    "openai":   "gpt-4o-mini",
}

_SYSTEM_PROMPT = """你是一名专业的财务与公司治理风险分析师，擅长 A 股和台股上市公司分析。
请根据下方提供的结构化信号数据，用中文撰写一份简洁的风险备忘录。
要求：
- 只使用输入数据中已有的信息，不得捏造数据或结论
- 语言专业、客观，适合机构投资者阅读
- 重点解读已触发（triggered）的信号，说明其财务含义和潜在风险
- 对 not_available 的信号，简要说明数据缺失原因
- 输出格式为 Markdown，包含：## 公司概况、## 风险信号解读、## 综合评估 三个章节
- 总字数控制在 400-600 字"""


def _build_user_prompt(snapshot: dict[str, Any], signal_result: dict[str, Any]) -> str:
    name = snapshot.get("name", "未知公司")
    market = snapshot.get("market", "")
    code = snapshot.get("code", "")
    industry = snapshot.get("industry", "未知行业")
    summary = signal_result.get("summary", {})

    signals = signal_result.get("financial_signals", []) + signal_result.get("governance_signals", [])
    signal_lines = []
    for s in signals:
        status = "触发" if s.get("triggered") else ("数据缺失" if s.get("status") == "not_available" else "正常")
        line = f"- [{status}] {s.get('name', s.get('signal_id', ''))}: {s.get('message', '')}"
        if s.get("value") and isinstance(s["value"], dict):
            kv = ", ".join(f"{k}={v}" for k, v in list(s["value"].items())[:4])
            line += f"（{kv}）"
        signal_lines.append(line)

    # Include recent financials for context
    annual = snapshot.get("financials", {}).get("annual", [])
    fin_lines = []
    for yr in annual[:3]:
        rev = yr.get("revenue")
        np_ = yr.get("net_profit")
        ocf = yr.get("operating_cash_flow")
        lev = (yr.get("total_liabilities", 0) / yr.get("total_assets", 1)
               if yr.get("total_assets") else None)
        parts = [f"期间={yr.get('period')}"]
        if rev is not None:
            parts.append(f"营收={rev:,.0f}")
        if np_ is not None:
            parts.append(f"净利润={np_:,.0f}")
        if ocf is not None:
            parts.append(f"经营现金流={ocf:,.0f}")
        if lev is not None:
            parts.append(f"资产负债率={lev:.1%}")
        fin_lines.append("  " + ", ".join(parts))

    return "\n".join([
        f"## 公司基本信息",
        f"- 名称：{name}（{market}:{code}）",
        f"- 行业：{industry}",
        f"- 触发信号数：{summary.get('triggered_count', 0)} / {summary.get('total_rules', 0)}",
        f"- 快照层级：{summary.get('snapshot_tier', '未知')}",
        "",
        "## 信号评估结果",
        *signal_lines,
        "",
        "## 近期财务数据（单位：元）",
        *(fin_lines if fin_lines else ["  暂无财务数据"]),
    ])


def _call_llm(user_prompt: str) -> str:
    """Call DeepSeek (or configured provider) and return the response text."""
    provider = (LLM_PROVIDER or "deepseek").lower()
    url = _PROVIDER_URLS.get(provider, _PROVIDER_URLS["deepseek"])
    model = _PROVIDER_MODELS.get(provider, _PROVIDER_MODELS["deepseek"])

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _fallback_report(snapshot: dict[str, Any], signal_result: dict[str, Any]) -> str:
    """Rule-based summary used when LLM is unavailable."""
    triggered = [
        s["name"]
        for s in signal_result.get("financial_signals", []) + signal_result.get("governance_signals", [])
        if s.get("triggered")
    ]
    name = snapshot.get("name", "未知公司")
    market = snapshot.get("market", "")
    code = snapshot.get("code", "")
    count = signal_result.get("summary", {}).get("triggered_count", 0)
    lines = [
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


def generate_report_payload(snapshot: dict[str, Any], signal_result: dict[str, Any]) -> dict[str, Any]:
    name = snapshot.get("name", "未知公司")
    triggered = [
        s["name"]
        for s in signal_result.get("financial_signals", []) + signal_result.get("governance_signals", [])
        if s.get("triggered")
    ]

    if LLM_API_KEY:
        try:
            user_prompt = _build_user_prompt(snapshot, signal_result)
            report_markdown = _call_llm(user_prompt)
            source = "llm"
        except Exception as exc:
            report_markdown = _fallback_report(snapshot, signal_result)
            source = f"fallback ({exc})"
    else:
        report_markdown = _fallback_report(snapshot, signal_result)
        source = "fallback (no api key)"

    return {
        "company_id": snapshot.get("company_id"),
        "title": f"{name} 风险摘要",
        "highlights": triggered,
        "report_markdown": report_markdown,
        "source": source,
    }
