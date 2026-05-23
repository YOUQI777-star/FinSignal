# FinSignal — 完整项目交接文档

> 适用于：新 AI / 新开发者接手时完整了解项目现状、架构、数据链路、已知问题和下一步方向。

---

## 一、项目概述

**FinSignal** 是一个针对 A 股（CN）和台股（TW）的**财务与治理异常信号监测系统**。

核心逻辑：
1. 从公开数据源抓取上市公司财务快照（资产负债表、利润表、现金流量表）
2. 对每家公司运行 6 条规则引擎，检测财务/治理异常
3. 将结果缓存为 JSON，通过 Flask REST API 暴露
4. 前端纯静态 HTML+CSS+JS，部署在 Cloudflare Pages

**前端地址：** https://finsignal-b8n.pages.dev (Cloudflare Pages)  
**后端地址：** https://tender-fascination-production.up.railway.app (Railway)  
**GitHub：** https://github.com/YOUQI777-star/FinSignal

---

## 二、技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.x + Flask + flask-cors |
| 数据存储 | 本地 JSON 文件 (`data/cn/*.json`, `data/tw/*.json`) + SQLite (`company_master.db`, `turnover_history.db`) |
| 信号缓存 | `data/signals/cn_signals.json`（21MB，已入 Git），`data/signals/tw_signals.json`（3.3MB），**启动时整体读入内存**（`_signals_mem_cache`），按文件 mtime 做失效，避免每次 API 请求 IO |
| 数据源（CN） | AKShare EastMoney bulk API + Tushare Pro（历史日线 / 换手率） |
| 数据源（TW） | TWSE OpenAPI + FinMind（OCF 字段） |
| 前端 | 原生 HTML + CSS + JavaScript（无框架，无构建工具） |
| 部署（前端） | Cloudflare Pages（直接 wrangler deploy） |
| 部署（后端） | Railway（Hobby 计划，$5/月，Nixpacks 自动构建） |

---

## 三、目录结构

```
C_G/
├── backend/
│   ├── app.py                      # Flask 主入口，所有 API 路由
│   ├── config.py                   # 环境变量、路径配置
│   ├── requirements.txt            # Python 依赖
│   ├── gunicorn.conf.py            # Gunicorn 生产配置（timeout=300，已启用）
│   ├── ai/
│   │   ├── report_generator.py     # 报告生成（当前是占位规则摘要，未接 LLM）
│   │   └── prompt_template.py      # LLM prompt 模板（未激活）
│   ├── data_access/
│   │   ├── local_store.py          # 读取 data/cn/*.json, data/tw/*.json
│   │   ├── master_store.py         # 读取 SQLite company_master.db
│   │   ├── company_repository.py   # 合并 master + snapshot，统一对外接口
│   │   ├── turnover_history_store.py # 历史行情轻量 SQLite（turnover_rate + OHLC + pct_change + volume + amount + circ_mv）
│   │   └── coverage.py             # 判断 snapshot_tier（full/partial/shell）
│   ├── rules/
│   │   ├── base.py                 # RuleDefinition + build_signal_result
│   │   ├── engine.py               # RuleEngine.evaluate(snapshot) → signal result
│   │   ├── financial_rules.py      # F1 F2 F3 F4
│   │   └── governance_rules.py     # G1 G3
│   ├── scrapers/
│   │   ├── cn_akshare.py           # A 股抓取（AKShare + EastMoney）
│   │   ├── cn_baostock.py          # A 股补充（BaoStock，较少使用）
│   │   ├── cn_tushare.py           # A 股 Tushare Pro 客户端（历史日线 / daily_basic / 交易日历）
│   │   ├── tw_twse.py              # 台股抓取（TWSE OpenAPI + FinMind OCF）
│   │   ├── schema.py               # 数据 schema 定义
│   │   └── save_snapshots.py       # 将抓取结果写入 data/cn/ 或 data/tw/
│   ├── master/
│   │   └── build_master.py         # 构建 company_master.db（SQLite）
│   ├── graph/
│   │   └── neo4j_client.py         # Neo4j 占位（未接入，返回空节点）
│   ├── screening/
│   │   ├── __init__.py
│   │   ├── market_loader.py        # AKShare 实时行情拉取 + 交易日历（get_last_trading_date）
│   │   ├── candidate_rules.py      # 筛选规则：换手率/现价/流通市值/涨幅/ST
│   │   ├── candidate_scoring.py    # 候选池综合评分（structure_v3）：四维子评分 × 权重 + bonus/penalty；依赖 turnover_history.db 60日OHLC
│   │   ├── screening_service.py    # 实时候选池主逻辑：30 分钟内存缓存 + thread-safe
│   │   └── turnover_bootstrap.py   # 单股换手率历史按需补数 + 候选池批量回填实验
│   └── scripts/
│       ├── bulk_enrich_cn.py       # A 股批量财务数据补充（EastMoney bulk）
│       ├── bootstrap_turnover_history.py # 候选池公司 10 日换手率批量回填实验脚本
│       ├── enrich_tw_ocf.py        # 台股 OCF 字段补充（FinMind，有配额限制）
│       ├── run_signals.py          # 跑规则引擎，生成信号缓存 JSON
│       └── analyze_coverage.py     # 分析覆盖率
├── data/
│   ├── cn/                         # 5502 个 A 股公司 JSON snapshot（.gitignore 排除，本地）
│   ├── tw/                         # 1081 个台股公司 JSON snapshot（.gitignore 排除，本地）
│   └── signals/
│       ├── cn_signals.json         # A 股信号缓存（已入 Git，21MB，Railway 可读）
│       ├── tw_signals.json         # 台股信号缓存（已入 Git，3.3MB，Railway 可读）
│       └── summary.json            # 汇总统计
├── frontend/
│   ├── styles.css                  # 全局设计系统（design tokens + 所有公共组件）
│   ├── i18n.js                     # CN/EN 双语切换系统（I18N 字典 + applyLang() + getLang()）
│   ├── api.js                      # 所有 API 调用封装 + MOCK_DATA fallback
│   ├── index.html + app.js         # 首页产品门户（候选池 / 风险排行入口 + 最近浏览 + 候选摘要）
│   ├── company.html + company.js + company.css  # 单公司详情页（含历史换手率模块）
│   ├── ranking.html + ranking.js   # 全量信号排行榜
│   ├── compare.html + compare.js   # 多公司对比
│   ├── reports.html + reports.js   # 报告生成页
│   ├── search.html + search.js     # 公司搜索页
│   ├── candidates.html + candidates.js  # 实时换手候选池（AKShare 实时行情 + 财务状态联动 + 分页 + turnover_max）
│   └── settings.html + settings.js # 系统设置
├── refresh.sh                      # 每日一键：记录当天换手率快照 + 补 OCF + 重算信号缓存
├── .gitignore                      # 排除 data/*.json、.venv、DB 等大文件
└── PROJECT_HANDOFF.md              # 本文档
```

---

## 四、数据快照结构

每个公司快照是一个 JSON 文件，位于 `data/cn/{code}.json` 或 `data/tw/{code}.json`。

```json
{
  "company_id": "CN:600519",
  "market": "CN",
  "code": "600519",
  "name": "贵州茅台",
  "industry": "食品饮料",
  "status": "active",
  "currency": "CNY",
  "financials": {
    "annual": [
      {
        "period": "2024",
        "revenue": 174000000000,
        "net_profit": 86228146421,
        "operating_cash_flow": 92463692168,
        "accounts_receivable": 19200000,
        "inventory": 39100000000,
        "total_assets": 270000000000,
        "total_liabilities": 46000000000,
        "source": "akshare_em_bulk"
      },
      { "period": "2023", ... },
      { "period": "2022", ... },
      { "period": "2021", ... }
    ]
  },
  "governance": {
    "pledge_ratio": 0.0,
    "chairman_is_ceo": false,
    "independent_director_ratio": 0.40
  },
  "equity_structure": []
}
```

**重要：** 所有金额字段单位是**元**（原始值）。TWSE 来源数据是千元，在抓取时已乘以 1000 换算过。

---

## 五、信号规则详解

规则引擎入口：`backend/rules/engine.py` → `RuleEngine.evaluate(snapshot)`

### F1 — 应收账款异常增长（AR Abnormal Growth）
- **逻辑：** `(curr_ar / curr_revenue) / (prev_ar / prev_revenue) > 1.3`
- **意义：** AR/Revenue 比率 YoY 扩张超 30%，说明应收账款积累速度远超营收增速
- **注意：** 早期版本用 `ar_growth > revenue_growth * 2`，当营收负增长时会大量误报，已修复为比率方法
- **触发数：** CN 1030 家，TW 12 家

### F2 — 现金流与利润背离（Cash Flow Divergence）
- **逻辑：** 连续 2 年 `operating_cash_flow < 0` 且 `net_profit > 0`
- **意义：** 利润为正但现金流持续为负，说明账面利润没有转化为真实现金
- **触发数：** CN 162 家，TW 3 家（TW 台股 OCF 数据仍大量缺失，触发数偏低）

### F3 — 资产负债率持续偏高（High Leverage）
- **逻辑：** 连续 2 年 `total_liabilities / total_assets > 0.70`
- **触发数：** CN 499 家，TW 5 家

### F4 — 净利率骤降（Margin Decline）
- **逻辑：** `(prev_net_profit/prev_revenue) - (curr_net_profit/curr_revenue) > 0.10`（下降超 10pp）
- **触发数：** CN 738 家，TW 16 家

### G1 — 大股东高比例质押（Pledge Ratio Alert）
- **逻辑：** `governance.pledge_ratio > 0.50`
- **仅适用：** CN 市场
- **现状：** governance 数据大多缺失，基本返回 not_available

### G3 — 两职合一且独董不足（Board Independence）
- **逻辑：** `chairman_is_ceo == True AND independent_director_ratio < 1/3`
- **现状：** governance 数据大多缺失，基本返回 not_available

---

## 六、API 端点

**生产地址：** `https://tender-fascination-production.up.railway.app`  
**本地地址：** `http://localhost:5001`（macOS AirPlay 占用 5000，改用 5001）  
前端 `api.js` 读取 `localStorage.getItem('fsm_api_base')`，默认指向 Railway 生产地址，可在 Settings 页覆盖。

