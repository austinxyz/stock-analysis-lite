# ticker-scan

用 热门赛道热门股选择方法论（`wiki/frameworks/hot-sector-method.md`）在七大结构性赛道中发现翻倍股/多倍股候选。三阶段漏斗：2A 九大特征 → 2B 六大类型×五大公式 → 2C 五大标准快速核查。量化指标由 `scripts/ticker_scan.py`（yfinance）提供，定性判断由 LLM 完成，backlog 和新股发现通过 WebSearch。

## Arguments

```
/ticker-scan                              # 发现模式：扫全部七大赛道
/ticker-scan <赛道>                       # 赛道聚焦：如 光互连 / optical / 矿产资源
/ticker-scan <TICKER>                     # 单股验证：对指定股票跑完整 2A/2B/2C 评分
/ticker-scan <赛道> --tickers T1 T2       # 赛道基础池 + 自定义追加
/ticker-scan --tickers T1 T2 T3          # 自定义池（直接进 Stage 2）
```

## 赛道名称映射表（用于模式检测和文件命名）

| 中文输入 | 英文 ID（文件名用）| Chen 点名代表标的 |
|---------|--------------|----------------|
| 存储 / 存储记忆体 / storage | storage | MU MRVL QMCO GSIT |
| 光互连 / 光电互连 / optical | optical | COHR CRDO AAOI AXTI NOK OCC LWLG MXL |
| 卫星 / LEO卫星 / satellite | satellite | RKBL YSS PL SIDU GCTS ASTS |
| 电网 / 储能 / 功率半导体 / grid | grid | NVTS WOLF VSH AMSC FLNC EOSE |
| 封装 / 封测 / packaging | packaging | AMKR COHU AEHR INTC ASX INTT |
| 矿产 / 矿产资源 / minerals | minerals | ALOY UUUU ABAT ALM USAR UMAY |
| 房地产 / realestate | realestate | OPEN COMP |

## Steps

### 0. Resolve language + detect mode

Read `data/config.md`, extract `lang` (default `zh`). If `--lang zh|en` passed, override.

**Mode detection（优先级从高到低）：**
- `--tickers` only，无其他参数 → **custom-pool mode**（直接进 Stage 2，跳 Stage 1）
- 参数匹配赛道名（对照上方映射表，中英文均支持）→ **sector mode**
- 参数匹配纯大写字母 ticker（1–6 字符）→ **single-stock mode**（跳过 Stage 1 cutoff，完整跑 2A/2B/2C）
- 无参数 → **discovery mode**（全部七大赛道）

存储解析后的 `MODE`、`SECTOR_EN`（文件名用）、`BASE_TICKERS`（从映射表提取）。

---

### 1. 构建候选池

**① Chen 基础池**
根据 MODE 从上方映射表读取目标赛道 ticker。
- discovery mode → 全部七大赛道所有标的
- sector mode → 该赛道标的
- single-stock mode → 仅输入 ticker
- custom-pool mode → 仅 `--tickers` 列表

**② WebSearch 发现新股**（discovery/sector mode 时执行，single-stock/custom-pool 跳过）

对每个目标赛道执行：
```
WebSearch: "[sector keyword] small cap stock NYSE Nasdaq 2025 2026 growth"
```
赛道 keyword 参考：
- optical → "optical interconnect photonics"
- storage → "AI memory HBM DRAM"
- satellite → "LEO satellite communications"
- grid → "power semiconductor grid storage SiC"
- packaging → "advanced packaging OSAT semiconductor"
- minerals → "critical minerals rare earth uranium battery"
- realestate → "proptech real estate technology"

从结果中提取 ticker，每赛道**最多 10 只新股**，OTC 排除。新发现 ticker 标记为 `[NEW]`，直接进 Stage 2（不受 Stage 1 cutoff 限制）。

**③ --tickers 追加**
`--tickers` 中的 ticker 追加到池，直接进 Stage 2（skip Stage 1 cutoff）。

最终候选池去重。记录：`Chen点名 X + 新发现 Y + --tickers Z`

---

### 2. Stage 0 — 运行 ticker_scan.py（批量拉取量化数据）

```bash
python scripts/ticker_scan.py <全部候选 ticker> --json
```

解析每行 JSON，存入 `scan_data` dict（key = ticker）。

**OTC 即时排除**：`is_otc == true` 的 ticker 从候选池移除，记入筛除表（原因："OTC，非主板上市"）。

---

### 3. Stage 1 — 2A 九大特征（LLM + yfinance，Chen 点名标的用；新发现/--tickers 跳过 cutoff）

对每个候选 ticker，结合 `scan_data` 和 LLM 知识，逐条评估：

