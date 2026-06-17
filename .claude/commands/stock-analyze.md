# stock-analyze

对个股做深度基本面 + 技术面分析。
**支持三种股票类型：🏦 蓝筹长持 / 🚀 翻倍候选 / ⚡ 热赛道动量**，分析框架按类型自动调整。

## Arguments

Required: `<TICKER>` — 股票代码（如 `ABAT`, `NVDA`, `LLY`）
Optional: `--type 蓝筹 | 翻倍 | 动量` — 手动指定类型（否则自动判断）

## 框架依据

读取 `wiki/frameworks/bait.md` — Mauboussin BAIT 评分（Behavioral/Analytical/Informational/Technical）
读取 `wiki/frameworks/sepa.md` — SEPA 趋势模板 + Stage 判断

---

## Steps

### 0. 股票类型判断（决定整个分析重点）

**自动判断规则：**

| 类型 | 判断条件 | 分析重点 |
|------|---------|---------|
| 🏦 **蓝筹长持** | 市值 >$10B + 已盈利 + 非热赛道小盘 | 护城河深度、FCF 质量、估值vs历史、LTCG 考量 |
| 🚀 **翻倍候选** | 市值 $500M–$10B + Chen 赛道 + 高成长/拐点 | 稀释风险、现金跑道、催化剂日历、2A/2B/2C 评分 |
| ⚡ **热赛道动量** | 市值 <$2B + 纯动量 + Chen 热赛道卫星仓 | 赛道强度、SEPA Stage、快速催化剂、短期动量指标 |

用户传 `--type` 参数时直接采用，否则根据 Step 1 数据 + LLM 判断自动分类。

**在输出报告顶部明确标注类型（影响整个分析逻辑）。**

---

### 1. 拉取量化数据（yfinance）

```python
import yfinance as yf
import pandas as pd

t = yf.Ticker("TICKER")
info = t.info

# 技术面
hist = t.history(period="1y")
price  = hist['Close'].iloc[-1]
ma50   = hist['Close'].rolling(50).mean().iloc[-1]
ma150  = hist['Close'].rolling(150).mean().iloc[-1]
ma200  = hist['Close'].rolling(200).mean().iloc[-1]
hi52   = hist['High'].rolling(252).max().iloc[-1]
lo52   = hist['Low'].rolling(252).min().iloc[-1]

# ATR-14（波动性评估）
high_low   = hist['High'] - hist['Low']
high_close = abs(hist['High'] - hist['Close'].shift())
low_close  = abs(hist['Low']  - hist['Close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
atr14 = tr.rolling(14).mean().iloc[-1]
atr_pct = atr14 / price * 100

# 财务
qfin = t.quarterly_financials
qbal = t.quarterly_balance_sheet

# 营收（近5季）
revenue = qfin.loc['Total Revenue'] if 'Total Revenue' in qfin.index else None
gross   = qfin.loc['Gross Profit']  if 'Gross Profit'  in qfin.index else None

# FCF / 现金（蓝筹重点）
cash   = qbal.loc['Cash And Cash Equivalents'].iloc[0] if 'Cash And Cash Equivalents' in qbal.index else None
cfo    = t.quarterly_cashflow
opcf   = cfo.loc['Operating Cash Flow'].iloc[:4].sum() if cfo is not None else None  # TTM 经营现金流
capex  = cfo.loc['Capital Expenditure'].iloc[:4].sum() if (cfo is not None and 'Capital Expenditure' in cfo.index) else None
fcf    = (opcf + capex) if (opcf and capex) else None  # FCF = 经营现金流 - Capex

# 股份（稀释检查）
shares_out = info.get('sharesOutstanding', None)

# 机构持仓、空头
inst_pct   = info.get('heldPercentInstitutions', 0) * 100
short_pct  = info.get('shortPercentOfFloat', 0) * 100
float_sh   = info.get('floatShares', None)
market_cap = info.get('marketCap', 0)

print(f"价格={price:.2f}  市值={market_cap/1e9:.1f}B  ATR%={atr_pct:.1f}%")
print(f"MA50={ma50:.2f}  MA150={ma150:.2f}  MA200={ma200:.2f}")
print(f"ATR14={atr14:.2f}  52周高={hi52:.2f}  低={lo52:.2f}")
print(f"机构持仓={inst_pct:.1f}%  空头={short_pct:.1f}%")
print(f"现金={cash/1e6:.1f}M  TTM经营现金流={opcf/1e6:.1f}M  FCF={fcf/1e6:.1f}M" if cash and opcf else "")
```