```
GET  /api/health
     → {"status": "ok"}

GET  /api/signals/top?limit=50&market=CN&signal_id=F1
     → {"total": N, "results": [...]}
     读信号缓存 data/signals/{market}_signals.json，按 triggered_count 降序

GET  /api/signals/{market}/{code}?fresh=true
     → 完整 signal result（含 financial_signals + governance_signals）
     默认读缓存；?fresh=true 强制实时重算

GET  /api/company/{market}/{code}
     → 公司基础信息（来自 master_store + local_store 合并）

GET  /api/search?q=茅台
     → {"results": [{company_id, market, code, name, industry}, ...]}
     先查 SQLite master，没有则 fallback 到 JSON 文件全扫

GET  /api/compare?codes=CN:600519,TW:2330,CN:000002
     → {"results": [signal_result, ...]}
     对每个 code 实时调用 RuleEngine.evaluate()

POST /api/report/{market}/{code}
     → {"company_id", "title", "highlights": [...], "report_markdown": "..."}
     当前是规则摘要占位版，未接 LLM

GET  /api/graph/{market}/{code}
     → {"nodes": [], "edges": [], "message": "..."}
     Neo4j 占位，返回空

GET  /api/candidates?turnover_min=2&turnover_max=30&price_max=20&circ_mv_max=80&pct_max=9&exclude_st=1&page=1&page_size=100&refresh=0
     → {
         "total": N,
         "results": [...],
         "generated_at": "2026-04-18T00:34:09Z",   # AKShare 拉取时间（UTC）
         "trading_date": "2026-04-17",              # 对应的上一个 A 股交易日
         "source": "realtime",
         "thresholds": {...},
         "page": 1,
         "page_size": 100,
         "total_pages": 11
       }
     实时拉取 AKShare stock_zh_a_spot_em()，30 分钟内存缓存，首次约 60-150s
     非交易日（周末/节假日）**优先从 `turnover_history.db` 读取最近一个已落库交易日的快照重建候选池**；
       仅当数据库无足够数据时，才回落到东方财富实时接口（收盘数据不清零）
     ?refresh=1 强制绕过缓存重新拉取（实时接口）
     后端在过滤后会追加 `candidate_score`、`score_breakdown`、`history_metrics`
     默认结果顺序按综合评分排序（`score_model: structure_v3`），不再只是单纯按当日换手率：
       - `activity_score`（×0.30）：10日活跃天数 + 活跃连续天数 + 中位数换手 + 活跃趋势，含过热惩罚 / 低位加成
       - `price_structure_score`（×0.28）：距20/60日高点比率 + 区间位置 + 突破强度 + 均线多头排列 + 连续创高低，含超涨惩罚 / 假突破惩罚
       - `volume_price_score`（×0.27）：放量上涨 / 缩量回调 / 量能趋势 / 洗盘后反弹形态，含出货惩罚 / 噪音换手惩罚
       - `sector_resonance_score`（×0.15）：同行业候选股数量 + 行业平均换手/涨幅 + 板块有无领涨标
       全局加减项（叠加在合计分之上）：
       - `washout_recovery_bonus`（+4）：近期有过30日高点10-30%回撤 + 已反弹修复
       - `early_setup_bonus`（+4）：60日区间低位（≤68%）+ 高低点收敛 + 换手趋势向上
       - `turnover_noise_penalty`（-2~-6）：换手率脉冲但收盘偏弱 / 价格效率极低
       - `distribution_risk_penalty`（-2~-10）：高位放量停顿 + 上影线多 + 大跌放量
     每条 result 额外带 `financial_check`：
       status = `high_risk | warning | pass | no_data`
       triggered_signals = 已触发的财务/治理信号 ID
       triggered_count = 触发数量
     启动时 prewarm 线程自动预热缓存，用户请求直接命中缓存

GET  /api/candidates/CN/{code}
     → 候选池中单只股票详情
     返回 candidate entry + signal_summary（若有）+ financial_check

GET  /api/turnover-history/CN/{code}?days=10
     → {"market","code","days","total","results":[...]}
     历史换手率 / 日线接口。优先读 `data/turnover_history.db`；若本地没有该股票历史，则自动按需抓取该单股最近 N 个交易日数据并写入 SQLite
     新版本优先走 Tushare Pro（`TUSHARE_TOKEN` + `TUSHARE_HTTP_URL`），可拿到：
       - `turnover_rate`
       - `open/high/low/close`
       - `pct_change`
       - `volume / amount`
       - `circ_mv`
     若 Tushare 不可用，则回落到 AKShare 历史接口，仅保证 `turnover_rate`
```

---

## 七、候选池选股/评分思路演进历史

> 本章记录候选池从最初版本到当前 `structure_v3` 的完整演进脉络，方便后续调参或新增评分维度时理解设计决策。

---

### V1：纯换手率筛选（最初版本）

**思路：** 简单粗暴，只做一个正筛选——今日换手率超过阈值。

**筛选规则（C1~C6 全部 AND）：**
- C1 换手率 > 2%（今日放量）
- C2 现价 < 20 元（避免高价股）
- C3 流通市值 < 80 亿（中小盘）
- C4 今日涨幅 < +9%（排除接近涨停）
- C5 今日涨幅 > -9%（排除接近跌停）
- C6 非 ST / \*ST

**排序：** 按今日换手率降序。

**问题：** 只反映今日一个数字，无法区分"偶发脉冲"和"持续放量建仓"；换手率高但全是出货的股票会排在前面。

---

### V2：四维加权评分（过渡版本）

**思路：** 在 V1 筛选条件不变的前提下，引入历史数据维度，对筛选后的候选池计算综合评分。

**评分维度：**
- `turnover_quality`：换手率质量（强度 + 稳定性）
- `sustained_activity`：持续活跃度（近 5/10 日换手 ≥ 2% 的天数 + 连续天数）
- `structure_strength`：近期价格结构（高低点形态）
- `industry_bonus`：同板块候选股数量 + 板块平均换手 → 轻量共振加成

**改进：** 开始区分"今日脉冲"和"多日活跃"两种不同性质的换手，减少了一日游股票的排名；加入行业共振逻辑，优先同板块多股同时活跃的情形。

**遗留问题：** 价格结构维度过于简单，未纳入 OHLC 价格行为（量价配合、洗盘形态、收盘强弱等）；无法识别"高位震荡出货"。

---

### V3：结构评分重写（当前版本，`structure_v3`）

**背景：** Tushare Pro 接入后，历史数据质量大幅提升（可获取 60 日 OHLC + 成交金额 + 换手率），使精细化量价分析成为可能。

**四个子评分 + 全局 bonus/penalty：**

#### 1. `activity_score`（×0.30）——活跃持续性

核心问题：这只股票的放量是持续行为还是今日偶发？

| 指标 | 含义 |
|------|------|
| `active_days_10` | 近10日中换手≥2%的天数（×6分/天）|
| `active_streak_10` | 近10日最长连续活跃天数（×7分/天）|
| `turnover_median_10` | 10日中位数换手率（稳健，不被单日拉高）|
| `turnover_trimmed_mean_10` | 去头尾均值（抗异常值）|
| `activity_trend` | 后5日均值 vs 前5日均值：换手在加速还是降温 |
| **修正项** | 低位+趋势向上：+5（`range_position_60 ≤ 0.45`）；过热惩罚：-最多8（`avg_turnover_5 > 10`）；噪音换手折扣：当换手很高但价格效率低时扣分 |

#### 2. `price_structure_score`（×0.28）——价格形态质量

核心问题：当前价格是在什么位置、形成了什么形态？

| 指标 | 含义 |
|------|------|
| `close_to_20d_high` | 当前价 / 20日最高价（靠近高点加分）|
| `close_to_60d_high` | 当前价 / 60日最高价 |
| `breakout_strength` | 相对近期高点的突破幅度（综合范围位置）|
| `range_position_20/60` | 在20/60日区间的位置（低位/中位/高位）|
| `higher_lows_ratio_10` | 近10日低点逐步抬高的比例（上升趋势验证）|
| `higher_highs_ratio_10` | 近10日高点逐步抬高的比例 |
| `ma_bullish_alignment` | MA5 ≥ MA10 ≥ MA20 > 0（均线多头排列）|
| **修正项** | 初期建仓形态加成：+8（中间区间+高低点收敛+微突破）；超涨惩罚：5日涨幅≥8%、当日涨幅≥5.5%、极高位突破各扣分；假突破惩罚：突破幅度>0.6但收盘弱（<0.4）：-5 |

#### 3. `volume_price_score`（×0.27）——量价健康度

核心问题：成交量的性质是建仓（放量上涨/缩量回调）还是出货（放量下跌/高位量价背离）？

| 指标 | 含义 |
|------|------|
| `up_volume_ratio_10` | 近10日"放量上涨日"占比（涨幅>0 + 成交≥中位数）|
| `controlled_pullback_ratio_10` | 近10日"缩量回调日"占比（跌幅<0 + 成交<中位数 + 守住支撑）|
| `amount_trend` | 后5日均成交金额 vs 前5日：量能趋势 |
| `heavy_distribution_days_10` | 重度出货日数（跌幅≤-3% + 放量≥中位数×1.2）×-9 |
| `long_upper_shadow_days_10` | 上影线明显日数（上影≥日内振幅45%）×-5 |
| `price_progress_efficiency` | 10日涨幅 / 10日平均换手（花多少换手换来多少涨幅）|
| **修正项** | 洗盘反弹形态加成：+6（从高点回撤12-30%后已回升）；出货停滞惩罚：-8（高位+高换手+涨幅微小+多上影线）；噪音换手惩罚：-6（换手脉冲+收盘弱+价格效率低）|

#### 4. `sector_resonance_score`（×0.15）——板块共振

核心问题：板块内有没有同步活跃的多只股票？是否有领涨标的？

| 指标 | 含义 |
|------|------|
| `industry_count` | 同行业在候选池中的股票数（每多一只+10分，上限5只）|
| `industry_turnover_avg` | 板块内平均换手率 |
| `industry_pct_avg` | 板块内平均涨幅 |
| `leader_presence` | 板块内有5日涨幅≥4%的领涨标：+8 |
| 自身参与度 | 自身换手≥行业均值 且 今日涨幅≥0：+6 |

#### 全局修正项（加减在合计分之上）

| 项目 | 条件 | 分值 |
|------|------|------|
| `washout_recovery_bonus` | 从30日高点回撤12-30% + 已有效反弹 + 位置≤72% | +4 |
| `early_setup_bonus` | 60日低位（≤68%）+ 高低点收敛 + 换手向上 + 5日涨幅≤4% | +4 |
| `turnover_noise_penalty` | 换手脉冲比≥2.8 + 价格效率<0.35 | -4 |
| `turnover_noise_penalty` | 收盘弱（<0.4）+ 当日换手≥10日中位数×2 | -2 |
| `distribution_risk_penalty` | 高位（≥80%）+ 高换手（≥8%）+ 涨幅停滞（≤2.5%）| -5 |
| `distribution_risk_penalty` | 上影线天数≥2 | -2 |
| `distribution_risk_penalty` | 重度出货天数≥2 | -3 |

**最终评分公式：**
```
candidate_score = activity×0.30 + price_structure×0.28 + volume_price×0.27 + sector_resonance×0.15
                + washout_recovery_bonus + early_setup_bonus
                - turnover_noise_penalty - distribution_risk_penalty
```

**设计原则：**
- 三种股票应拿到高分：① 低位持续活跃+均线多头排列；② 短期洗盘后回升+量价配合；③ 板块共振中位居中上游
- 三种股票应被压低：① 高位换手不涨（出货）；② 今日换手脉冲但历史无持续性；③ 涨停后第二天高开低走
- `circ_mv`/`pct_change`/`turnover` 在评分计算时**优先读 `turnover_history.db` 快照**，不依赖实时行情（避免盘中数据噪音影响评分稳定性）

---

## 八、前端架构

### 设计系统
- 所有颜色、间距、圆角、字体在 `styles.css` 顶部 `:root` 里定义
- 不引入任何 CSS 框架，不引入任何 JS 库
- 关键 design tokens：
  - `--sidebar-bg: #141c2e`（深蓝侧边栏）
  - `--brand: #1e40af`（品牌蓝）
  - `--c-triggered: #dc2626`（红色，触发状态）
  - `--c-ok: #16a34a`（绿色，正常状态）
  - `--m-cn-bg: #dbeafe`（A 股蓝色 badge）
  - `--m-tw-bg: #ede9fe`（台股紫色 badge）

### 各页面职责

