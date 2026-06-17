# stock-analyze

对翻倍候选股做深度基本面 + 技术面分析，判断市场是否存在错误定价以及翻倍路径是否清晰。

## Arguments

Required: `<TICKER>` — 股票代码（如 `ABAT`）

## Steps

### 1. 拉取量化数据（yfinance）

```python
import yfinance as yf
import pandas as pd

t = yf.Ticker("TICKER")
info = t.info

hist = t.history(period="1y")
price  = hist['Close'].iloc[-1]
ma50   = hist['Close'].rolling(50).mean().iloc[-1]
ma150  = hist['Close'].rolling(150).mean().iloc[-1]
ma200  = hist['Close'].rolling(200).mean().iloc[-1]
hi52   = hist['High'].rolling(252).max().iloc[-1]
lo52   = hist['Low'].rolling(252).min().iloc[-1]

# ATR-14
high_low   = hist['High'] - hist['Low']
high_close = abs(hist['High'] - hist['Close'].shift())
low_close  = abs(hist['Low']  - hist['Close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
atr14 = tr.rolling(14).mean().iloc[-1]
atr_pct = atr14 / price * 100

# 财务
qfin = t.quarterly_financials
qbal = t.quarterly_balance_sheet
revenue = qfin.loc['Total Revenue'] if 'Total Revenue' in qfin.index else None
gross   = qfin.loc['Gross Profit']  if 'Gross Profit'  in qfin.index else None
cash    = qbal.loc['Cash And Cash Equivalents'].iloc[0] if 'Cash And Cash Equivalents' in qbal.index else None

shares_out = info.get('sharesOutstanding', None)
short_pct  = info.get('shortPercentOfFloat', 0) * 100
float_sh   = info.get('floatShares', None)
market_cap = info.get('marketCap', 0)

print(f"价格={price:.2f}  市值={market_cap/1e9:.1f}B  ATR%={atr_pct:.1f}%")
print(f"MA50={ma50:.2f}  MA150={ma150:.2f}  MA200={ma200:.2f}")
print(f"52周高={hi52:.2f}  低={lo52:.2f}")
print(f"空头={short_pct:.1f}%  现金={cash/1e6:.1f}M" if cash else "")
```

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
| 8 | 相对强度 > 70百分位 | ✅/⚠️/❌ |

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

### 6. 综合结论

必须包含：
1. BAIT 结论（市场错在哪里，一句话）
2. 翻倍路径：什么事件 × 什么时间 × 目标价
3. 主要风险（2-3 条）
4. 入场等待条件（若 Stage 1：等哪几个信号才运行 `/stock-entry`）

---

### 7. 输出报告

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

## 六、风险
| 风险 | 级别 | 说明 |
|------|------|------|

---

## 七、结论

**评级：[🔥 强烈关注 / ⭐ 关注候选 / 👀 观察 / ❌ 回避]**

**核心 thesis：** [2-3句]

**翻倍路径：** [事件] YYYY-MM → T1 $X（+X%）→ T2 $X（+X%）

**入场等待条件：**
1. [最关键条件]
2. [次要条件]

**若条件满足 → 运行 `/stock-entry [TICKER]`**

---

*数据来源：yfinance（YYYY-MM-DD）、WebSearch*
*框架：Mauboussin BAIT | Minervini SEPA*
*上游：`/ticker-scan` | 下游：`/stock-entry [TICKER]`*
```
