# stock-entry

基于 SEPA + Moneyball 框架，给出具体入场区间、止损位、仓位建议。

## Arguments

Required: `<TICKER>` — 股票代码（如 `POET`, `NVDA`）

## 框架依据

读取 `wiki/frameworks/sepa.md` 了解入场时机标准。
读取 `wiki/frameworks/moneyball.md` 了解非对称风险计算。

## Steps

### 1. 读取现有分析（如有）

检查 `wiki/tickers/[TICKER]/analysis.md` 是否存在，提取：
- 当前 Stage 和趋势模板得分
- 价格 vs 各 MA 数据
- 近期催化剂

如无此文件，先运行 `/stock-analyze [TICKER]`。

### 2. 拉取当前价格数据（yfinance）

```python
import yfinance as yf
t = yf.Ticker("TICKER")
hist = t.history(period="3mo")
# 计算：当前价、近期高低点、ATR（14日）、成交量均值
```

### 3. SEPA 入场确认（参考 wiki/frameworks/sepa.md）

检查入场条件：
- [ ] Stage 2 上升趋势（50MA > 150MA > 200MA，价格在 50MA 上方）
- [ ] 趋势模板 ≥5/8 通过
- [ ] 有明确轴心点（VCP / 杯柄 / 平台突破口）
- [ ] 成交量缩量整理（突破时需放量）

**入场区间：** 轴心点上方 0–3% 为理想入场区。

### 4. Moneyball 风险计算（参考 wiki/frameworks/moneyball.md）

计算非对称风险比：

```
止损位 = 轴心点下方 5–8%（或近期支撑位）
目标1 = +15–20%（第一目标，减半仓）
目标2 = +30–50%（第二目标，剩余仓位）

风险回报比 = (目标1 - 入场) / (入场 - 止损)
要求：R/R ≥ 2:1 才考虑入场
```

### 5. 仓位建议

```
标准仓位 = 总资金 × 2%（单笔最大亏损上限）
具体股数 = (总资金 × 2%) / (入场价 - 止损价)
```

说明：这是风险金额固定法（Kelly 简化版），确保单次止损不超过总资金 2%。

### 6. 输出入场分析

保存到 `wiki/tickers/[TICKER]/entry-[YYYY-MM-DD].md`：

```markdown
# [TICKER] 入场分析 — YYYY-MM-DD

## 当前状态
- 现价：$X
- Stage：[2 / 其他]
- 趋势模板：X/8
- 入场条件：[✅ 满足 / ⚠️ 部分满足 / ❌ 不满足]

## 入场方案
| 项目 | 价位 |
|------|------|
| 入场区间 | $X – $X |
| 止损位 | $X（-X%）|
| 目标1（减半仓）| $X（+X%）|
| 目标2（剩余）| $X（+X%）|
| 风险回报比 | X:1 |

## 仓位建议
假设总资金 $10,000，最大亏损 2%（$200）：
- 建议股数：约 X 股
- 占总资金：约 X%

## 关键催化剂
[触发上涨的事件/时间节点]

## 结论
[一句话：现在可入 / 等待形态 / 条件未满足]
下一步：入场后用 `/stock-exit [TICKER]` 管理退出。
```