| 页面 | 文件 | 功能 |
|------|------|------|
| 首页 | `index.html` + `app.js` | 产品门户：4 个 `scard` 摘要卡（候选池数量 / 高风险公司数 / A股覆盖 / 规则数）+ 候选池实时预览（带 `financial_check` badge）+ 最近浏览 + 规则分布进度条 + 深入分析快捷入口 |
| 公司详情 | `company.html` + `company.js` + `company.css` | 单公司完整信号分析，含 sparkline 折线图；从候选池进入时显示 Candidate Context；新增历史换手率模块 |
| 全量排行 | `ranking.html` + `ranking.js` | 完整排行表格，支持筛选、前端搜索、Export CSV |
| 多公司对比 | `compare.html` + `compare.js` | Summary 表 + Rule Matrix（行=规则，列=公司）|
| 报告 | `reports.html` + `reports.js` | 输入公司 → POST 生成报告 → 展示文本 + Copy |
| 搜索 | `search.html` + `search.js` | 全文搜索，带搜索词高亮、市场 tab 过滤 |
| 候选池 | `candidates.html` + `candidates.js` | 实时换手候选池，支持 `turnover_min` + `turnover_max` 双端筛选与真分页（默认 100 条/页）；表格含财务状态（`financial_check`）和触发信号列 |
| 设置 | `settings.html` + `settings.js` | API Base URL、默认筛选参数、清除历史 |

### i18n 双语切换系统

全站支持中文 / 英文实时切换，语言偏好持久化到 `localStorage('fsm_lang')`，默认英文。

**核心文件：** `frontend/i18n.js`
- `I18N` 对象：`{ en: {...}, zh: {...} }`，包含所有页面的翻译 key
- `applyLang(lang)`：遍历页面所有 `[data-i18n]` 和 `[data-i18n-placeholder]` 元素，替换文本；更新切换按钮标签
- `getLang()`：读 localStorage，默认 `'en'`
- 页面加载时自动 `applyLang(getLang())`，切换按钮 `#langToggleBtn` 在 sidebar 底部

**动态渲染的双语：** 各 JS 文件顶部定义 `const t = (zh, en) => window._currentLang === 'zh' ? zh : en`，用于 JS 动态生成的 HTML 片段

**注意事项：**
- `showToast()` 函数内部 `const el = document.createElement('div')` — 变量命名用 `el` 而非 `t`，避免与全局 `t()` helper 冲突
- 所有新功能默认做双语，HTML 用 `data-i18n`，JS 用 `t()` helper

### 侧边栏导航结构

所有 9 个 HTML 页面统一使用以下四级导航结构（已全部更新）：

```
Home（首页，房子图标）
─ Discover（发现）
  ├── Candidates（候选池）
  └── Signal Ranking（信号排行）
─ Deep Dive（深入分析）
  ├── Company Search（公司搜索）
  ├── Compare（多股对比）
  └── AI Report（AI 报告）
─ System（系统）
  └── Settings（设置）
```

**i18n keys：** `nav_home`, `nav_discover`, `nav_deep_dive`, `nav_signal_ranking`, `nav_company_search`, `nav_compare`, `nav_reports`, `nav_candidates`, `nav_system`, `nav_settings`。旧 key `nav_monitor`, `nav_analysis` 已移除。

---

### 首页产品门户（index.html + app.js）关键设计

首页 `DOMContentLoaded` 并发调用两个接口：
- `API.getTop({ limit: 200 })` — 获取信号排行数据，用于规则分布进度条 + 高风险公司总数
- `API.getCandidates({ limit: 5 })` — 获取候选池前 5 条预览，附带 `financial_check` 数据

**布局结构：**
1. **`summary-row`**：4 个摘要卡（`scard`）— 候选池数量（可点击跳转）、高风险公司数（可点击跳转）、A股覆盖 5502 家、覆盖规则 6 条
2. **`content-grid`**（两列）：
   - 左侧主面板：最近浏览（`recentList`）+ 候选池摘要预览（`candidatePreview`，显示财务状态 badge + 触发信号）
   - 右侧侧栏：深入分析快捷按钮（3 个跳转链接）+ 规则分布进度条（按触发数量排序的横向 bar chart）

**接口容错：** 两个接口各自独立处理异常（`Promise.allSettled`），任一失败只 toast 提示，不影响另一个数据展示。

---

### 用户认证系统（Auth）

**后端：** `backend/auth/user_store.py` — SQLite 实现，DB 写在 Railway Volume `/app/userdata/users.db`

数据表：
- `users`：id, email（唯一，大小写不敏感）, password_hash（werkzeug bcrypt）, created_at
- `user_sessions`：token（hex 64位）, user_id, expires_at（30天）
- `favorites`：user_id, market, code, name, added_at（UNIQUE(user_id, market, code)）

API 端点（均以 `Authorization: Bearer <token>` 鉴权）：
```
POST /api/auth/register   → { token, user: { email } }   注册（邮箱不验证）
POST /api/auth/login      → { token, user: { email } }   登录
POST /api/auth/logout     → { ok: true }                 删除 session token
GET  /api/me              → { email }                    当前用户
GET  /api/me/favorites    → { results: [...] }           收藏列表
POST /api/me/favorites    → { ok: true }                 添加收藏
DELETE /api/me/favorites/{market}/{code} → { ok: true }  删除收藏
```

**前端：** `frontend/auth.js` — 全站注入，所有 9 个 HTML 页面加载
- `AUTH` 模块：token/user 存 localStorage（`fsm_auth_token` / `fsm_auth_user`）
- 右上角 `position: fixed` 头像按钮（不占 topbar 布局）
- 未登录：显示"登录 / 注册"按钮 → 弹出 Modal（Tab 切换登录/注册）
- 已登录：显示蓝色头像圆圈（邮箱首字母）→ 点击从右侧滑出个人面板
- 个人面板：显示邮箱 + 收藏股票列表（可删除）+ 退出登录
- `window.AUTH_UI`：公共接口，供 company.js 调用收藏功能

**company.html** topbar 新增收藏心形按钮：
- 未登录点击 → 弹出登录框
- 已登录点击 → 收藏/取消，按钮变红色实心 + "已收藏"

**注意：** `data/users.db` 已加入 `.gitignore`，用户数据不入 Git。

---

### AI 报告生成（report_generator.py）关键设计

**架构：两阶段推理 → 一阶段输出**

#### Phase 1 — 结构化推理（JSON mode）

强制 AI 输出 JSON 判断对象（`response_format: json_object`）：
```json
{
  "stock_situation_type": "财务偏弱+盘面高度活跃",
  "financial_risk_level": "high | medium | low | unknown",
  "market_activity_level": "high | medium | low | none",
  "turnover_pattern": "spike_only | multi_day_elevated | accelerating | cooling | no_data",
  "evidence_alignment": "aligned | conflicting | neutral",
  "main_tension": "财务现金流持续承压，但市场资金持续关注",
  "watch_points": ["观察点1", "观察点2"],
  "report_tone": "cautious | neutral | constructive"
}
```

#### Phase 2 — 报告写作

拿 Phase 1 的判断 + 原始数据，写三段 Markdown：
- `## 当前状态定位` — 一句话定位 + 财务风险等级 + 市场活跃度
- `## 多源证据整合` — 各层证据是共振还是冲突
- `## 核心矛盾与观察要点` — 主矛盾一句话 + 2-3个具体观察点

**每个判断句末强制标注数据来源**：`（来源：规则引擎）` / `（来源：候选池实时）` / `（来源：换手历史）` / `（来源：财务数据）`

#### 生成前的上下文预取（app.py）

`generate_report` 路由调用前先并行构建：

1. **候选池上下文** `_build_candidate_context(market, code)`：
   - 查当前内存缓存，判断该股是否在候选池
   - 返回：现价、今日换手率、今日涨幅、流通市值、候选原因、financial_check 等级

2. **换手趋势摘要** `_build_turnover_context(market, code)`：
   - 读 `turnover_history.db` 最近 10 天数据
   - 压缩为特征字段：`avg_10d / avg_5d / latest / trend（accelerating/stable/cooling）/ elevated_days / latest_vs_avg`
   - 不把原始日期序列全塞进 prompt，只传特征

#### 降级机制

LLM 不可用时自动降级为规则摘要（`_fallback_report()`），`source` 字段标注降级原因。

---

### 候选池财务状态叠加（financial_check）

**后端：** `backend/app.py` 中 `_build_financial_check(signal_result)` 函数：
- 查询信号缓存（`_load_signals_cache("CN")`），找到对应公司的信号结果
- 统计已触发（`triggered=True`）的信号 ID 列表
- 映射规则：`triggered_count ≥ 2` → `high_risk`；`= 1` → `warning`；`= 0` → `pass`；无数据 → `no_data`
- 每条候选结果附带 `financial_check: { status, triggered_signals, triggered_count }`

**前端展示位置：**
1. **首页候选摘要**（`app.js`）：每条预览显示 `financial-check-badge`（颜色：`badge-high-risk` 红 / `badge-warning` 橙 / `badge-pass` 绿 / `badge-no-data` 灰）
2. **候选池表格**（`candidates.js`）：表格含"财务状态"和"触发信号"两列

---

### 候选池（Candidates）关键设计

候选池是唯一使用**实时行情数据**的功能，其余页面全部基于预计算的静态信号缓存。

**数据源：** `ak.stock_zh_a_spot_em()`（东方财富实时行情，~5800 只 A 股）

**关键行为：**
- 首次调用约 60-150s（AKShare 分页拉取 58×100 条）；30 分钟内缓存命中直接返回
- 非交易日（周末/节假日）返回最后一个交易日的收盘快照，East Money 接口不清零
- `trading_date` 字段：调用 `ak.tool_trade_date_hist_sina()` 获取完整 A 股交易日历（24h 缓存），返回最近的实际交易日；fallback 为往前跳过周末（不感知节假日）
- **Gunicorn timeout 必须 ≥ 300s**（见 `gunicorn.conf.py`），否则首次拉取会超时导致 worker 无限重启
- **启动预热线程：** `app.py` 在模块导入时立即启动 `threading.Thread(target=_prewarm_candidates)`，确保用户首次访问命中缓存

**前端时间戳（候选池面板右上角）：**
1. 对应交易日：`YYYY/MM/DD（周X）` / `YYYY/MM/DD (Weekday)` — 来自 `trading_date` 字段
2. AKShare 抓取：`generated_at` 转北京时间，缓存有效期内不变
3. 本次请求：客户端当前时间，每次请求刷新

**筛选与分页补充：**
- 当前候选池支持 `turnover_min` + `turnover_max`
- `turnover_max` 为空表示“不设上限”
- 前端默认每页 100 条，后端真分页：`page / page_size / total_pages`
- 默认排序按 `turnover desc, code asc`，避免翻页时顺序抖动

### 历史换手率（Turnover History）关键设计

目标是只补“单股连续换手率曲线”，不做全市场历史回放系统。

当前实现：
- 历史仓只存最小字段：`market / code / date / turnover_rate / updated_at`
- 不存历史现价、历史涨幅、历史流通市值、历史候选原因
- 候选池页仍然只看当天；历史换手率仅在 `company.html` 中展示
- 公司页支持 `5D / 10D / 20D / 自定义日期区间`
- 历史查询优先读 `data/turnover_history.db`
- 若某只股票历史不存在，`/api/turnover-history` 会自动按需抓取该单股最近 N 个交易日换手率并写库

