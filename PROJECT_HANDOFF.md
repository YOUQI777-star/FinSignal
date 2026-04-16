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
| 数据存储 | 本地 JSON 文件 (`data/cn/*.json`, `data/tw/*.json`) + SQLite (company_master.db) |
| 信号缓存 | `data/signals/cn_signals.json`, `data/signals/tw_signals.json` |
| 数据源（CN） | AKShare EastMoney bulk API |
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
│   ├── gunicorn.conf.py            # Gunicorn 生产配置（未使用）
│   ├── ai/
│   │   ├── report_generator.py     # 报告生成（当前是占位规则摘要，未接 LLM）
│   │   └── prompt_template.py      # LLM prompt 模板（未激活）
│   ├── data_access/
│   │   ├── local_store.py          # 读取 data/cn/*.json, data/tw/*.json
│   │   ├── master_store.py         # 读取 SQLite company_master.db
│   │   ├── company_repository.py   # 合并 master + snapshot，统一对外接口
│   │   └── coverage.py             # 判断 snapshot_tier（full/partial/shell）
│   ├── rules/
│   │   ├── base.py                 # RuleDefinition + build_signal_result
│   │   ├── engine.py               # RuleEngine.evaluate(snapshot) → signal result
│   │   ├── financial_rules.py      # F1 F2 F3 F4
│   │   └── governance_rules.py     # G1 G3
│   ├── scrapers/
│   │   ├── cn_akshare.py           # A 股抓取（AKShare + EastMoney）
│   │   ├── cn_baostock.py          # A 股补充（BaoStock，较少使用）
│   │   ├── tw_twse.py              # 台股抓取（TWSE OpenAPI + FinMind OCF）
│   │   ├── schema.py               # 数据 schema 定义
│   │   └── save_snapshots.py       # 将抓取结果写入 data/cn/ 或 data/tw/
│   ├── master/
│   │   └── build_master.py         # 构建 company_master.db（SQLite）
│   ├── graph/
│   │   └── neo4j_client.py         # Neo4j 占位（未接入，返回空节点）
│   └── scripts/
│       ├── bulk_enrich_cn.py       # A 股批量财务数据补充（EastMoney bulk）
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
│   ├── api.js                      # 所有 API 调用封装 + MOCK_DATA fallback
│   ├── index.html + app.js         # Dashboard 首页
│   ├── company.html + company.js + company.css  # 单公司详情页
│   ├── ranking.html + ranking.js   # 全量信号排行榜
│   ├── compare.html + compare.js   # 多公司对比
│   ├── reports.html + reports.js   # 报告生成页
│   ├── search.html + search.js     # 公司搜索页
│   └── settings.html + settings.js # 系统设置
├── refresh.sh                      # 每日一键：补 OCF + 重算信号缓存
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
```

---

## 七、前端架构

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
| Dashboard | `index.html` + `app.js` | 信号排行榜（top 50）+ 规则分布 + 最近查看 |
| 公司详情 | `company.html` + `company.js` + `company.css` | 单公司完整信号分析，含 sparkline 折线图 |
| 全量排行 | `ranking.html` + `ranking.js` | 完整排行表格，支持筛选、前端搜索、Export CSV |
| 多公司对比 | `compare.html` + `compare.js` | Summary 表 + Rule Matrix（行=规则，列=公司）|
| 报告 | `reports.html` + `reports.js` | 输入公司 → POST 生成报告 → 展示文本 + Copy |
| 搜索 | `search.html` + `search.js` | 全文搜索，带搜索词高亮、市场 tab 过滤 |
| 设置 | `settings.html` + `settings.js` | API Base URL、默认筛选参数、清除历史 |

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

## 八、数据链路与覆盖状态

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

## 九、本地启动方式

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

## 十、每日维护命令

```bash
# 每天运行一次，补充台股 OCF 并重算信号缓存
cd "/Users/wangyouqi/Documents/DesktopOrganizer/Web Development/C_G"
./refresh.sh
```

脚本内容：
1. `enrich_tw_ocf.py --limit 100 --delay 1.5`（FinMind 配额内最大化）
2. `run_signals.py --market TW`（重算 TW 信号缓存）
3. `run_signals.py --market CN`（重算 CN 信号缓存）

---

## 十一、部署

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

**Railway 已包含的数据文件（在 Git 中）：**
- `data/signals/cn_signals.json`（21MB，A 股信号缓存）
- `data/signals/tw_signals.json`（3.3MB，台股信号缓存）
- `backend/master/company_master.db`（712KB，公司搜索）
- `data/cn/*.json`（48MB，A 股 5502 家个股快照）✅ 已加入 Git
- `data/tw/*.json`（5.3MB，台股 1081 家个股快照）✅ 已加入 Git

**已正常工作的云端端点：** 全部端点均可用，包括 `/api/company/{market}/{code}` 详情和 `/api/report/{market}/{code}` 报告生成。

---

## 十二、已知问题 / 技术债

1. **TW OCF 缺失率 72%**：F2 规则在台股几乎全 not_available，需要继续每天跑 `refresh.sh`，约 8-9 天清零。

2. **Governance 数据几乎全缺**：G1 和 G3 规则对绝大多数公司返回 `not_available`。pledge_ratio 数据源没有接入，board composition 数据未采集。

3. ~~**报告是占位版**~~ ✅ **已完成**：`report_generator.py` 已接入 DeepSeek，使用 `deepseek-chat` 模型，中文 prompt，输出三段式 Markdown 报告（公司概况 / 风险信号解读 / 综合评估），API 失败时自动降级为规则摘要。Railway 环境变量 `LLM_PROVIDER=deepseek`、`LLM_API_KEY` 已配置。

4. ~~**公司快照不在 Git 仓库**~~ ✅ **已完成**：`data/cn/*.json`（48MB，5502 家）和 `data/tw/*.json`（5.3MB，1081 家）已加入 Git 并部署至 Railway。`/api/company/{market}/{code}` 和 `/api/report` 在云端完全可用。

5. **Neo4j 图谱未接入**：`/api/graph/{market}/{code}` 返回空节点，`Neo4jClient` 是占位实现。

6. **company_master.db 已在 Git 仓库**：712KB，已提交。Railway 上搜索功能正常。

---

## 十三、下一步优先级建议

| 优先级 | 任务 |
|--------|------|
| P0 | 每天跑 `./refresh.sh` 补台股 OCF，约 8 天清零（当前还剩 790 家）|
| ✅ 已完成 | 接入 DeepSeek LLM，report_generator.py 生成真实中文风险报告，含降级fallback |
| ✅ 已完成 | `data/cn/`（48MB）和 `data/tw/`（5.3MB）加入 Git，Railway 全端点可用 |
| P2 | 补充 governance 数据（pledge_ratio 可从 AKShare 获取，CN 市场） |
| P2 | 公司快照定期更新机制（目前是手动跑脚本，可加 cron 或 Railway Cron Service） |
| P3 | 接入 Neo4j 图谱（股权穿透、关联方分析） |
| P3 | 信号趋势历史（目前只看当前一次评估结果，没有时序对比） |

---

## 十四、拟扩展功能规划

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