---

### 2. WebSearch 补充（基本面 + 分析师）

搜索 1：`"[TICKER] earnings revenue growth 2025 2026 analyst target"`
搜索 2（蓝筹额外）：`"[TICKER] free cash flow dividend moat competitive advantage 2026"`
搜索 2（翻倍/动量）：`"[TICKER] shares outstanding ATM offering dilution 2025 2026"`
搜索 3：`"[TICKER] catalyst upcoming event contract approval backlog 2026"`

提取：
- 最新财报亮点、分析师数量、目标价
- 蓝筹：FCF trend、股息、回购、管理层质量信号
- 翻倍/动量：近期股权融资/定增/ATM 动态、未来 6-12 月内关键催化剂

---

### 3. BAIT 评分（Mauboussin 框架，每项 0-3 分）

Mauboussin BAIT 的核心问题：**市场为什么错了？错误有多严重？**

| 维度 | 核心问题 | 评分信号 |
|------|---------|---------|
| **B — Behavioral（行为错误）** | 市场情绪是否过度悲观？定价反映了认知偏差？ | 3=明显情绪错价；2=部分；1=轻微；0=无 |
| **A — Analytical（分析盲点）** | 覆盖率低？非经常性项目扭曲？传统指标不适用？ | 3=明显盲点；2=部分；1=轻微；0=无 |
| **I — Informational（信息不对称）** | 10-Q 注脚、供应链信号、行业渠道数据？ | 3=明显信息优势；2=部分；1=轻微；0=无 |
| **T — Technical（技术因素）** | 指数剔除、强制清仓、期权到期、低流动性？ | 3=明显技术错位；2=部分；1=轻微；0=无 |

**解读：**
- 总分 ≥8：强烈错误定价信号
- 总分 5-7：有错误定价迹象，需确认催化剂
- 总分 ≤4：市场定价可能已充分

> 蓝筹 BAIT 重点看 A+T（盲点 + 技术性抛压 = 最常见买入窗口）。翻倍 BAIT 重点看 B+I（情绪超卖 + 市场未发现的信息）。

---

### 4. 类型专项分析（按 Step 0 判断结果选择）

---

#### 🏦 蓝筹长持 专项分析

> **蓝筹买的是护城河 + 时间**。分析重点是"它 5 年后仍然是市场领导者吗"，而非短期催化剂。

**① 护城河深度（Moat Quality）**

| 护城河类型 | 有无 | 证据 |
|-----------|------|------|
| 网络效应 | ✅/❌ | |
| 转换成本 | ✅/❌ | |
| 成本优势（规模/流程）| ✅/❌ | |
| 无形资产（品牌/专利/监管牌照）| ✅/❌ | |
| 有效规模（市场容量限制竞争）| ✅/❌ | |

**结论：** [无/窄/宽护城河] — [2-3句理由]

**② FCF 质量**
```
TTM FCF = $XB（FCF Margin = X%）
FCF 5年增速 = +X% CAGR
资本分配：股息 $X/股（股息率X%）+ 回购 $XB TTM
```
- FCF Margin >15% = 健康；>25% = 优质
- 若 FCF 增速高于收入增速 → 杠杆提升（好信号）

**③ 估值 vs 历史（多重指标）**
```
当前 P/FCF = Xx  vs 5年均值 Xx  vs 行业均值 Xx
当前 EV/EBITDA = Xx  vs 5年均值 Xx
P/E (fwd) = Xx  vs 历史中枢 Xx
```
- 折价于历史均值 >20% → 潜在机会
- 溢价于均值 >30% → 需要更强的增长预期支撑