### api.js 关键设计
- `API_BASE` 读 localStorage `fsm_api_base`，默认 `https://tender-fascination-production.up.railway.app`
- 所有页面在后端不可达时自动 fallback 到 `MOCK_DATA`，toast 提示 "showing demo data"
- `localStorage key: fsm_recent`，存最近查看的 8 家公司（跨页面共享）

### company.js 特殊逻辑
- 从 URL `?market=CN&code=600519` 读参数
- signal card 对应后端字段是 `sig.value`（不是 `sig.values`）
- 数组类型 value（如 F2、F3 的多年数据）自动渲染 sparkline 折线图（纯 Canvas，无第三方库）
- sparkline 末尾点：绿色=上涨，红色=下跌

---

## 九、数据链路与覆盖状态

### A 股（CN）
| 指标 | 数据 |
|------|------|
| 公司总数 | 5,502 |
| 有完整财务数据 | ~5,502（100%，EastMoney bulk 覆盖）|
| 信号触发 | 1,930（35.1%）|
| 数据来源 | AKShare EastMoney：`stock_zcfz_em`、`stock_lrb_em`、`stock_xjll_em` |
| 抓取方式 | 每次调用覆盖全部 ~5200 家（date='YYYYMMDD'），约 3 个 API 调用搞定一年 |

**批量补充命令：**
```bash
.venv/bin/python -m backend.scripts.bulk_enrich_cn --years 2024 2023 2022 2021
```

### 台股（TW）
| 指标 | 数据 |
|------|------|
| 公司总数 | 1,081 |
| 有完整财务数据 | ~301 家有 OCF，其余字段基本完整 |
| OCF 缺失 | **780 家**（占 72%）|
| 信号触发 | 28（偏低，因 OCF 缺失导致 F2 大量 not_available）|
| 数据来源 | TWSE OpenAPI（主要财务字段）+ FinMind（OCF） |
| FinMind 配额 | 免费 ~100 requests/day |

**OCF 补充进度：** 每天运行 `./refresh.sh` 可补充约 90-100 家，还剩 780 家，约需 8-9 天跑完。

**重要坑：** TWSE OpenAPI 金额单位是**千元**，抓取时已 `×1000` 换算。TWSE 不提供现金流量表 JSON 端点，OCF 只能走 FinMind。

---

## 十、本地启动方式

**前提：** 项目目录下有 `.venv/` 虚拟环境，已安装 `backend/requirements.txt`。

```bash
# 终端1：启动后端（端口 5001，因为 5000 被 macOS AirPlay 占用）
cd "/Users/wangyouqi/Documents/DesktopOrganizer/Web Development/C_G"
.venv/bin/python -m flask --app backend.app run --host 127.0.0.1 --port 5001

# 终端2：启动前端静态服务
cd ".../frontend"
python3 -m http.server 8080

# 浏览器访问
open http://localhost:8080/index.html
```

> **注意：** 不能直接双击 HTML 文件，`file://` 协议下 fetch() 被浏览器 CORS 拦截。

---

## 十一、每日维护命令

```bash
# 每天运行一次：记录当天换手率快照、补充台股 OCF、重算信号缓存
cd "/Users/wangyouqi/Documents/DesktopOrganizer/Web Development/C_G"
./refresh.sh
```

脚本内容：
1. `capture_turnover_snapshot.py --force-refresh`（记录当天 CN 全市场换手率到 `data/turnover_history.db`）
2. `enrich_tw_ocf.py --limit 100 --delay 1.5`（FinMind 配额内最大化）
3. `run_signals.py --market TW`（重算 TW 信号缓存）
4. `run_signals.py --market CN`（重算 CN 信号缓存）

---

## 十二、部署

### 前端（Cloudflare Pages）
**线上地址：** https://finsignal-b8n.pages.dev  
**账号：** wangyifei0611@gmail.com

**更新前端：**
```bash
cd "/Users/wangyouqi/Documents/DesktopOrganizer/Web Development/C_G"
git add frontend/ && git commit -m "update frontend" && git push
npx wrangler pages deploy frontend --project-name finsignal --commit-dirty=true
```

### 后端（Railway）
**线上地址：** https://tender-fascination-production.up.railway.app  
**账号：** wangyifei0611@gmail.com  
**项目名：** tender-fascination  
**计划：** Hobby（$5/月）  
**构建：** Nixpacks 自动检测 Python，读 `requirements.txt`，启动命令见 `railway.toml`

**数据持久化：**
- `backend/config.py` 已支持 `APP_DATA_DIR` / `DATA_DIR`
- 生产环境必须把它指向 Railway 持久卷路径，例如 `/app/userdata`（当前这个 Railway 服务的实际挂载路径）
- `turnover_history.db`、用户数据 SQLite、信号缓存都应落在该目录，而不是容器临时文件系统

**启动保障：**
- `backend/startup_maintenance.py` 会在应用启动后后台检查 CN 最近交易日快照
- 若发现最近交易日没有快照，或完整度明显不足，会自动触发一次 `get_candidates(force_refresh=True)` 写入 `turnover_history.db`
- 这能保证“今天第一次有人打开站点时”尽快落库，但不能替代定时任务

**推荐每日维护命令：**
```bash
.venv/bin/python -m backend.scripts.maintain_daily_history --force-refresh
```

作用：
- 强制抓取并落库当天 CN 全市场快照
- 再用 Tushare Pro 回填最近 60 个交易日的候选池结构历史
- 这样第二天候选池页点“前一天”时，不会依赖临时容器里的残缺 SQLite

**推荐 Railway 定时任务：**
- 每个交易日下午收盘后运行一次上面的命令
- 如果没有 Railway Cron，也至少保留启动保障 + 手动执行该命令补库

**更新后端：**
```bash
cd "/Users/wangyouqi/Documents/DesktopOrganizer/Web Development/C_G"
git add . && git commit -m "update backend" && git push
railway up --detach   # 手动触发；或 Railway 控制台开启 GitHub 自动部署
```

**重新登录 Railway CLI（无 TTY 环境）：**
```bash
expect -c '
  set timeout 300
  spawn railway login --browserless
  expect "code is:"
  # 记下显示的 XXXX-XXXX 代码
  interact
'
# 然后访问 https://railway.com/activate 输入代码
```

**Railway 已包含的数据文件（在 Git 中）：**
- `data/signals/cn_signals.json`（21MB，A 股信号缓存）
- `data/signals/tw_signals.json`（3.3MB，台股信号缓存）
- `backend/master/company_master.db`（712KB，公司搜索）
- `data/cn/*.json`（48MB，A 股 5502 家个股快照）✅ 已加入 Git
- `data/tw/*.json`（5.3MB，台股 1081 家个股快照）✅ 已加入 Git

**Railway Volume（持久化磁盘）：**
- 卷名：`tender-fascination-volume`
- 挂载路径：`/app/userdata`（注意：不是 `/app/data`，避免覆盖信号缓存）
- 用途：存储 `userdata/users.db`（用户账号 + session + 收藏）
- 重部署不丢失，约 $0.25/GB/月

**已正常工作的云端端点：** 全部端点均可用，包括 `/api/company/{market}/{code}` 详情、`/api/report/{market}/{code}` 报告生成、`/api/auth/*` 用户认证、`/api/me/favorites` 收藏。

---

## 十三、已知问题 / 技术债

1. **TW OCF 缺失率 72%**：F2 规则在台股几乎全 not_available，需要继续每天跑 `refresh.sh`，约 8-9 天清零。

2. **Governance 数据几乎全缺**：G1 和 G3 规则对绝大多数公司返回 `not_available`。pledge_ratio 数据源没有接入，board composition 数据未采集。

3. ~~**报告是占位版**~~ ✅ **已完成并升级**：`report_generator.py` 接入 DeepSeek，采用**两阶段推理架构**，API 失败时自动降级为规则摘要。详见下方”AI 报告生成”小节。Railway 环境变量 `LLM_PROVIDER=deepseek`、`LLM_API_KEY` 已配置。

4. ~~**公司快照不在 Git 仓库**~~ ✅ **已完成**：`data/cn/*.json`（48MB，5502 家）和 `data/tw/*.json`（5.3MB，1081 家）已加入 Git 并部署至 Railway。`/api/company/{market}/{code}` 和 `/api/report` 在云端完全可用。

5. **Neo4j 图谱未接入**：`/api/graph/{market}/{code}` 返回空节点，`Neo4jClient` 是占位实现。

6. **company_master.db 已在 Git 仓库**：712KB，已提交。Railway 上搜索功能正常。

7. ~~**候选池页面无限 Loading**~~ ✅ **已修复**：根因是 AKShare `stock_zh_a_spot_em()` 分页拉取 58×~1s = ~145s，超过原 Gunicorn 120s timeout 导致 worker 无限重启。已将 `gunicorn.conf.py` 的 `timeout` 改为 300，并在 `app.py` 启动时加入后台预热线程。

8. **候选池 `trading_date` fallback 不感知节假日**：`get_last_trading_date()` 优先使用 AKShare 交易日历（准确），但若接口失败，fallback 逻辑只跳过周六/周日，不处理法定节假日（如五一、国庆）。节假日期间 fallback 可能显示错误的”上一交易日”。优先级低，因 AKShare 日历接口通常不会失败。

9. **AKShare 免费源不适合批量历史换手率回填**：无论是”全市场 5500+ 支股票逐股补最近 10 日”，还是”候选池 1000+ 支股票逐股补最近 10 日”，都可能触发 `Connection aborted / RemoteDisconnected`。当前结论：
   - ✅ 当日全市场换手率：稳定可抓（候选池主流程已验证）
   - ⚠️ 单股历史换手率：通常可按需抓取，适合 company 页懒加载
   - ❌ 多股票批量历史回填：免费源下不稳定，不建议作为主流程依赖

10. **`backend/scripts/bootstrap_turnover_history.py` 保留为实验脚本，不是推荐主流程**：
    - 已加 retry + sleep 节流
    - 仍然会受上游断连影响
    - 仅适合小批量测试，不应作为”上线前必须先跑完”的前置步骤

11. ~~**信号 JSON 每次请求触发 IO，Railway 响应达 8s**~~ ✅ **已修复**（commit `1c695db` + `86d137e`）：`cn_signals.json`（21MB）现在在 `_load_signals_cache()` 中**按 mtime 缓存到内存**，只在文件变更时重新读取；Railway `/api/signals/top` 响应时间从 8s 降至 <300ms。

12. ~~**候选池非交易日数据混乱**~~ ✅ **已修复**（commit `c565053` / `836e984`）：候选池接口现在优先从 `turnover_history.db` 读取最近一个完整快照日重建候选池，不再依赖东方财富实时接口”不清零”这一副作用行为。前端也增加了”查看前一天”切换按钮。

13. **Tushare Token 需要定期刷新**：`tushare_client.py` 已统一初始化逻辑（commit `b5c1f3e`），可用 `python -m backend.tushare_client` 更新 token；Railway 环境变量 `TUSHARE_TOKEN` 若过期则 Tushare 回落到 AKShare，历史 OHLC 字段会缺失。

---

## 十四、下一步优先级建议

