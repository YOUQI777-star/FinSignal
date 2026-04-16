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

**Railway 上缺失的数据（.gitignore 排除，仅本地）：**
- `data/cn/*.json`（48MB，A 股个股快照）→ `/api/company/CN/{code}` 详情端点在云端不可用
- `data/tw/*.json`（5.3MB，台股个股快照）→ `/api/company/TW/{code}` 详情端点在云端不可用
- `/api/report` 也依赖个股快照，云端会返回 404

**已正常工作的云端端点：** health、signals/top（排行）、signals/{market}/{code}（从缓存读）、search、compare

---

## 十二、已知问题 / 技术债

1. **TW OCF 缺失率 72%**：F2 规则在台股几乎全 not_available，需要继续每天跑 `refresh.sh`，约 8-9 天清零。

2. **Governance 数据几乎全缺**：G1 和 G3 规则对绝大多数公司返回 `not_available`。pledge_ratio 数据源没有接入，board composition 数据未采集。

3. **报告是占位版**：`report_generator.py` 当前只输出规则摘要文本，没有接 LLM。`prompt_template.py` 已有模板，接入 DeepSeek 或 OpenAI API 后可激活。环境变量：`LLM_PROVIDER=deepseek`，`LLM_API_KEY=...`。

4. **公司快照不在 Git 仓库**：`data/cn/*.json`（48MB）和 `data/tw/*.json`（5.3MB）在 `.gitignore` 中排除。Railway 云端没有这些文件，导致 `/api/company/{market}/{code}` 和 `/api/report` 返回 404。新环境需重新抓取，或把 `data/tw/` 加入 Git（5.3MB 可接受）。

5. **Neo4j 图谱未接入**：`/api/graph/{market}/{code}` 返回空节点，`Neo4jClient` 是占位实现。

6. **company_master.db 已在 Git 仓库**：712KB，已提交。Railway 上搜索功能正常。

---

## 十三、下一步优先级建议

| 优先级 | 任务 |
|--------|------|
| P0 | 每天跑 `./refresh.sh` 补台股 OCF，约 8 天清零（当前还剩 790 家）|
| P1 | 接入 LLM 替换 report_generator.py 占位版（接 DeepSeek API，key 在 .env） |
| P1 | 把 `data/tw/` 加入 Git（5.3MB），让 Railway 云端支持台股个股详情和报告 |
| P2 | 补充 governance 数据（pledge_ratio 可从 AKShare 获取，CN 市场） |
| P2 | 公司快照定期更新机制（目前是手动跑脚本，可加 cron 或 Railway Cron Service） |
| P3 | 接入 Neo4j 图谱（股权穿透、关联方分析） |
| P3 | 信号趋势历史（目前只看当前一次评估结果，没有时序对比） |