**④ LTCG 考量**
- 计划持有时间 > 1年 → 应在 LTCG 账户或确认持有到期
- 买入账户：Roth IRA 免税 / 应税账户 LTCG 15% / 短期税率 37%
- **注意：蓝筹不要为短期波动（<10%）出仓，税务摩擦代价大**

---

#### 🚀 翻倍候选 专项分析

> **翻倍股的 alpha 来自"拐点前入场"**。检查点：稀释不破坏故事 + 现金够活到催化剂 + 催化剂日历明确。

**① 稀释风险**
- 近12个月股份变化：X → Y（+X%）
- 是否有 ATM 计划？剩余额度？
- 是否有待行权 warrant / 可转债？潜在稀释比例？
- **结论：[低/中/高] 稀释风险**

**② 现金跑道**
```
现金 = $XM
TTM 月均 burn = $XM/月
当前跑道 = X 个月
```
- <6 个月：🔴 融资压力，可能被迫低价稀释
- 6-12 个月：⚠️ 关注融资动态
- >12 个月：✅ 安全

**③ 催化剂日历**

| 催化剂 | 预计日期 | 上行情形 | 下行情形 |
|--------|---------|---------|---------|
| 季报（Q X）| YYYY-MM | 营收/毛利继续改善 | 营收环比下滑 |
| [合同/FDA/政策/合作]| YYYY-MM | ... | ... |

**④ 空头挤压潜力**
- 空头/Float：X% | Float：XM 股 | Days to Cover：X天
- **结论：[无/低/中/高]**

---

#### ⚡ 热赛道动量 专项分析

> **动量股买的是"赛道最热那一段"**。超出热度窗口或技术破位立刻出，不恋战。

**① 赛道强度检查**
- Chen Yun 近 7 日提及次数：X 次（≥3 = 热赛道确认）
- 赛道 ETF 状态：[ETF名] vs MA50 = +/-X%（>0% = 赛道趋势向上）
- 赛道同类股涨跌：[近期表现，说明赛道是否普涨]

**② 相对强度（RS）**
- vs 同赛道龙头（1个月回报）：本股 +X% vs 龙头 +X%
- vs S&P 500（3个月）：+X% vs +X%
- **结论：[赛道领头 / 跟随 / 落后]**（落后＝不选）

**③ 动量催化剂（30天内）**
| 近期信号 | 日期 | 量价 |
|---------|------|------|
| 财报 gap-up | YYYY-MM-DD | 量比 Xx |
| 合同/订单 | YYYY-MM-DD | |
| 轧空 | YYYY-MM-DD | 空头/Float X% |

**④ 移动止损参考**
```
近10日最高价 = $X
ATR14        = $X
初始移动止损  = 近10日高 - 1.5×ATR = $X
```
技术破位信号：SEPA Stage 由 2 → 3/4，或赛道 ETF 跌破 MA50。

---

### 5. SEPA 技术面评估（参考 wiki/frameworks/sepa.md）

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
| 8 | RS > 70百分位 | ✅/⚠️/❌ |

**Stage 判断 + 各类型入场标准：**

| Stage | 技术状态 | 蓝筹 | 翻倍候选 | 热赛道动量 |
|-------|---------|------|---------|-----------|
| Stage 1 | 底部横盘整理 | ❌ 不入 | 可小仓试探 (≤1%) | ❌ 不入 |
| Stage 2 | 均线多头排列 | ✅ 标准入场 | ✅ 全仓建立 | ✅ 唯一入场区 |
| Stage 3 | 顶部走平 | 减仓信号 | 减仓信号 | 立即减仓 |
| Stage 4 | 下降趋势 | ❌ 回避 | ❌ 回避 | ❌ 回避 |

---

### 6. 综合结论 + 路径

**必须包含：**
1. BAIT 定性结论（市场错在哪里）
2. 各类型路径：
   - 蓝筹：**护城河持续 5 年场景** + 合理估值区间 + 下行保护分析
   - 翻倍：**具体翻倍场景**（什么事件 × 什么时间 × 什么价格目标）
   - 动量：**热度窗口估算**（赛道持续热多久 + 目标价 + 止损纪律）
3. 主要风险
4. 入场等待条件（若 Stage 1 或条件未满足：等什么信号才运行 `/stock-entry`）

