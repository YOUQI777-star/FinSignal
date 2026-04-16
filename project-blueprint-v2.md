# 公司治理与财务风险扫描平台 — 项目蓝图 v3

## 一句话定位

输入 A 股或台股上市公司代码，自动扫描财务与治理风险信号，生成股权穿透图谱和 AI 风险报告。

---

## 已确认决策

| 项目 | 决策 |
|---|---|
| 市场覆盖 | A 股（沪深）+ 台股（TWSE） |
| A 股数据源 | AKShare（免费、纯 Python） |
| 台股数据源 | TWSE Open API（免费、无需 key） |
| 现成图谱数据 | liuhuanyong/ChainKnowledgeGraph（产业链基础层） |
| 图数据库 | Neo4j AuraDB Free |
| 图谱可视化 | Cytoscape.js + dagre 布局 |
| 后端 | Flask (Python) |
| 前端 | React |
| AI 模块 | DeepSeek API 或 Qwen 免费额度 |
| 部署 | Vercel（前端）+ Render（后端）+ AuraDB Free |
| 开发策略 | 优先复用 GitHub 现成仓库与数据集，核心规则与产品层自研 |
| 总成本 | 开发阶段接近 ¥0，必要时按部署/模型额度小幅升级 |

---

## GitHub 参考项目与复用策略

本项目不从零开始造所有轮子，而是采用“数据底座和工程范式尽量复用，核心判断逻辑自己掌握”的策略。

### 已确认可参考/可复用的 GitHub 项目

| 项目 | 作用 | 复用方式 |
|---|---|---|
| `liuhuanyong/ChainKnowledgeGraph` | A 股产业链图谱基础层 | 直接拉取原始数据，做清洗后导入 Neo4j |
| `jm199504/Financial-Knowledge-Graphs` | 金融知识图谱建模、Cypher、Neo4j 导入范式 | 参考图谱 schema、导入脚本结构、查询写法 |
| `wxy2ab/akinterpreter` | AKShare + LLM 金融分析工作流 | 参考数据访问层与 LLM 解释层的组织方式 |
| `JerBouma/FinanceToolkit` | 指标口径透明化、财务比率组织方式 | 参考规则计算层的字段命名、公式说明与结果表达 |
| `OpenBB-finance/OpenBB` | 大型金融分析平台的分层架构 | 参考模块拆分与数据/分析/展示分层，不直接照搬 |

### 复用原则

1. **直接 pull / clone 的部分**：产业链原始图谱数据、部分 Neo4j 建模范式、部分财经分析工程结构
2. **参考实现但不直接复制的部分**：AKShare 访问方式、指标计算组织、LLM 报告链路
3. **必须自己实现的部分**：公司治理规则、A 股/台股统一 schema、风险信号解释、产品 API、前端交互

### 项目差异化定位

GitHub 上已有项目大多只覆盖以下单点能力之一：

- 财务数据分析 dashboard
- 股票问答或 LLM 分析助手
- 金融知识图谱 demo
- 通用金融研究平台

本项目的差异化是把这些能力组合成一个面向**公司治理与财务风险识别**的完整产品：

- `多源数据对齐`
- `规则引擎判定`
- `股权/产业链图谱`
- `AI 风险解释与报告`

---

## 项目与 ISS STOXX 实习的关系

ISS 实习内容：分析中国大陆和台湾市场上市公司的公司治理，阅读 Proxy Statement，撰写投票建议报告。

本项目的起点：将 ISS 实习中手动做的治理分析工作，提炼成可量化的规则引擎并自动化执行。

面试叙事（四个版本）：

- **投行/并购**：尽调自动化工具，快速筛查标的公司的财务和治理风险
- **行研**：风险信号检测框架，从审计和风控实务中提炼的 20 条规则
- **咨询**：结构化分析框架的产品化——拆解问题→定义指标→量化判断
- **商分**：完整数据链条——多源采集→ETL→图数据库→API→可视化

---

## 数据一致性架构（核心设计）

### 问题

多个数据源（AKShare、TWSE API、ChainKnowledgeGraph、东方财富等）对同一家公司的命名和编码可能不一致。必须在架构层面保证所有数据源指向同一个实体。