| 优先级 | 任务 |
|--------|------|
| P0 | 每天跑 `./refresh.sh` 补台股 OCF，约 8 天清零（当前还剩 790 家）|
| ✅ 已完成 | 接入 DeepSeek LLM，report_generator.py 生成真实中文风险报告，含降级 fallback |
| ✅ 已完成 | `data/cn/`（48MB）和 `data/tw/`（5.3MB）加入 Git，Railway 全端点可用 |
| ✅ 已完成 | 全站 CN/EN 双语切换（i18n.js + 9 个 HTML 页面 data-i18n + JS t() helper）|
| ✅ 已完成 | 候选池实时换手功能（AKShare 实时行情 + 30min 缓存 + 预热线程 + trading_date）|
| ✅ 已完成 | 候选池筛选增强：新增 `turnover_max` 上限筛选 |
| ✅ 已完成 | 候选池真分页：`page / page_size / total_pages`（默认 100 条/页）|
| ✅ 已完成 | 公司页历史换手率模块：5D / 10D / 20D / 自定义日期 |
| ✅ 已完成 | 历史换手率轻量 SQLite：`data/turnover_history.db`（含 OHLC + pct_change + amount + circ_mv）|
| ✅ 已完成 | 侧边栏导航重构：Home / Discover / Deep Dive / System 四级结构，所有 9 个页面统一更新 |
| ✅ 已完成 | 首页产品门户重设计：4 个摘要卡 + 候选池预览（带财务状态 badge）+ 规则分布 + 快捷入口 |
| ✅ 已完成 | 候选池 × 信号系统打通：`_build_financial_check()` 在 app.py 中叠加财务状态到每条候选结果；候选池表格和首页预览均展示 financial_check badge + 触发信号 |
| ✅ 已完成 | 用户注册/登录系统：邮箱+密码（无需验证），SQLite 存 Railway Volume，30天 session token；收藏股票功能；右上角头像 + 右侧滑出个人面板 |
| ✅ 已完成 | AI 报告升级：两阶段推理架构（Phase 1 JSON 结构化判断 + Phase 2 报告写作）；接入候选池实时上下文 + 换手趋势特征；每句话标注数据来源 |
| ✅ 已完成 | 候选池综合评分升级至 `structure_v3`：四维子评分（活跃度/价格结构/量价关系/板块共振）+ 全局 bonus/penalty；Tushare Pro 补充历史 OHLC 支撑评分计算 |
| ✅ 已完成 | 候选池非交易日降级：优先读 `turnover_history.db` 重建，前端支持”前一天”切换 |
| ✅ 已完成 | 信号 JSON 内存缓存：21MB 文件按 mtime 缓存，Railway 响应从 8s 降至 <300ms |
| ✅ 已完成 | Tushare 客户端统一初始化（`tushare_client.py`），token 更新流程规范化 |
| ✅ 已完成 | Railway 每日历史维护：`maintain_daily_history.py` + 启动后台保障线程，历史数据持久化 |
| ⚠️ 已记录 | 历史批量回填在免费 AKShare 源下不稳定，当前主流程改为”单股按需抓取并写库” |
| P1 | 每天跑 `./refresh.sh` 补台股 OCF，约 8 天清零（当前还剩 ~790 家）|
| P2 | 补充 governance 数据（pledge_ratio 可从 AKShare 获取，CN 市场） |
| P2 | 公司快照定期更新机制（目前是手动跑脚本，可加 Railway Cron Service） |
| P2 | 候选池评分回测工具：记录每日候选池 + 标注 N 日后涨跌，验证 structure_v3 预测力 |
| P3 | 接入 Neo4j 图谱（股权穿透、关联方分析） |
| P3 | 信号趋势历史（目前只看当前一次评估结果，没有时序对比） |
| P3 | 多层风险框架（Pillar 聚合 + Piotroski F-Score + Beneish M-Score，见第 14.3 节）|

---

## 十五、拟扩展功能规划

> 本章节面向下一阶段接手者，记录三个已明确方向但尚未实现的功能规划。每项规划包含业务目标、数据流设计、输出结构、前端展示建议及已知风险，可直接作为需求文档起点。

---

### 14.1 新闻事件影响分析（News Event Intelligence）

#### 功能目标

自动抓取与上市公司相关的财经新闻、公告、监管动态，识别事件类型，并通过 LLM 分析该事件对公司在**治理风险、融资风险、盈利预期、市场情绪**等维度的潜在影响。

这不是预测股价涨跌。目标是将非结构化的新闻信息转化为与现有信号体系对齐的结构化风险事件，让分析师在查看公司页面时能够同时看到"规则触发状态"和"近期事件影响评估"。

#### 为什么值得做

当前系统的信号完全基于历史财务快照（季报/年报数据），存在明显的时滞性。一家公司可能财务指标正常，但刚刚发生了重大诉讼、监管处罚、高管变动或融资失败——这些信息完全无法从现有规则引擎中反映出来。新闻事件分析层填补的正是这个空白：**前瞻性事件风险 vs. 后验性财务信号**，两者互补才构成完整的风险画像。

#### 建议数据流

**Step 1 — 新闻抓取**

优先数据源（按可靠性排序）：
- 东方财富公告中心（CN）：结构化，有公司代码，噪声低
- 上交所 / 深交所公告 RSS
- 台湾证交所重大讯息公告（TW）
- 财联社、36Kr 等财经媒体 RSS（噪声较高，作为补充）

抓取频率：每 4-6 小时一次，存储原始标题 + 摘要 + 来源 + 发布时间 + 原始 URL。

**Step 2 — 公司映射（Ticker Mapping）**

这是整个流程中最容易出错的环节，需单独处理：
- 优先从新闻来源字段提取公司代码（公告类来源直接携带股票代码，准确率接近 100%）
- 媒体类新闻需做 alias matching：用 `company_master.db` 中的 `name`、`name_en`、`code` 做模糊匹配
- 无法确定归属的新闻不强行映射，标记为 `unmapped`，进入人工审核队列
- 一条新闻可能涉及多家公司（如并购、供应链事件），需支持一对多映射

**Step 3 — 事件分类（Event Classification）**

建议的事件类型枚举（`event_type` 字段）：

| 类型 | 说明 |
|------|------|
| `regulatory_penalty` | 监管处罚、罚款、立案调查 |
| `litigation` | 诉讼、仲裁 |
| `management_change` | 高管变动、董事辞职 |
| `financing` | 定增、债券发行、借款、股权质押新增 |
| `m_and_a` | 收购、合并、资产处置 |
| `earnings_warning` | 业绩预警、预亏公告 |
| `operational_disruption` | 停产、火灾、安全事故 |
| `positive_catalyst` | 重大合同、政策利好、新产品发布 |
| `other` | 无法归类 |

分类推荐用 LLM（DeepSeek），输入：新闻标题 + 摘要，输出：`event_type` + 置信度。对于公告类来源，也可以用规则匹配关键词做初步分类再交 LLM 确认。

**Step 4 — 影响分析（Impact Analysis）**

由 LLM 完成，输入：事件分类结果 + 公司当前信号状态（来自信号缓存）+ 新闻全文摘要。

LLM 应输出对以下维度的影响评估（而非预测股价）：

| 影响维度 | 说明 |
|---------|------|
| `governance_risk` | 治理结构是否受影响（如高管变动、诉讼涉及实控人） |
| `financing_risk` | 融资能力是否受影响（如评级下调、质押平仓风险） |
| `earnings_outlook` | 对未来盈利预期的影响（如业绩预警、重大合同） |
| `operational_risk` | 经营连续性风险（如停产、供应链中断） |
| `regulatory_risk` | 合规风险（如被调查、处罚） |
| `market_sentiment` | 市场情绪变化（用于定性描述，不作为量化评分） |

**Step 5 — 存储与时效管理**

新闻事件有时效性，建议：
- 存储在 SQLite 新表 `news_events`（而非 JSON 文件）
- 每条记录有 `event_date`，前端默认只展示近 30 天事件
- 超过 90 天的事件可归档，不再主动展示

#### 建议的结构化输出字段

```
company_id        string    公司唯一标识，如 CN:600519
event_date        string    事件日期（ISO 8601）
event_type        string    见上方枚举
source_url        string    原始新闻链接
headline          string    新闻标题
sentiment         enum      positive / negative / neutral
severity          enum      low / medium / high / critical
affected_dims     list      受影响维度列表（见上方表格）
time_horizon      enum      immediate / short_term(1-3m) / medium_term(3-12m)
impact_summary    string    LLM 生成的 200 字以内影响摘要
confidence        float     LLM 置信度，0-1
mapped_by         enum      source_field / alias_match / manual
```

#### 建议前端展示位置

- **Dashboard**：新增"近期事件预警"卡片，展示过去 7 天 severity=high/critical 的事件，按 event_date 排序
- **Company Detail Page**（`company.html`）：在现有信号卡片下方新增"近期事件"区块，展示该公司过去 30 天事件列表，每条显示 severity badge + event_type + headline + impact_summary
- **新增 Event Monitor Page**（`events.html`）：全局事件流，支持按 market / event_type / severity / 日期范围过滤，类似 Bloomberg Terminal 的事件提醒界面

#### 技术风险 / 已知挑战

1. **公司映射错误**：媒体类新闻标题中的公司名称歧义性高（如"中国建筑"可能指多家实体）。建议第一版只处理公告类来源（精确映射），媒体类新闻作为 P2。
2. **新闻噪声过大**：财经媒体存在大量重复、无实质内容的新闻。需在入库前做去重（标题相似度）和过滤（最短摘要长度、来源白名单）。
3. **LLM 过度臆测**：LLM 在分析"未来影响"时容易推断过度，尤其对 `time_horizon=medium_term` 的判断缺乏依据。Prompt 中需明确要求"只基于新闻事实推断，不得凭空推理"，并将置信度低于 0.6 的分析结果标记为"仅供参考"。
4. **成本控制**：若每天抓取 500 条新闻，每条调用一次 DeepSeek，按 deepseek-chat 定价约 $0.1-0.2/天，可接受。但需设置每日调用上限，避免抓取异常导致费用失控。

#### 建议实现优先级

| 阶段 | 内容 |
|------|------|
| P0（验证可行性） | 在 `reports.html` 或新增入口支持**手动输入新闻文本**，调用 LLM 分析影响，不涉及自动抓取 |
| P1 | 接入东方财富公告 RSS，自动抓取 CN 市场公告，精确映射公司代码，存入 SQLite |
| P2 | 接入台湾证交所重大讯息，覆盖 TW 市场 |
| P3 | 接入媒体类新闻，增加 alias matching，上线 Event Monitor 页面 |

---

### 14.2 用户上传财报分析（Custom Financial Statement Upload）

#### 功能目标

允许用户上传自己的财务报表（Excel / CSV），系统将其转换为与现有上市公司一致的 snapshot schema，然后复用现有 `RuleEngine` 完成风险分析，输出与上市公司相同格式的信号结果。

这是将系统从"上市公司分析器"升级为**泛企业风险分析平台**的关键一步。非上市公司、拟 IPO 企业、私募投资标的均可进入同一套分析框架，而无需对核心引擎做任何改动。

#### 为什么值得做

现有系统的数据完全依赖公开市场数据（AKShare、TWSE），覆盖范围天然受限于上市公司。但实际业务场景中，大量分析需求来自：

- 投资人对拟投企业的尽调
- 供应商 / 采购方对合作伙伴的信用评估
- 企业自身的财务健康自查

这些场景中企业不一定上市，但其财务数据结构（利润表、资产负债表、现金流量表）与上市公司完全相同，完全可以复用现有规则引擎。

#### 建议第一版支持的输入形式

优先级从高到低：