---

### 7. 输出报告

保存到 `wiki/tickers/[TICKER]/analysis.md`：

```markdown
# [TICKER] — [公司简称] 分析报告
**分析日期：** YYYY-MM-DD
**当前价格：** $X | **市值：** $XB
**股票类型：** [🏦 蓝筹长持 / 🚀 翻倍候选 / ⚡ 热赛道动量]
**来源赛道：** [Chen 赛道名 / 蓝筹自选 / N/A]

---

## 一、公司简介
[行业、核心业务、上市交易所、最近里程碑 — 3-4句]

---

## 二、BAIT 评分（Mauboussin 框架）

| 维度 | 得分 | 核心信号 |
|------|------|---------|
| **B — Behavioral** | X/3 | [1句] |
| **A — Analytical** | X/3 | [1句] |
| **I — Informational** | X/3 | [1句] |
| **T — Technical** | X/3 | [1句] |

**总评：X/12 — [强/中/弱]错误定价信号**

---

## 三、技术面（SEPA）
**当前价：$X | MA50：$X | MA150：$X | MA200：$X**

| # | 条件 | 状态 |
|---|------|------|
[8条趋势模板]

**趋势模板得分：X/8 | Stage：X**
- **关键阻力：** $X → $X → $X
- **关键支撑：** $X → $X

---

## 四、财务快照

### 季度营收（最近5季）
| 季度 | 营收 | 毛利润 | 毛利率 | QoQ |
|------|------|--------|--------|-----|
[表格]

### 关键指标
| 指标 | 数值 | 备注 |
|------|------|------|
| 营收 YoY | X% | |
| 毛利率 | X% | |
| FCF（TTM）| $XM | [蓝筹：FCF Margin X%] |
| 市值 | $XB | |
| 分析师数量 | X名 | |
| 分析师均价目标 | $X | +X% |

---

## 五、类型专项

### [🏦 蓝筹] 护城河 + FCF + 估值
*护城河类型：[网络效应/转换成本/成本优势/无形资产]*
- **FCF TTM：** $XB（Margin X%）| 5年 CAGR +X%
- **估值：** P/FCF Xx（vs 5年均 Xx）| EV/EBITDA Xx（vs 历史 Xx）
- **资本分配：** 股息 X% + 回购 $XB TTM
- **LTCG 建议：** [LTCG 账户/Roth IRA 优先]

### [🚀 翻倍] 稀释 + 跑道 + 催化剂
- **稀释风险：** [低/中/高] — [1句理由]
- **现金跑道：** X个月 — [✅/⚠️/🔴]
- **催化剂日历：** [列表]
- **空头挤压：** X% float，Days to Cover X天

### [⚡ 动量] 赛道强度 + RS + 移动止损参考
- **Chen 7日信号：** X次 | **赛道 ETF vs MA50：** +/-X%
- **RS vs 龙头：** +X% vs +X%
- **移动止损参考：** 近10日高 $X - 1.5×ATR $X = $X

---

## 六、风险
| 风险 | 级别 | 说明 |
|------|------|------|
[按类型列出关键风险]

---

## 七、综合结论

**综合评定：[🔥 强烈关注 / ⭐ 关注候选 / 👀 观察 / ❌ 回避]**
**股票类型：[🏦 蓝筹长持 / 🚀 翻倍候选 / ⚡ 热赛道动量]**

**核心 thesis：** [2-3句]

**[蓝筹] 5年持有场景：** $X → $X（+X%，基于护城河维持 + FCF 增长）
**[翻倍] 翻倍路径：** 触发事件 [YYYY-MM] → T1 $X（+X%）→ T2 $X（+X%）
**[动量] 热度窗口：** 赛道热度预计持续 [X个月] → 目标 $X → 移动止损 $X

**入场等待条件：**
1. [最关键条件]
2. [次要条件]

**若上述条件满足 → 运行 `/stock-entry [TICKER]`**

---

*数据来源：yfinance（YYYY-MM-DD）、WebSearch*
*框架：Mauboussin BAIT | Minervini SEPA*
```