### 解决方案：company_master 主数据表

全局唯一主键：`market + code`（如 `CN:600519`、`TW:2330`）

```
company_master 表
├── code          # 股票代码（A股6位 / 台股4位）
├── market        # CN | TW
├── name          # 公司最新名称（以 AKShare / TWSE 为准）
├── name_en       # 英文名（台股用）
├── industry_sw   # 申万行业分类（A股）
├── industry_twse # TWSE 行业分类（台股）
├── status        # active | delisted | suspended
├── ipo_date      # 上市日期
└── updated_at    # 最后更新时间
```

### 数据对齐规则

1. **company_master 是唯一权威来源**，首次运行时从 AKShare（全部 A 股）和 TWSE API（全部台股）拉取生成
2. **ChainKnowledgeGraph 导入时**：以股票代码匹配 company_master，匹配上的才写入 Neo4j，匹配不上的丢弃（退市公司等）
3. **AKShare 财报数据**：以股票代码查询，结果直接关联 company_master
4. **股东/治理数据**：同样以股票代码为 key，写入前校验 company_master 中存在该代码
5. **公司改名**：以 AKShare / TWSE 返回的最新名称为准，导入图谱时只用代码匹配，不用名称匹配
6. **新上市公司**：company_master 中有但 ChainKnowledgeGraph 中没有 → 财报和治理分析正常做，图谱上显示"暂无产业链数据"
7. **退市公司**：ChainKnowledgeGraph 中有但 AKShare 查不到 → 标记 status=delisted，保留图谱关系但不做信号检测

### 数据源分层

为降低实现风险，数据源按照“必须可用”和“可选增强”分层：

- `L1 核心数据源`：AKShare、TWSE Open API、ChainKnowledgeGraph
- `L2 增强数据源`：东方财富等公开网页数据
- `L3 暂不承诺`：需要授权、限制较强或稳定性不明的数据源

产品首版只依赖 L1 跑通主链路；L2/L3 只作为增强项，不阻塞主功能上线。

### 数据流图

```
Step 0: 生成 company_master
         AKShare (全部A股代码+名称+行业) ──┐
                                            ├──→ company_master.db (SQLite)
         TWSE API (全部台股代码+名称+行业) ─┘

Step 1: 导入产业链图谱基础层
         ChainKnowledgeGraph 原始数据
              │
              ├── 用 code 匹配 company_master
              │   ├── 匹配成功 → 写入 Neo4j（Company 节点 + 行业/产品关系）
              │   └── 匹配失败 → 跳过并记录日志
              │
              └── Industry / Product 节点 → 直接写入 Neo4j（无需匹配）

Step 2: 拉取财报 + 治理数据
         AKShare / TWSE API
              │
              ├── 用 code 校验 company_master 存在
              ├── 转换为统一 JSON Schema
              └── 存入 data/{market}/{code}.json

Step 3: 运行规则引擎
         读取 data/{market}/{code}.json
              │
              ├── 执行 20 条规则
              └── 输出 signals/{market}/{code}.json

Step 4: 补充股东数据到 Neo4j
         AKShare stock_gdfx_* 接口
              │
              ├── 用 code 匹配 company_master
              ├── 创建 Person / Institution 节点
              └── 创建 HOLDS_SHARE 关系
```

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Data Sources                           │
│  AKShare (A股)  │  TWSE API (台股)  │  东方财富(可选) │  其他增强源  │
│  财报/股东/质押  │  财报/ESG/估值      │  补充披露/行情   │  非首版依赖   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────────┐
│  ChainKnowledgeGraph   │   (GitHub 现成数据集)               │
│  4654 公司 / 511 行业 / 95559 产品 / 上下游关系              │
└────────────────────────┼────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              company_master (SQLite) — 全局主键              │
│              market + code 唯一标识每家公司                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Python ETL Pipeline                       │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐     │
│  │ Scraper  │ →  │ Rule Engine  │ →  │ Graph Builder │     │
│  │ 数据采集  │    │ 20条规则检测  │    │ 节点/关系构建  │     │
│  └──────────┘    └──────────────┘    └───────────────┘     │
└──────────┬──────────────┬───────────────────┬──────────────┘
           │              │                   │
           ▼              ▼                   ▼
    ┌────────────┐  ┌────────────┐  ┌─────────────────┐
    │   SQLite   │  │    JSON    │  │  Neo4j AuraDB   │
    │  财报缓存   │  │  信号结果   │  │  产业链+股权图谱 │
    └─────┬──────┘  └─────┬──────┘  └────────┬────────┘
          │               │                  │
          └───────────────┼──────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │     Flask Backend     │
              │  REST API + LLM 代理  │←── DeepSeek API
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────────────────────────┐
              │          React Frontend (Vercel)          │
              │                                           │
              │  ┌─────────┐ ┌─────────┐ ┌────────────┐ │
              │  │信号仪表盘│ │股权图谱  │ │ AI风险报告 │ │
              │  │(红旗卡片)│ │Cytoscape│ │ (LLM生成)  │ │
              │  └─────────┘ └─────────┘ └────────────┘ │
              └───────────────────────────────────────────┘
