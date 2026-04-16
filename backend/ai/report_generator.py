from __future__ import annotations

from typing import Any


def generate_report_payload(snapshot: dict[str, Any], signal_result: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic placeholder report until LLM integration is enabled."""
    triggered = [
        item["name"]
        for item in signal_result.get("financial_signals", []) + signal_result.get("governance_signals", [])
        if item.get("triggered")
    ]
    return {
        "company_id": snapshot.get("company_id"),
        "title": f"{snapshot.get('name')} 风险摘要",
        "highlights": triggered,
        "report_markdown": "\n".join(
            [
                f"# {snapshot.get('name')} 风险摘要",
                "",
                f"- 市场：{snapshot.get('market')}",
                f"- 代码：{snapshot.get('code')}",
                f"- 触发信号数：{signal_result.get('summary', {}).get('triggered_count', 0)}",
                "",
                "## 说明",
                "当前报告为规则引擎的结构化摘要占位版本，后续将替换为 LLM 解释层。",
            ]
        ),
    }