| # | 特征 | 数据来源 | 判断规则 |
|---|------|---------|---------|
| 1 | 营收/利润高速增长 | **yfinance** | `revenue_yoy_pct > 20` → ✅；10–20 → ⚠️；<10 或无数据 → LLM 判断 |
| 2 | 扭亏转盈拐点 | **yfinance** | `eps_trend == "loss→profit"` → ✅ |
| 3 | 企业转型 | LLM | 老业务 + 新题材？（如 NOK 通信→AI）|
| 4 | 大量订单/积压 | LLM | 已知 backlog > 当年营收信号？ |
| 5 | 高端新材料/技术壁垒 | LLM | 专利/独家工艺/材料技术门槛？ |
| 6 | 热门赛道底层标的 | LLM | 非赛道龙头，但受赛道结构性需求驱动？ |
| 7 | 供应链回归美国 | LLM | CHIPS 法案/国防采购/去中国化受益？ |
| 8 | 早期验证阶段 | LLM | 产品进入测试/POC/首批采购阶段？ |
| 9 | 财报断层 gap-up | **yfinance** | `max_gap_up_pct > 10` → ✅ |

**评分**：命中 X/9。

**晋级规则**：
- Chen 基础池标的：≥2/9 → 进 Stage 2
- `[NEW]`（WebSearch 新发现）：直接进 Stage 2（LLM 可能不熟悉）
- `--tickers` 标的：直接进 Stage 2
- single-stock mode：直接进 Stage 2

未通过的 → 筛除表（原因："2A 仅 X/9"）。

---

### 4. Stage 2 — 2B 六大类型 × 五大公式（yfinance + LLM + WebSearch backlog）

对 Stage 1 通过的 ticker，按以下顺序评估：

**六大类型（0–6 分）：**

| # | 类型 | 数据来源 | 判断规则 |
|---|------|---------|---------|
| 1 | 行业赛道足够大（TAM）| LLM | 多年期结构性需求？赛道规模 $10B+？ |
| 2 | 营收进入爆发期 | **yfinance** | `revenue_yoy_pct > 50` 或 `revenue_accel == true` → ✅；>20 → ⚠️ |
| 3 | 订单储备 > 当年营收 | WebSearch | query: `"[TICKER] backlog order book 2025 2026"` → 找具体数字；无数据 → ⚠️ |
| 4 | 技术壁垒高 | LLM | 专利保护/独家合同/工艺护城河？ |
| 5 | 机构开始建仓 | **yfinance** | `inst_pct > 5` → ⚠️；`inst_pct > 15` 且趋势上升 → ✅ |
| 6 | 小市值 + 主板上市 | **yfinance** | `is_otc == false AND market_cap_m < 2000` → ✅；2000–5000 → ⚠️；>5000 → ❌ |

**五大公式（必要条件，binary ✓/✗）：**

| # | 公式 | 数据来源 | 判断 |
|---|------|---------|------|
| 1 | 大赛道 | LLM | TAM 多年期结构性需求？ |
| 2 | 营收高增长 | **yfinance** | `revenue_yoy_pct > 20` |
| 3 | 订单大、多 | WebSearch backlog | 有 backlog 信号 |
| 4 | 技术壁垒高 | LLM | 有明确技术护城河 |
| 5 | 小市值（主板，非OTC）| **yfinance** | `is_otc == false AND market_cap_m < 5000` |

**晋级规则**：六大类型 ≥3 AND 五大公式 ≥3/5 → 进 Stage 3

未通过的 → 筛除表（注明：类型 X/6，公式 X/5）。

---

### 5. Stage 3 — 2C 五大标准快速核查（yfinance + WebSearch backlog，Stage 2 通过者）

| # | 标准 | 数据来源 | 判断 | 输出 |
|---|------|---------|------|------|
| 1 | 营收/盈利 YoY >20%，或亏损收窄 >50% | **yfinance** | `revenue_yoy_pct > 20` 或 `eps_trend == "improving"/"loss→profit"` | ✅/⚠️/❌ + 具体数字 |
| 2 | 积压订单覆盖 ≥2 季度收入 | WebSearch | query: `"[TICKER] backlog guidance Q1 Q2 2026"` | ✅/⚠️/❌ + 原文摘录 |
| 3 | 连续 ≥3 季度正向增长 | **yfinance** | `consecutive_growth_q >= 3` | ✅/⚠️/❌ + 季度数 |
| 4 | 盈利拐点出现（亏→盈） | **yfinance** | `eps_trend == "loss→profit"` | ✅/⚠️/❌ |
| 5 | 价格结构配合（Stage 2，非 Stage 4 崩坏）| **yfinance** | `ma50_pct > 0 AND ma200_pct > -20` | ✅/⚠️/❌ + MA 数字 |

每条输出：`✅/⚠️/❌ — [1行证据，尽量含具体数字]`

---

### 6. 打标签 + 输出

**标签规则：**

| 标签 | 条件 |
|------|------|
| 🔥 多倍候选 | 2B类型 ≥5/6 AND 2B公式 5/5✓ AND 2C ≥4✅ |
| ⭐ 翻倍候选 | 2B类型 ≥3/6 AND 2B公式 ≥3/5✓ AND 2C ≥3✅ |
| 👀 观察 | 通过 Stage 2 cutoff，但 2C 信号不足（<3✅）|
| ❌ 筛除 | 未通过 Stage 1 或 Stage 2 |