```

---

## 数据模型

### 统一 JSON Schema（双市场通用）

```json
{
  "market": "CN | TW",
  "code": "600519 | 2330",
  "company_id": "CN:600519 | TW:2330",
  "name": "贵州茅台 | 台積電",
  "currency": "CNY | TWD",
  "financials": {
    "annual": [
      {
        "period": "2024",
        "revenue": 0,
        "net_profit": 0,
        "operating_cash_flow": 0,
        "accounts_receivable": 0,
        "inventory": 0,
        "goodwill": 0,
        "total_assets": 0,
        "total_liabilities": 0,
        "non_recurring_items": 0,
        "related_party_revenue": null,
        "rd_capitalization_rate": null,
        "audit_opinion": "standard | qualified | adverse | disclaimer",
        "source": "akshare | twse",
        "unit": "base_currency",
        "as_of": "2025-03-31"
      }
    ]
  },
  "governance": {
    "controlling_shareholder_pct": 0.0,
    "pledge_ratio": 0.0,
    "equity_layers": 0,
    "chairman_is_ceo": false,
    "independent_director_ratio": 0.0,
    "auditor_changes_3y": 0,
    "insider_selling_6m": 0.0,
    "independent_director_overboarding": 0,
    "shareholder_meeting_attendance": 0.0,
    "disclosure_rating": "A | B | C | D",
    "esg_score": null
  },
  "equity_structure": [
    {"holder": "张三", "type": "person", "pct": 0.35, "pledged_pct": 0.5},
    {"holder": "XX控股", "type": "company", "pct": 0.20, "parent": "YY集团"}
  ],
  "coverage": {
    "available_rules": ["F1", "F2", "G1"],
    "missing_fields": ["related_party_revenue", "shareholder_meeting_attendance"]
  }
}
```

### Schema 设计原则

1. 所有可比较财务字段必须带 `period`
2. 所有金额字段必须可追溯到 `currency` 和 `unit`
3. 缺失字段不默认按 `0` 处理，而是明确记录在 `coverage.missing_fields`
4. 规则引擎必须允许 `not_available`，避免因为缺字段产生误判

### Neo4j 图谱模型

**节点类型（5 种）：**
- `(:Company {company_id, code, name, market, industry})` — 上市公司
- `(:Person {entity_id, name, normalized_name, role, source})` — 实控人、高管、独董
- `(:Institution {entity_id, name, normalized_name, type, source})` — 持股机构
- `(:Industry {name, level, parent_industry})` — 行业（来自 ChainKnowledgeGraph）
- `(:Product {name})` — 产品（来自 ChainKnowledgeGraph）

**关系类型（8 种）：**
- `[:HOLDS_SHARE {pct, pledged_pct}]` — 持股关系
- `[:CONTROLS]` — 实际控制关系
- `[:IS_DIRECTOR_OF {role, is_independent}]` — 任职关系
- `[:RELATED_PARTY {transaction_amount}]` — 关联交易关系
- `[:BELONGS_TO_INDUSTRY]` — 公司所属行业（ChainKnowledgeGraph）
- `[:HAS_PRODUCT]` — 公司主营产品（ChainKnowledgeGraph）
- `[:UPSTREAM_OF]` — 产品上游关系（ChainKnowledgeGraph）
- `[:DOWNSTREAM_OF]` — 产品下游关系（ChainKnowledgeGraph）

**关键 Cypher 查询：**

```cypher
// 股权穿透（向上追溯 4 层）
MATCH path = (c:Company {code: $code})<-[:HOLDS_SHARE*1..4]-(holder)
RETURN path