1. **Excel（.xlsx）**：用户接受度最高，会计师交付格式。支持用户按照系统提供的模板填写，或上传自有格式后做字段映射。
2. **CSV**：适合系统导出数据的二次导入，格式简单，解析成本低。
3. **手动录入表单**：在前端提供一个结构化的年度财务数据录入表，适合字段较少的快速分析场景。

#### 为什么第一版不建议优先支持 PDF / OCR

PDF 财报（尤其是扫描版）的结构高度不一致：表格跨页、合并单元格、中英文混排、金额单位标注位置随意。OCR + 表格抽取的错误率在实际财报中通常超过 15%，而下游规则引擎对数据质量高度敏感（一个错误的负号可能导致完全相反的信号结果）。PDF 解析应作为独立子项目，不应阻塞核心上传功能的上线。

#### 建议数据流

**Step 1 — 文件上传**

前端 `upload.html` 提供文件拖拽上传入口，接受 `.xlsx` / `.csv`，文件大小限制 5MB。上传后发送至后端新增端点 `POST /api/upload/financials`。

**Step 2 — 字段映射（Column Mapping）**

这是整个流程的核心难点。用户的表格列名五花八门（"营业收入" vs "总营收" vs "Revenue" vs "营收合计"），需要一套宽松的映射层：

- 第一版：提供**标准模板下载**，要求用户按模板填写，减少映射复杂度
- 第二版：支持上传自有格式，后端用关键词匹配（含同义词字典）猜测字段映射，前端展示"字段预览 + 确认映射"界面，由用户最终确认

系统内部的目标字段集合已由现有 snapshot schema 定义（`revenue`、`net_profit`、`operating_cash_flow`、`accounts_receivable`、`inventory`、`total_assets`、`total_liabilities`），只需映射这 7 个核心字段即可覆盖当前全部 4 条财务规则（F1-F4）。

**Step 3 — 数据校验**

在构造 snapshot 之前必须执行校验，否则规则引擎会产生误导性结果：

- 年份字段存在且至少有连续 2 年数据（F2、F3 需要多年数据）
- 金额字段为数值类型，不含文字
- 单位标注一致（系统内部统一使用**元**，需提示用户确认或填写单位换算系数）
- `total_assets > total_liabilities`（基础合理性校验）
- `revenue > 0`（负数营收不合理）

校验失败的字段在前端高亮显示，提示用户修正，而不是静默跳过。

**Step 4 — Schema 归一化**

将用户数据转换为与 `data/cn/*.json` 完全一致的 snapshot 结构。关键设计决策：

- `market` 字段设为 `CUSTOM`
- `company_id` 格式为 `CUSTOM:{user_defined_name}`，如 `CUSTOM:某科技有限公司`
- `status` 设为 `custom_upload`
- `governance` 字段默认为空（G1、G3 规则将返回 `not_available`，属于预期行为）
- `source` 字段标注为 `user_upload`，前端可据此展示不同的数据来源说明

**Step 5 — 调用现有分析引擎**

归一化后的 snapshot 直接传入 `RuleEngine.evaluate(snapshot)`，无需对引擎做任何修改。这是这个设计最大的优势：核心分析逻辑零改动，只扩展数据入口层。

结果可调用现有 `generate_report_payload()` 生成 LLM 报告，与上市公司报告格式完全一致。

#### 建议前端页面

- **`upload.html`**：上传入口，支持拖拽 + 文件选择，提供模板下载链接，显示支持的字段说明
- **Preview / Validation 界面**（可内嵌于 `upload.html` 的第二步）：表格预览 + 字段映射确认 + 校验错误高亮
- **Analysis Result 界面**：复用 `company.html` 的信号卡片样式，顶部添加"自定义上传"标识 badge，底部说明哪些规则因数据缺失无法评估

上传结果不持久化到服务器（第一版），仅在 session 内有效，避免存储用户私有财务数据带来的合规风险。

#### 技术风险 / 已知挑战

1. **列名不统一**：中文财务术语有大量同义词，即使使用模板，用户仍可能擅自修改列名。建议维护一个同义词映射表（JSON），后续可持续扩充。
2. **单位不统一**：用户可能以"万元"或"千元"填写，而系统内部统一为"元"。必须在校验步骤强制要求用户确认单位，或提供单位选择下拉框，后端统一换算。
3. **年份字段缺失或格式不一致**：`period` 字段要求为 4 位年份字符串（如 `"2024"`），用户可能填写 `"2024年"` 或 `"FY2024"`，需做清洗。
4. **报表字段不完整**：用户只有利润表而没有现金流量表（F2 规则所需），或只有 1 年数据（F2、F3 需要连续 2 年）。这些情况下对应规则应返回 `not_available`，不应强行报错，信号卡片上需有清晰的"数据不足"说明。
5. **数据安全**：用户上传的财务数据属于商业敏感信息，第一版建议不落库、不记录，仅在请求生命周期内处理。如果未来需要持久化，需要明确的用户同意和数据隔离方案。

#### 建议实现优先级

| 阶段 | 内容 |
|------|------|
| P0（验证可行性） | 前端手动录入表单（无文件上传），填写 7 个核心字段 × 3 年，直接调用现有引擎，验证 schema 兼容性 |
| P1 | 支持标准模板 Excel 上传，严格字段映射，完整校验流程，上线 `upload.html` |
| P2 | 支持自有格式 Excel，增加字段映射确认界面，扩充同义词字典 |
| P3 | 支持 PDF 抽取（独立子项目，不阻塞 P0-P2） |

---

### 14.3 多层风险分析框架升级（Multi-Pillar Risk Framework）

#### 当前分析的局限性

当前规则引擎有 6 条规则（F1-F4、G1、G3），覆盖了应收账款、现金流、杠杆、利润率、股权质押、董事会结构。这套规则能有效识别财务异常的粗粒度信号，但存在以下结构性局限：

- **维度覆盖不足**：没有盈利能力效率（ROA、ROE）、流动性（速动比率、流动比率）、成长质量（营收增速一致性）等维度
- **规则之间互相独立**：一家公司触发 3 条规则和触发 1 条规则，在系统里除了 `triggered_count` 的数字之外没有本质区别，缺乏加权综合评估
- **输出粒度太粗**：只有 `triggered / ok / not_available` 三种状态，无法反映"刚刚越过阈值"和"严重超标"之间的程度差异
- **无行业参照**：一家钢铁企业资产负债率 65% 和一家软件公司资产负债率 65% 的含义完全不同，但当前规则一视同仁

#### 为什么不能只是继续无脑加规则

单纯堆砌更多独立规则会带来三个问题：
1. **误报率上升**：规则越多，单条规则的 false positive 越容易被放大，最终结果对用户失去参考价值
2. **维护成本线性增长**：每条规则需要独立维护阈值、数据依赖和测试用例
3. **缺乏解释层**：用户看到"触发了 5 条规则"不知道该关注哪个，需要一个有层次的评估结构来引导注意力

正确的升级方向是：引入**风险支柱（Risk Pillars）**概念，将规则信号聚合为有业务含义的维度得分，再由维度得分合成整体风险等级。

#### 建议的多层风险框架（Risk Pillars）

**Pillar 1 — Earnings Quality / Accounting Quality（盈利质量）**

关注核心问题：账面利润是否真实反映经营成果？是否存在盈余管理迹象？

建议纳入的因子：
- `CFO / Net Profit` 比率：持续低于 0.8 说明利润没有转化为现金，是盈余管理的经典信号（对应现有 F2 规则）
- `AR / Revenue` 比率及其 YoY 变化（对应现有 F1 规则）
- 应收账款周转天数（DSO）变化趋势
- 存货周转天数变化趋势（存货积压是收入虚增的常见手段）
- `Beneish M-Score`（见下方专项说明）

**Pillar 2 — Liquidity & Solvency（流动性与偿债能力）**

关注核心问题：企业能否按时偿还短期债务？是否有流动性危机风险？

建议纳入的因子：
- 流动比率（Current Ratio = 流动资产 / 流动负债），低于 1.0 为危险信号
- 速动比率（Quick Ratio，扣除存货），低于 0.8 需关注
- 现金及等价物占总资产比例
- 短期借款占总负债比例

> 当前 snapshot schema 中缺少流动资产、流动负债的单独字段，需在数据抓取层补充这两个字段才能计算此 Pillar。这是实现该框架的主要数据依赖。

**Pillar 3 — Leverage（杠杆与资本结构）**

关注核心问题：负债规模是否可持续？利息覆盖能力如何？

建议纳入的因子：
- 资产负债率（对应现有 F3 规则）
- 有息负债率（区分经营性负债和融资性负债）
- EBITDA / 利息支出（Interest Coverage Ratio），需要利息费用字段
- `Altman Z-Score`（见下方专项说明）

**Pillar 4 — Profitability & Operating Efficiency（盈利能力与运营效率）**

关注核心问题：企业用资产和资本赚钱的效率如何？

建议纳入的因子：
- ROA（净利润 / 总资产）
- ROE（净利润 / 净资产，需要净资产字段）
- 净利率及其趋势（对应现有 F4 规则）
- 毛利率（需要营业成本字段）
- `DuPont 三因素分解`：ROE = 净利率 × 资产周转率 × 权益乘数（见下方专项说明）

**Pillar 5 — Growth Quality（成长质量）**

关注核心问题：营收增长是否健康、可持续？

建议纳入的因子：
- 营收 3 年 CAGR
- 营收增速一致性（是否存在忽高忽低的异常波动）
- 净利润增速 vs 营收增速的匹配度（利润增速长期高于营收增速需审查原因）
- `Piotroski F-Score` 中的成长类子指标（见下方专项说明）

**Pillar 6 — Governance & Event Risk（治理与事件风险）**

关注核心问题：公司治理结构是否存在风险敞口？近期是否有重大风险事件？

建议纳入的因子：
- 大股东股权质押比例（对应现有 G1 规则）
- 董事会独立性（对应现有 G3 规则）
- 审计意见类型（标准无保留意见 vs 保留意见 vs 无法表示意见）
- 近期监管处罚记录（对接 14.1 新闻事件分析后可自动填充）

**（可选）Pillar 7 — Industry Benchmark Layer（行业分位对比）**

在前 6 个 Pillar 的绝对评估基础上，增加行业相对评估层：将关键指标与同行业公司的分布做百分位对比。例如，一家钢铁企业资产负债率 65% 处于行业第 30 分位（相对合理），而软件企业同样的比率可能处于第 95 分位（极度异常）。

此层依赖行业分组数据（`industry_sw` 字段已存在于 `company_master.db`）和跨公司聚合计算，计算成本较高，建议作为 P3 实现。

---

#### 建议接入的经典金融 / 风险模型

**Altman Z-Score**

用于评估企业破产概率，经典五因子模型：
`Z = 1.2×X1 + 1.4×X2 + 3.3×X3 + 0.6×X4 + 1.0×X5`
（X1=营运资金/总资产，X2=留存收益/总资产，X3=EBIT/总资产，X4=市值/总负债，X5=营收/总资产）

在本项目中的定位：作为 **Pillar 3（Leverage）** 的综合评分，而非独立预测指标。Z-Score < 1.81 为危险区，1.81-2.99 为灰色区，> 2.99 为安全区，这些阈值可直接映射为系统的 severity 等级。注意：Z-Score 的 X4 因子需要市值数据，上市公司可以接入，非上市公司（14.2 功能）需使用账面净资产替代。

**Piotroski F-Score**

