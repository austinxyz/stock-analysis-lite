# stock-analyze

对翻倍候选股做深度基本面 + 技术面分析，判断市场是否存在错误定价以及翻倍路径是否清晰。

## Arguments

Required: `<TICKER>` — 股票代码（如 `ABAT`）

## Steps

### 1. 拉取量化数据（共用数据层）

```bash
python scripts/ticker_scan.py TICKER --mode full --benchmark --json
```

输出两行 JSON：第一行 benchmark（`spy_vs_ma200_pct` / `qqq_vs_ma200_pct` / `market_env`），第二行 ticker 深度数据。本报告使用的关键字段：

- 价格/波动：`price`、`atr14`、`atr_pct`、`ma50_pct`、`ma150_pct`、`ma200_pct`、`ma200_trend`
- 52 周位置：`high_52w`、`low_52w`、`pct_from_52w_high`、`pct_above_52w_low`
- SEPA：`trend_template`（8 条布尔 + score）、`rs_score`、`rs_pass`
- 财务：`revenue_yoy_pct`、`consecutive_growth_q`、`eps_trend`、`cash_m`、`market_cap_m`
- 筹码：`short_pct_float`、`float_m`、`shares_out_m`、`inst_pct`
- 日历：`next_earnings_date`、`earnings_in_days`

---

### 2. WebSearch 补充

搜索 1：`"[TICKER] earnings revenue growth analyst target 2025 2026"`
搜索 2：`"[TICKER] shares outstanding ATM offering dilution 2025 2026"`
搜索 3：`"[TICKER] catalyst upcoming event contract approval 2026"`

提取：最新财报亮点、分析师数量、目标价、近期融资动态、未来关键催化剂。

---

### 3. BAIT 评分 — 找市场的错误

核心问题：**市场为什么错了？**

| 维度 | 含义 | 评分（0-3） |
|------|------|-----------|
| **B — Behavioral** | 市场情绪过度悲观？锚定偏差？ | 3=明显；0=无 |
| **A — Analytical** | 分析师覆盖少？财务数字被误读？ | 3=明显；0=无 |
| **I — Informational** | 10-Q 注脚有隐藏信息？市场未发现？ | 3=明显；0=无 |
| **T — Technical** | 指数剔除/强制清仓等技术性抛压？ | 3=明显；0=无 |

**各维度评分判据（对齐 `wiki/frameworks/bait.md`）：**

- **B**：可识别的情绪催化剂？恐惧是否被财报数据证伪？short interest >10% = 高、>20% = 极端
- **A**：自建模型 vs 共识差 >20%（关键指标）？覆盖分析师 <3 名？有被媒体/卖方跳过的具体财务行项？
- **I**：transcript Q&A / 10-K 注脚 / proxy / investor day 中有具体、可量化、未被报道的信息？
- **T**：多个技术因素在同一价位汇聚？（高空头 + 回购 + 指数机制 + 期权结构）

**Overlap 换算（裁决以此为准，/12 总分仅展示）：**
`overlap = (B≥2) + (A≥2) + (I≥2) + (T≥2)` → 1 弱 / 2 中等 / 3 强 / 4 极强（对应 bait.md 裁决表）

**解读：** ≥8 强烈错误定价；5-7 有迹象；≤4 市场定价可能已充分

翻倍股最常见：**A + I 双叠加**（覆盖率低 + 财务数字被误读）

---

### 4. 翻倍股专项检查

**① 稀释风险**
- 近12个月股份变化：X → Y（+X%）
- ATM 计划剩余额度？待行权 warrant / 可转债？
- 结论：[低 / 中 / 高] 稀释风险

**② 现金跑道**
```
现金 = $XM
月均 burn = $XM/月（= TTM 运营现金流出 ÷ 12）
当前跑道 = X 个月
```
- <6 个月：🔴 融资压力大，可能低价稀释
- 6-12 个月：⚠️ 关注融资动态
- >12 个月：✅ 安全

**③ 催化剂日历**

| 催化剂 | 预计日期 | 上行情形 | 下行情形 |
|--------|---------|---------|---------|
| 季报 Q X | YYYY-MM | 营收/毛利继续改善 | 营收环比下滑 |
| [合同/FDA/政策] | YYYY-MM | ... | ... |

**④ 空头挤压潜力**
- 空头/Float：X% | Float：XM 股
- 结论：[低 / 中 / 高]（高空头 + 小 float = 额外上涨动力）

---

### 5. SEPA 技术面评估

**8 条趋势模板：**

| # | 条件 | 状态 |
|---|------|------|
| 1 | Price > MA150 AND Price > MA200 | ✅/❌ |
| 2 | MA150 > MA200 | ✅/❌ |
| 3 | MA200 上升趋势 ≥1个月 | ✅/❌ |
| 4 | MA50 > MA150 AND MA50 > MA200 | ✅/❌ |
| 5 | Price > MA50 | ✅/❌ |
| 6 | Price ≥ 52周低点 +30% | ✅/❌ |
| 7 | Price 在52周高点 25% 以内 | ✅/❌ |
| 8 | 相对强度跑赢大盘（`rs_pass`，代理 IBD RS>70）| ✅/❌ + rs_score |

8 条状态直接读 Step 1 的 `trend_template` 字段（`score` = X/8）；#8 用 `rs_pass` 判定并附 `rs_score` 数字（正 = 跑赢 SPY 加权收益）。禁止在无数据时凭印象打 ✅。