// 找出质押比例超 50% 的股东
MATCH (holder)-[r:HOLDS_SHARE]->(c:Company {code: $code})
WHERE r.pledged_pct > 0.5
RETURN holder.name, r.pct, r.pledged_pct

// 同一实控人控制的所有公司
MATCH (p:Person)-[:CONTROLS]->(c:Company)
WHERE p.name = $controller_name
RETURN c.code, c.name

// 产业链上下游（来自 ChainKnowledgeGraph）
MATCH (c:Company {code: $code})-[:HAS_PRODUCT]->(p:Product)-[:UPSTREAM_OF]->(up:Product)<-[:HAS_PRODUCT]-(supplier:Company)
RETURN supplier.code, supplier.name, up.name AS upstream_product

// 同行业公司
MATCH (c:Company {code: $code})-[:BELONGS_TO_INDUSTRY]->(i:Industry)<-[:BELONGS_TO_INDUSTRY]-(peer:Company)
WHERE peer.code <> $code
RETURN peer.code, peer.name
```

---

## 风险信号规则（20 条）

### 财务红旗（12 条）

| # | 信号 | 触发条件 | 严重度 |
|---|---|---|---|
| F1 | 应收账款异常增长 | AR 增速 > 营收增速 × 2 | 高 |
| F2 | 现金流与利润背离 | 经营性现金流连续 2 年为负 & 净利润为正 | 高 |
| F3 | 商誉减值风险 | 商誉 / 净资产 > 50% | 高 |
| F4 | 审计意见异常 | 非标准无保留意见 | 高 |
| F5 | 关联交易占比过高 | 关联交易收入 / 总营收 > 30% | 中 |
| F6 | 存货周转恶化 | 存货周转天数同比恶化 > 30% | 中 |
| F7 | 偿债压力 | 资产负债率 > 70% & 利息保障倍数 < 2 | 中 |
| F8 | 非经常性损益占比高 | 非经常性损益 / 净利润 > 50% | 中 |
| F9 | 应付账款异常拉长 | 应付周转天数同比增加 > 50% | 低 |
| F10 | 研发资本化率偏高 | 资本化研发支出 / 总研发 > 50% | 低 |
| F11 | 客户集中度风险 | 前 5 大客户占比 > 60% | 低 |
| F12 | 短期债务结构失衡 | 短期借款 / 总债务 > 70% | 低 |

### 治理红旗（8 条）

| # | 信号 | 触发条件 | 严重度 | 适用市场 |
|---|---|---|---|---|
| G1 | 大股东高比例质押 | 质押比例 > 50% | 高 | CN |
| G2 | 多层嵌套持股 | 股权穿透层级 > 4 层 | 高 | CN + TW |
| G3 | 两职合一且独董不足 | 董事长=总经理 & 独董占比 < 1/3 | 高 | CN + TW |
| G4 | 审计机构频繁更换 | 3 年内更换审计机构 | 中 | CN + TW |
| G5 | 高管集中减持 | 6 个月减持 > 持股市值 20% | 中 | CN + TW |
| G6 | 独董过度兼职 | 同时在 > 3 家公司任独董 | 中 | CN + TW |
| G7 | 股东大会出席率低 | 出席率 < 50% | 低 | CN |
| G8 | 信息披露评级差 | 评级为 C 或 D | 低 | CN |

**台股特有补充：** TWSE 官方提供 ESG 评分和公司治理评鉴，可直接作为信号来源，替代 G7/G8。

### 规则实现策略

20 条规则不会盲目同时开工，而是按“数据稳定性”分层：

- `P0 可立即实现`：依赖财报主表或稳定股东字段的规则
- `P1 部分实现`：字段存在但覆盖率可能不稳定的规则
- `P2 增强项`：依赖披露文本、网页抽取或跨源拼接的规则

每条规则都应额外维护一份实现元数据：

| 字段 | 含义 |
|---|---|
| `signal_id` | 如 F1 / G3 |
| `required_fields` | 规则所需字段列表 |
| `source_priority` | 首选与备选数据源 |
| `market_support` | CN / TW / CN+TW |
| `availability` | stable / partial / manual / unavailable |
| `fallback_behavior` | 缺失时返回 not_available / skip |

LLM 不参与规则判定，只负责把规则输出转成自然语言解释和风险摘要。

---

## Flask 后端设计

### API 端点

```python
# app.py — Flask 入口

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/company/<market>/<code>')
def get_company(market, code):
    """公司基本信息 + 财务摘要"""
    pass