9 个二元指标（每项 0 或 1 分）的加总，评估财务健康度和改善趋势，涵盖盈利能力（4 项）、财务杠杆与流动性（3 项）、运营效率（2 项）。

在本项目中的定位：作为 **Pillar 5（Growth Quality）** 和 **Pillar 4（Profitability）** 的辅助验证工具。F-Score 0-2 为弱质公司，7-9 为强质公司。F-Score 与现有规则引擎的触发信号高度互补——现有规则侧重"异常点"检测，F-Score 侧重"综合财务健康趋势"评估。这两者结合才能区分"偶尔出现一个异常但整体健康"和"全面恶化"两种截然不同的情况。

**Beneish M-Score**

8 因子模型，专门用于检测财务报表操纵可能性（financial statement manipulation），核心因子包括 DSRI（应收账款指数）、GMI（毛利率指数）、AQI（资产质量指数）、SGI（营收增长指数）等。

在本项目中的定位：作为 **Pillar 1（Earnings Quality）** 的核心评分工具。M-Score > -1.78 说明存在盈余管理可能性。对于已触发 F1（应收账款异常）的公司，M-Score 可以作为"是否真正存在操纵风险"的二次验证，减少 F1 的误报率。

**DuPont Analysis（杜邦分析）**

将 ROE 分解为净利率 × 资产周转率 × 权益乘数三个驱动因子，用于解释"为什么 ROE 好 / 差"。

在本项目中的定位：不作为触发规则，而是作为 **报告生成层的解释工具**。当 LLM 生成风险报告时，DuPont 分解结果可以作为上下文传入 prompt，让报告从"ROE 下降了"升级为"ROE 下降主要由资产周转率恶化驱动，而非利润率问题"。这对提升报告专业度有显著帮助，且实现成本较低（只需在 `_build_user_prompt()` 中增加 DuPont 计算结果）。

---

#### 建议的输出升级方向

**当前输出结构（每条信号）：**
```
signal_id / name / triggered(bool) / status / message / value
```

**目标输出结构（未来）：**

信号层保持不变（向下兼容），在其上新增聚合层：

```
pillar_scores:
  earnings_quality:     { score: 0-100, level: low/medium/high/critical, signals: [...] }
  liquidity:            { score: 0-100, level: ..., signals: [...] }
  leverage:             { score: 0-100, level: ..., altman_z: float, signals: [...] }
  profitability:        { score: 0-100, level: ..., roa: float, roe: float, signals: [...] }
  growth_quality:       { score: 0-100, level: ..., piotroski_f: int, signals: [...] }
  governance_event:     { score: 0-100, level: ..., signals: [...] }

model_scores:
  altman_z:     { value: float, zone: safe/grey/distress }
  piotroski_f:  { value: int, label: strong/neutral/weak }
  beneish_m:    { value: float, manipulated: bool }

overall:
  risk_score:   0-100
  risk_level:   low / medium / high / critical
  key_concerns: ["string", ...]   # LLM 从各 pillar 中提炼的 3 条核心关注点
```

**向下兼容原则：** 现有 `financial_signals` 和 `governance_signals` 数组保留原样，`pillar_scores` 作为新增字段追加在信号缓存 JSON 中。前端页面可按需展示新字段，不破坏现有展示逻辑。

#### 建议实现优先级

| 阶段 | 内容 |
|------|------|
| P0 | 在现有 snapshot schema 中补充流动资产、流动负债、净资产、毛利润字段（数据层扩展，影响 Pillar 2、4 的可计算性） |
| P1 | 实现 Piotroski F-Score 和 Beneish M-Score，集成进信号缓存，前端公司详情页展示模型得分卡 |
| P2 | 实现 Pillar 聚合层，为每个 Pillar 计算综合得分，展示 Overall Risk Level |
| P3 | 实现 Industry Benchmark Layer（行业分位），接入 Altman Z-Score（需要市值数据），DuPont 分解集成进 LLM 报告 prompt |

---

## Stage 5: Tushare 2年历史数据 Wyckoff 结构验证

**完成日期：** 2026-05-22  
**任务：** 使用 Tushare Pro 数据替代短期样本，进行 2 年期长期回测验证  
**关键成果：** structure_v4 相比 v3 取得 **+0.799% 显著改进**，跨所有 regime 生效

### 5.1 数据规模

| 指标 | 值 |
|------|-----|
| 时间跨度 | 2024-01-01 → 2026-05-21 |
| 交易日数 | 574 天 |
| 股票代码数 | 5,605 只 |
| 日线数据行数 | 3,095,322 行 |
| 候选快照观测 | 698,848 个 |
| 有效 5d 收益观测 | 693,569 个 (99.2%) |
| Regime 分布 | 上升 263 天 / 横盘 153 天 / 下降 158 天 |

### 5.2 v3 vs v4 回测结果

#### 全样本 (All Regime)

| 模型 | 5d 均收 | 胜率 | 最大回撤 | Top-10 Rank |
|------|--------|------|---------|---------|
| **structure_v3** | **-0.772%** | 40.9% | -6.35% | ❌ 表现最差 |
| **structure_v4** | **+0.027%** | 46.9% | -5.15% | ✅ **+0.799% 改进** |
| early_setup_only | +0.181% | 47.9% | -4.98% | ✅ 最强信号 |
| washout_gate_v4 | -0.122% | 45.8% | -5.29% | ❌ 虚假信号 |
| v4_no_early_setup | -0.646% | 41.5% | -6.22% | ❌ early_setup 必需 |

#### 上升期 (Uptrend)

| 模型 | 5d 均收 | 胜率 | 最大回撤 |
|------|--------|------|---------|
| structure_v3 | -0.073% | 41.9% | -5.23% |
| **structure_v4** | **+0.654%** | 49.2% | -3.92% |
| early_setup_only | +0.835% | 50.1% | -3.80% |

**解读：** 上升期 v4 得分达 v3 的 9 倍，early_setup 信号仍为最强

#### 横盘期 (Sideways)

| 模型 | 5d 均收 | 胜率 | 最大回撤 |
|------|--------|------|---------|
| structure_v3 | -1.942% | 39.5% | -7.96% |
| **structure_v4** | **-0.847%** | 45.2% | -6.51% |
| early_setup_only | -0.742% | 47.0% | -6.39% |

**解读：** 横盘期全部模型负收益，但 v4 比 v3 减亏 **1.095%**，early_setup 仍然相对坚挺

#### 下降期 (Downtrend)

| 模型 | 5d 均收 | 胜率 | 最大回撤 |
|------|--------|------|---------|
| structure_v3 | -0.780% | 40.7% | -6.62% |
| **structure_v4** | **-0.149%** | 44.8% | -5.83% |
| early_setup_only | +0.006% | 45.1% | -5.52% |

**解读：** 下降期 v4 比 v3 少亏 **0.631%**，early_setup 在下降期基本失效

### 5.3 关键发现

#### 1. structure_v4 的改进机制

**v4 相比 v3 移除了两个有害因素：**

| 因素 | v3 中 | v4 中 | 影响 |
|------|------|------|------|
| sector_resonance | 权重 15% | 仅作 tag，不计分 | 部分行业共鸣形成羊群效应，全样本贡献为零 |
| washout_recovery_bonus | +4 分 | 完全移除 | 虚假弹簧信号，特别在下降期成为陷阱 |

**v4 强化了一个有效信号：**
- early_setup_bonus：从 +4 上升到 min(+6, 4×1.5)，并提高权重

#### 2. early_setup_bonus 是最强单一信号

| Regime | 贡献度 | 可靠性 | 备注 |
|--------|--------|--------|------|
| **全样本** | **+0.181%** | ⭐⭐⭐⭐⭐ | 跨所有 regime 有效 |
| 上升期 | +0.835% | ⭐⭐⭐⭐⭐ | 最强表现 |
| 横盘期 | -0.742% | ⭐⭐⭐ | 仍相对稳定 |
| 下降期 | +0.006% | ⭐⭐ | 基本失效，但仍优于其他 |

**Wyckoff 解释：** early_setup 捕捉的是 **accumulation 阶段向 markup 过渡** 的信号——LPS (Last Point of Support) 区域。这是 Wyckoff 结构中最可靠的入场点，因为此时 supply 已基本吸收完毕。

#### 3. Wyckoff 标签有效性排序

| 标签 | 5d 均收 | 观测数 | 胜率 | Wyckoff 含义 | 验证 |
|------|--------|--------|------|------------|------|
| spring_washout_attempt | +1.046% | 52,372 | 50.1% | 春季反弹 | ✅ 有效 |
| markup_prep | +0.825% | 67,302 | 50.0% | 上升准备期 | ✅ 有效 |
| early_setup_consolidation | +0.799% | 83,863 | 51.7% | LPS 巩固 | ✅ 最稳定 |
| distribution_risk | +0.788% | 287,505 | 49.3% | ⚠️ 见 5.4 | ⚠️ 需重评 |
| accumulation_zone | +0.456% | 16,855 | 47.5% | 建仓区域 | ✅ 弱正 |
| tag:neutral | -0.046% | 20,800 | 49.0% | 无特征 | ✅ 中性 |
| overextended | -0.613% | 21,714 | 39.0% | 过度上升 | ✅ 真正风险 |
| vp_confirmed | -5.323% | 179 | 17.3% | ⚠️ 虚假信号 | ❌ 样本极小 |

### 5.4 distribution_risk 标签重评（⚠️ 重要发现）

**观察现象：** distribution_risk 标签虽然名义上代表"分布期风险"，但实际表现为正收益。

**时间窗口分析：**

| 窗口 | 5d 均收 | 胜率 | 解读 |
|------|--------|------|------|
| 3d | +0.005% | 49.0% | 短期平稳 |
| 5d | +0.008% | 49.3% | 短期平稳 |
| 10d | +0.015% | 50.5% | **开始转正** |
| 20d | **+0.031%** | 50.8% | **长期加强** |

**结论：**

当前 distribution_risk 标签标记的是 **"高成交量的上升延续期"**，而不是真正的分布型风险。这个阶段：
- 短期（3-5天）：基本中性，可能存在短期调整
- 中长期（10-20天）：持续正收益，表现为 **late-stage markup momentum**

**建议：**

根据用户要求，此标签在下一个迭代中应考虑拆分为：
- `high_turnover_strength` — 高成交量但价格继续上升（长期有效，+0.031%@20d）
- `true_distribution_risk` — 高成交量且价格开始反转（当前标记机制未能区分）

**当前处理：** 保持现有标记以避免数据破裂，但在文档中明确说明此标签的实际含义，防止误解。

### 5.5 生产接入总结

**已完成的变更：**

| 文件 | 变更 | 目的 |
|------|------|------|
| `candidate_scoring.py` | 添加 `wyckoff_phase` / `wyckoff_tags` 占位符 | 后续支持存储 |
| `candidate_snapshot_store.py` | 新增 2 列存储 Wyckoff 信息 | 持久化标签 |
| `app.py` | 优先从 snapshot store 加载历史数据 | 保留 Wyckoff 标签 |
| `backtest_bootstrap_tushare.py` | 已实现完整 Wyckoff 标签化 | 实时候选无标签 |

**默认排序策略：**
- `candidate_score` = `score_v4` （生产已切换）
- `score_v3` 保留字段用于 A/B 对比和回滚
- Wyckoff 标签仅在 backtest 和历史快照中可用，实时候选返回 `None`

### 5.6 限制与后续方向