**输出格式：**

```
## /ticker-scan [赛道|ALL] — YYYY-MM-DD

候选池：N 只（Chen点名 X + 新发现 Y + --tickers Z）
Stage 1 通过：N 只 | Stage 2 通过：N 只 | Stage 3 评估：N 只

### 综合排名

| # | Ticker | 赛道 | 2A/9 | 2B类型/6 | 2B公式/5 | 2C核查 | 标签 | 建议 |
|---|--------|------|------|----------|----------|--------|------|------|
| 1 | LWLG | 光互连 | 7 | 5 | 5/5 | ✅✅✅⚠️✅ | 🔥多倍候选 | /stock-analyze LWLG |
| 2 | GCTS | LEO卫星 | 6 | 4 | 4/5 | ✅✅⚠️✅✅ | ⭐翻倍候选 | /stock-analyze GCTS |
| 3 | RKBL | LEO卫星 | 4 | 3 | 3/5 | ✅⚠️❌✅⚠️ | 👀观察 | 等下季财报 |

### Stage 1/2 筛除

| Ticker | 筛除阶段 | 原因 |
|--------|---------|------|
| VIAV | Stage 1 | 2A 仅 1/9，无增长特征 |
| MXL | Stage 2 | 六大类型 2/6，公式 2/5（营收下滑）|
| SIDU | OTC排除 | OTC 非主板上市 |

### 新发现（WebSearch 发现，非 Chen 点名）
- [TICKER] — 赛道：[X] | 市值：$XM | 交易所：Nasdaq | [1句发现理由]

### 赛道结论

**赛道周期判断：** [早期/扩张期/中后期/泡沫期] — 判断依据（如：多数标的市值已脱离小市值门槛，赛道进入中后期）

**最强候选：** [1–2 只] — 具体原因（最高 2A+2B+2C 综合得分；或唯一满足小市值条件）

**当前可操作窗口：**
- ✅ 现在可进：[Ticker] — 入场条件已满足（具体：现价 vs MA，EPS状态，催化剂）
- ⏳ 等待触发：[Ticker] — 需要什么条件（具体价格/事件/季报）
- ❌ 暂不考虑：[Ticker] — 原因（趋势破位/EPS下滑/超买）

**赛道空白信号：** 本赛道是否存在 Chen 尚未点名但值得跟踪的潜力标的？（如有，列出；如无，写"暂无明显空白"）

**下一步行动：** `/stock-analyze <TICKER>` 对 🔥/⭐ 做完整 15 节论文；👀 等触发条件后再跑 `/ticker-scan <TICKER>` 单股验证
```

---

### 7. 保存输出文件

**路径：** `outputs/ticker-scan/YYYY-MM-DD-[SECTOR_EN|ALL|TICKER].md`

- `SECTOR_EN` 用映射表中的英文 ID（optical / storage / satellite / grid / packaging / minerals / realestate）
- single-stock mode → 用 ticker 名（如 `2026-06-15-GCTS.md`）
- discovery mode → `2026-06-15-ALL.md`
- 同日同赛道再次运行 → append 新 section，不覆盖

**文件结构（固定顺序）：**

```
# /ticker-scan [赛道] — YYYY-MM-DD

[综合排名表]
[Stage 1/2 筛除表]
[新发现]
[赛道结论]

---

## 中间分析过程（完整记录）

### Stage 0 — ticker_scan.py 原始数据
[原始 yfinance 数据表，所有 ticker 所有字段]

### Stage 1 — 2A 九大翻倍股特征
[逐 ticker × 逐条特征评分表，含判断依据]

### Stage 2 — 2B 六大类型 × 五大公式
[六大类型表 + 五大公式表（两个独立表）]

### Stage 3 — 2C 五大标准详细核查
[逐 ticker × 五条标准，每条含证据行]
```

中间分析内容**必须完整保存**，不可省略。这是下次复盘、更新评分、与 `/stock-analyze` 对比的原始依据。

---

## 与现有 skills 的分工

| Skill | 关系 |
|-------|------|
| `/sector-analyze` | ticker-scan 读 `outputs/market/daily/` 已有赛道健康度，不重新运行赛道分析 |
| `/stock-analyze` | 下游；ticker-scan 永远不自动触发，由用户手动对 🔥/⭐ 候选运行 |
| `/morning-check` | 无直接关系；用户自行决定是否 `positions.py add --status Watch` |
| `/method-integrate` | ticker-scan 可读 `wiki/opinions/method-log/` 近 7 日文件，若某 ticker 近期被方法论提及，2A 评分 +1 bonus（标注"方法论近期提及"）|

## ticker-scan 不做的事

- 不自动调用 `/stock-analyze`
- 不写入 `positions.py`
- 不做 DCF 或深度财报建模（那是 `/stock-analyze` Section 8–10）
- 不替代 `/sector-analyze` 的赛道健康评估
- 不做买入决策，只输出候选排名