@app.route('/api/signals/<market>/<code>')
def get_signals(market, code):
    """所有触发的红旗信号"""
    pass

@app.route('/api/graph/<market>/<code>')
def get_graph(market, code):
    """股权穿透 + 产业链图谱数据（Cytoscape JSON 格式）"""
    pass

@app.route('/api/compare')
def compare_companies():
    """多公司信号对比，参数: ?codes=CN:600519,TW:2330"""
    pass

@app.route('/api/report/<market>/<code>', methods=['POST'])
def generate_report(market, code):
    """生成 AI 风险报告"""
    pass

@app.route('/api/search')
def search_company():
    """搜索公司，参数: ?q=茅台"""
    pass
```

### Flask 依赖

```
# requirements.txt
flask==3.1.*
flask-cors==4.*
neo4j==5.*
akshare
requests
gunicorn
```

---

## 前端页面结构

### 页面 1：首页 / 搜索
- 搜索栏（支持 A 股代码、台股代码、公司名称）
- 市场切换（A 股 / 台股）
- 热门公司快捷入口

### 页面 2：公司分析页
- **顶部**：公司名称、代码、行业、市值、市场标识
- **信号仪表盘**：左列 = 财务红旗卡片，右列 = 治理红旗卡片
  - 每张卡片：信号名、严重度色标、当前值 vs 阈值、一句话解释
  - 无信号触发时显示绿色 "未检出"
- **股权穿透图谱**：Cytoscape.js + dagre 布局
  - 节点颜色区分：公司（蓝）、个人（紫）、机构（灰）
  - 质押节点红色边框高亮
  - 边上标注持股比例
  - 点击节点展开下一层
- **产业链图谱**：Cytoscape.js（数据来自 ChainKnowledgeGraph）
  - 上游供应商 ← 目标公司 → 下游客户
  - 同行业可比公司
- **AI 报告**：按钮触发生成，显示为 Markdown 渲染结果
  - 报告结构：公司画像 → 核心风险点 → 治理评价 → 综合评级

### 页面 3：对比页
- 选择 2-4 家公司（支持跨市场对比）
- 信号矩阵：行 = 信号名，列 = 公司，单元格 = 颜色标记 + 数值

---

## 目录结构

```
governance-risk-scanner/
├── docs/
│   └── project-blueprint.md     # 项目蓝图
├── api/
│   ├── app.py                   # Flask 入口
│   ├── config.py                # 配置（Neo4j URI、DeepSeek Key 等）
│   ├── scrapers/
│   │   ├── cn_akshare.py        # A 股数据采集
│   │   ├── tw_twse.py           # 台股数据采集
│   │   └── schema.py            # 统一 JSON Schema 定义与转换
│   ├── master/
│   │   ├── build_master.py      # 生成 company_master.db
│   │   └── company_master.db    # SQLite 主数据（gitignore）
│   ├── rules/
│   │   ├── engine.py            # 规则引擎主逻辑
│   │   ├── financial_rules.py   # 12 条财务规则
│   │   └── governance_rules.py  # 8 条治理规则
│   ├── graph/
│   │   ├── neo4j_client.py      # Neo4j 连接和查询
│   │   ├── import_chain_kg.py   # 导入 ChainKnowledgeGraph（产业链基础层）
│   │   └── import_equity.py     # 导入股东/股权数据
│   ├── ai/
│   │   ├── prompt_template.py   # LLM prompt 模板
│   │   └── report_generator.py  # 报告生成逻辑
│   ├── requirements.txt
│   └── gunicorn.conf.py         # Gunicorn 部署配置
├── web/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.jsx         # 搜索首页
│   │   │   ├── Company.jsx      # 公司分析页
│   │   │   └── Compare.jsx      # 对比页
│   │   ├── components/
│   │   │   ├── SignalCard.jsx   # 信号卡片组件
│   │   │   ├── EquityGraph.jsx  # Cytoscape 股权图谱组件
│   │   │   ├── ChainGraph.jsx   # Cytoscape 产业链图谱组件
│   │   │   └── AIReport.jsx     # AI 报告组件
│   │   └── App.jsx
│   └── package.json
├── storage/                     # 本地数据缓存（gitignore）
│   ├── cn/                      # A 股财报 JSON
│   ├── tw/                      # 台股财报 JSON
│   ├── signals/                 # 信号检测结果
│   └── chain_kg/                # ChainKnowledgeGraph 原始数据（git clone）
└── README.md
```

---

## 执行顺序（由 Claude 协助完成）

### Step 0：拉取现成仓库与建立参考层
- [ ] pull / clone `ChainKnowledgeGraph`，确认数据格式与 code 字段可用性
- [ ] 阅读 `Financial-Knowledge-Graphs`，提取可复用的 Neo4j schema 与导入范式
- [ ] 阅读 `akinterpreter`，提取 AKShare 封装和 LLM 输出结构思路
- [ ] 阅读 `FinanceToolkit` / `OpenBB`，整理字段口径与模块分层参考

### Step 1：主数据对齐
- [ ] 从 AKShare 拉取全部 A 股代码 + 名称 + 行业 → 写入 company_master.db
- [ ] 从 TWSE API 拉取全部台股代码 + 名称 + 行业 → 写入 company_master.db
- [ ] 下载 ChainKnowledgeGraph，用 code 匹配 company_master 后导入 Neo4j

### Step 2：数据采集脚本
- [ ] A 股：AKShare 财报 + 股东 + 质押 + 高管减持
- [ ] 台股：TWSE API 财报 + ESG + 估值指标
- [ ] 统一转换为 JSON Schema（以 company_master 的 code 为 key）
- [ ] 验证数据覆盖度（20 条规则各需要哪些字段）

### Step 3：规则引擎
- [ ] 先实现 P0 规则，再逐步补 P1 / P2
- [ ] 为每条规则维护 required_fields / availability / fallback_behavior
- [ ] 跑几家公司验证（茅台、台积电、康美药业 / 类似问题公司）

### Step 4：Neo4j 图谱补充
- [ ] 导入股东 / 股权数据（AKShare stock_gdfx_* 接口）
- [ ] 测试股权穿透查询 + 产业链查询

### Step 5：Flask 后端
- [ ] 6 个 API 端点
- [ ] LLM 报告生成集成
- [ ] Gunicorn 配置

### Step 6：React 前端
- [ ] 搜索页
- [ ] 信号仪表盘
- [ ] Cytoscape 股权图谱 + 产业链图谱
- [ ] AI 报告页
- [ ] 对比页

### Step 7：部署 + 收尾
- [ ] Vercel 部署前端
- [ ] Render 部署后端（Gunicorn）
- [ ] README + 架构图 + 截图 + 面试叙事文档

---

## 开发原则

1. 能直接 pull 的数据集和参考工程，优先 pull，不重复造轮子
2. 能借鉴现成 schema 和导入逻辑的模块，优先参考后改写，不闭门重做
3. 风险规则、字段口径和产品 API 保持自研，确保项目有自己的方法论壁垒
4. 所有第三方仓库只作为底座或灵感来源，最终对外叙事仍然是“基于公开数据构建的治理与财务风险扫描平台”