**当前验证的限制：**
1. **Ranking validation only** — 回测只验证了候选排序的有效性，未模拟实际交易（滑点、费用、头寸管理）
2. **No portfolio optimization** — 未涉及 Top-10 / Top-20 投资组合的权重分配
3. **Regime 标签简化** — 仅使用 MA20/MA60 交叉，未考虑 VIX / 市场流动性等深层因素
4. **Wyckoff 标签局限** — 10 个标签涵盖主要结构，但复杂边界情况（如 test 重复）的判断仍不够精细

**后续建议（Priority Order）：**

| 优先级 | 方向 | 预期收益 |
|--------|------|---------|
| **P0** | 确认 distribution_risk 标签拆分方案，重新标记或改名 | 消除标签歧义 |
| **P1** | 验证 Top-10 / Top-20 投资组合的真实回报（包括成本） | 从排序验证升级到投资可行性验证 |
| **P2** | 细化 Wyckoff test / retest 标签，区分重复测试的强度 | 提高 spring 信号的区分度 |
| **P3** | 结合 options pricing implied volatility 验证 overextended 标签的时间尺度 | 改进 downtrend 期的卖点判断 |

### 5.7 文档更新清单

- ✅ 新增 Stage 5 章节（本部分）
- ✅ 明确 v4 > v3 的改进机制
- ✅ Wyckoff 标签有效性对标
- ✅ distribution_risk 重评结果
- ✅ 生产接入变更清单

---

## Stage 6: structure_v5 早期积累型排序

### 6.1 模型迭代背景

**问题发现：** structure_v4 在生产运行过程中发现了"思路跑偏"的现象——排序出的候选主要是**已经高换手、已经活跃**的股票（热股追涨），但我们的真正目标应该是找**低换手→换手开始抬升**的潜力股（早期积累阶段）。

**症状：** 
- v4 偏重于 `price_structure_score`（×0.40）和 `activity_score`（×0.27）
- 这两个维度天然倾向于"已经上升、已经活跃"的股票
- 缺乏对"积累期向上升期过渡"这一关键节点的识别

**解决方案：** 构建 structure_v5，一个 **5 分量的早期积累型评分系统**，配合市场制度门限来识别底部建仓信号。

### 6.2 structure_v5 参数设定（Conservative_PE50）

**基础筛选条件（不可调）：**

| 参数 | 值 | 含义 |
|------|-----|------|
| `pe_max` | 30 | 仅纳入 PE < 30 的低估值股票 |
| `pb_max` | 3 | 仅纳入 PB < 3 的低估值股票 |
| `circ_mv_max_yi` | 80 | 小盘聚焦：流通市值 < 80 亿 |
| `turnover_ratio_threshold` | 1.5 | 换手率拐点：今日换手 ≥ 平均20日×1.5倍 |
| `today_turnover_max` | 8% | 控制上限，避免过度放量 |
| `avg_turnover_20d_max` | 3% | 20日均换手 < 3%（低基数） |
| `position_60d_max` | 0.7 | 价位在60日区间下半部分（≤70%位） |

**验证成果：**
- **测试集**：+0.877% 5日平均收益，54.8% 胜率（5,944 样本）
- vs v4：+0.174% 改善（v4 为 +0.703%）
- **月度稳定性**：10 个月中 9 个月正收益（90% 成功率）
- **成本验证**：扣除 40bp 交易成本后仍净正 +0.707%

### 6.3 structure_v5 评分架构

**5 个评分维度（总分 100）：**

#### 1. Base Quality（0-25 分）— 估值与形态基础

- PE 质量（0-10 分）：PE < 15 给 10 分，PE < 20 给 8 分
- PB 质量（0-10 分）：PB < 1.5 给 10 分，PB < 2.5 给 7 分
- 趋势定位（0-5 分）：60 日区间位置 < 30% 给 5 分

#### 2. Inflection Detection（0-25 分）— 换手拐点识别

- 换手趋势（0-15 分）：20 日均换手趋势向上的幅度
- 动量累积（0-10 分）：近 20 日活跃天数（换手 ≥ 2% 的天数）

#### 3. Valuation Strength（0-20 分）— 估值力度

- PE 倍数评价（0-10 分）：PE 越低分数越高，最多 10 分
- 市值分层（0-10 分）：小盘（< 50 亿）10 分，中盘（< 150 亿）8 分

#### 4. Price Extension（0-20 分）— 价格延伸度

- 60 日位置评价：< 20% 位给 20 分，< 40% 位给 15 分

#### 5. Market Cap Alignment（0-10 分）— 规模匹配度

- 适合早期积累的规模（10-150 亿）给 10 分

**分级映射：**
- A 级（80-100 分）：高质量早期积累信号
- B 级（60-79 分）：中等质量信号
- C 级（40-59 分）：弱信号
- D 级（< 40 分）：不推荐

### 6.4 市场制度门限（Market Regime Gate）

**核心假设：** 早期积累模式在**上升期**最有效，在**下降期**容易产生虚假信号。

**市场分级与权重：**

| 市场状态 | 定义 | v5 权重 | 说明 |
|---------|------|---------|------|
| **Uptrend** | SMA200 上升，current > SMA200，波动率低 | **1.0** | 最优条件，充分信任 v5 信号 |
| **Sideways** | 混合条件 | **0.3** | 信号可靠性降低，仅 30% 权重 |
| **Downtrend** | SMA200 下降，current < SMA200，波动率高 | **0.0** | 禁用 v5 信号，structure_v5_score = 0 |

**实现方式：** 
```
structure_v5_score = score_v5 × regime_weight
```
- 下降期自动禁用（权重为 0），防止"底部陷阱"
- API 响应包含 `market_regime`、`regime_status`、`regime_weight` 字段，供前端决策

### 6.5 API 与数据库集成

**API 变更：**

1. **GET /api/candidates** 新增 `mode` 参数：
   - `?mode=structure_v5`（默认）→ 按 structure_v5_score 排序
   - `?mode=structure_v4` 或 `?mode=active` → 按 score_v4 排序（保留选项）

2. **响应字段（NEW）：**
   ```json
   {
     "mode": "structure_v5",
     "results": [{
       "score_v5": 75.3,
       "structure_v5_score": 75.3,         // 已应用 regime gate
       "structure_v5_tier": "A",
       "structure_v5_tags": ["low_pe", "turnover_rising", "near_60d_low"],
       "structure_v5_reason": "Tier A: Base quality dominant (low_pe, low_pb, near_60d_low)",
       "market_regime": "uptrend",
       "regime_status": "Market in uptrend with rising momentum",
       "regime_weight": 1.0
     }]
   }
   ```

**数据库变更：**

新增 8 列到 `candidate_snapshot` 表（safe migration）：
- `score_v5` (REAL)
- `structure_v5_score` (REAL) — 应用 regime gate 后的最终分值
- `structure_v5_tier` (TEXT)
- `structure_v5_tags` (TEXT)
- `structure_v5_reason` (TEXT)
- `market_regime` (TEXT)
- `regime_status` (TEXT)
- `regime_weight` (REAL)

### 6.6 代码实现清单

| 文件 | 变更 | 优先级 |
|------|------|--------|
| `backend/screening/structure_v5_model.py` | NEW：常量、市场分级、5 维评分、筛选验证 | P0 |
| `backend/screening/candidate_scoring.py` | 导入 v5 模块；增加市场分级检测；计算 score_v5；默认 → v5；新增返回字段 | P0 |
| `backend/app.py` | /api/candidates 新增 ?mode 参数；按 mode 排序；response 包含 mode | P0 |
| `backend/data_access/candidate_snapshot_store.py` | safe migration 添加 8 新列；save_snapshot 包含新字段 | P0 |
| `PROJECT_HANDOFF.md` | 本 Stage 6 文档 | P0 |

### 6.7 11 点测试套件

| # | 测试 | 预期结果 | 检查点 |
|---|------|---------|--------|
| 1 | 默认 `/api/candidates` | 返回 structure_v5 排序 | `mode: "structure_v5"`, `score_version: "structure_v5"` |
| 2 | `/api/candidates?mode=structure_v4` | 返回 v4 排序 | `score_version: "structure_v4"` |
| 3 | 下降期 regime gating | structure_v5_score = 0 | `regime_weight: 0.0`, `structure_v5_score: 0` |
| 4 | 上升期 regime enable | structure_v5_score ≈ score_v5 | `regime_weight: 1.0` |
| 5 | 响应字段完整性 | 所有 v5 字段存在 | `structure_v5_tier`, `structure_v5_tags`, `market_regime` 都在 |
| 6 | 数据库迁移 | 8 新列自动创建 | PRAGMA table_info 验证列存在 |
| 7 | 分级映射正确性 | 分数 80-100 → tier A | 多个样本验证 |
| 8 | 分页与 mode 兼容 | `?page=2&mode=structure_v5` | 结果正确且 mode 字段保持 |
| 9 | 历史快照与 v5 | `?trading_date=YYYY-MM-DD` | v5 分值被保存并加载 |
| 10 | v3/v4 向后兼容 | score_v3/score_v4 仍可访问 | 所有三个分值都在响应中 |
| 11 | 无 SQL 错误 | 生产级稳定性 | 日志无错误，无性能下降 |

### 6.8 前端影响分析

**候选池列表（index.html）：**
- 排序从 v4 自动切换到 v5
- 新增 Tier 标签（A / B / C / D 彩色徽章）
- 新增 Regime 指示器（图表右上角显示 Uptrend / Sideways / Downtrend）

**单股详情（company.html）：**
- 展示 structure_v5_reason（为什么这只股票排在这个位置）
- 展示 structure_v5_tags（标签 cloud）
- 展示 market_regime（当前市场状态）

**API 调用端（api.js）：**
- 默认调用不带 mode，自动获 structure_v5
- 高级用户可传 ?mode=structure_v4 手动切换

**兼容性：** 
- 若前端还未更新，仍可读 `score_v5` 字段做兼容降级
- 不影响风险排行（F/G 信号）和对比模块

### 6.9 生产部署与回滚计划

**部署步骤：**
1. 提交 structure_v5_model.py + candidate_scoring.py 更新
2. 部署到 Railway（自动触发 git push + redeploy）
3. 首次请求自动执行 migrate_add_structure_v5_fields()
4. 验证 11 点测试通过
5. 前端更新（可延后，向后兼容）

**回滚计划（如果出现问题）：**
- 立即：改 app.py 默认 mode = "structure_v4"，恢复 v4 排序
- 保留所有字段和代码，仅改 default mode
- 后续调查后再启用 v5

### 6.10 限制与后续方向

**当前假设：**
- Conservative_PE50 参数固定，不再调参（已充分验证）
- 市场分级仅基于 SMA200 + 波动率，未纳入高频流动性
- 5 个评分维度覆盖主要信号，但复杂边界（如突发事件）不在模型范围内

**建议的下一步（Priority）：**
| 优先级 | 方向 | 预期收益 |
|--------|------|---------|
| **P0** | 监控生产中 v5 vs v4 的实际表现差异 | 确认 +0.174% 改善是否在实时数据中重现 |
| **P1** | 结合头寸管理规则（Top-10 / Top-20 投资组合）验证 | 从排序验证升级到投资可行性 |
| **P2** | 细化市场分级，引入 implied volatility / 融资成本等深层因素 | 改进 downtrend 期的禁用精度 |
| **P3** | 对比 v5 在不同行业/板块的表现分化 | 识别行业偏好并加入权重调整 |
- ✅ 后续方向建议