**Stage 判断：**

| Stage | 技术状态 | 操作 |
|-------|---------|------|
| Stage 1 | 底部横盘，均线趋平 | 加入 watchlist，等 Stage 2 |
| Stage 2 | 均线多头排列，价格 > MA50 | 运行 `/stock-entry` |
| Stage 3 | 顶部走平 | 减仓信号 |
| Stage 4 | 下降趋势 | 回避 |

**Stage 2 启动信号（需同时满足）：**
1. 价格突破 MA200 并站稳 2-3 周
2. MA50 开始上穿 MA150
3. 有催化剂或财报确认基本面改善

---

### 6. Moneyball 情景 EV（对齐 `wiki/frameworks/moneyball.md`）

三情景概率和必须 = 100%。每个情景给终值算式（`[年] EBITDA/营收 $X × [倍数] = $Z/股`）。

| 情景 | 目标价 | 时间跨度 | 关键假设（2-3条） | 概率 |
|------|--------|---------|------------------|------|
| 🐂 Bull | $X | X 年 | ... | 20-35% |
| Base | $Y | X 年 | ... | 45-60% |
| 🐻 Bear | $Z | X 年 | ... | 15-30% |

```
EV = Bull×P + Base×P + Bear×P
Expected Return = (EV − 现价) / 现价
Asymmetry = Bull 上行% / Bear 下行%
```

**必答三问：**
1. Bear 成立需要什么为真？当前数据支持吗？
2. Bear 是否已 priced in？（已跌 30%+ 时 bear 数学要重算）
3. 解决不确定性的具体催化剂是什么？（下次财报 / FDA / 合同）

**PW EV 触发线**（synthesis.md 优先级规则）：现价 > EV × 0.85 → 即使 BAIT 强、SEPA 好也不追。

---

### 7. 综合结论

必须包含：
1. BAIT 结论（市场错在哪里，一句话）
2. 翻倍路径：什么事件 × 什么时间 × 目标价
3. 主要风险（2-3 条）
4. 入场等待条件（若 Stage 1：等哪几个信号才运行 `/stock-entry`）

---

### 8. 输出报告

保存到 `wiki/tickers/[TICKER]/analysis.md`：

```markdown
# [TICKER] — [公司简称] 分析报告
**分析日期：** YYYY-MM-DD
**当前价格：** $X | **市值：** $XB | **来源赛道：** [赛道名]

---

## 一、公司简介
[行业、核心业务、上市交易所、最近里程碑 — 3-4句]

---

## 二、BAIT 评分

| 维度 | 得分 | 核心信号 |
|------|------|---------|
| **B — Behavioral** | X/3 | [1句] |
| **A — Analytical** | X/3 | [1句] |
| **I — Informational** | X/3 | [1句] |
| **T — Technical** | X/3 | [1句] |

**总评：X/12 — [强/中/弱]错误定价信号**
**Overlap：X 因子重叠 — [弱/中等/强/极强]**

> "[1-2句总结：市场错在哪里]"

---

## 三、技术面（SEPA）
**当前价：$X | MA50：$X | MA150：$X | MA200：$X**

| # | 条件 | 状态 |
|---|------|------|
[8条趋势模板]

**趋势模板得分：X/8 | Stage：X**
- **关键阻力：** $X → $X
- **关键支撑：** $X → $X

---

## 四、财务快照

| 季度 | 营收 | 毛利润 | 毛利率 | QoQ |
|------|------|--------|--------|-----|
[近5季]

| 指标 | 数值 |
|------|------|
| 营收 YoY | X% |
| 现金 | $XM |
| 分析师数量 | X名 |
| 分析师均价目标 | $X（+X%）|

---

## 五、翻倍股专项

- **稀释风险：** [低/中/高] — [1句]
- **现金跑道：** X个月 [✅/⚠️/🔴]
- **催化剂：** [列表]
- **空头挤压：** Float 空头 X%，[低/中/高]潜力

---

## 六、Moneyball 情景 EV

| 情景 | 目标价 | 概率 | 关键假设 |
|------|--------|------|---------|
| 🐂 Bull | $X | X% | [1-2句] |
| Base | $Y | Y% | [1-2句] |
| 🐻 Bear | $Z | Z% | [1-2句] |

**EV：$W | 现价：$P | 预期收益：+X% | 非对称比：X:1**
**PW EV 触发线：现价 [≤/＞] EV×0.85 = $X → [可追 / 不追]**

---

## 七、风险
| 风险 | 级别 | 说明 |
|------|------|------|

---

## 八、结论

**评级：[🔥 强烈关注 / ⭐ 关注候选 / 👀 观察 / ❌ 回避]**

**核心 thesis：** [2-3句]

**翻倍路径：** [事件] YYYY-MM → T1 $X（+X%）→ T2 $X（+X%）

**入场等待条件：**
1. [最关键条件]
2. [次要条件]

**若条件满足 → 运行 `/stock-entry [TICKER]`**

---

*数据来源：yfinance（YYYY-MM-DD）、WebSearch*
*框架：Mauboussin BAIT | Minervini SEPA | Moneyball EV*
*上游：`/ticker-scan` | 下游：`/stock-entry [TICKER]`*
```
