# stock-analyze

对个股做基本面 + 技术面深度分析，基于 BAIT 框架评分，输出分析报告。

## Arguments

Required: `<TICKER>` — 股票代码（如 `POET`, `NVDA`）

## 框架依据

读取 `wiki/frameworks/bait.md` 了解评分标准。
读取 `wiki/frameworks/sepa.md` 了解技术面判断标准。

## Steps

### 1. 拉取基本数据（yfinance）

用 yfinance 获取以下数据：
- 公司简介（行业、市值、员工数）
- 财务报表：近 4 季营收、净利润、毛利率
- 关键指标：P/E、P/S、营收 YoY 增速
- 分析师评级：共识评级、目标价区间

```python
import yfinance as yf
t = yf.Ticker("TICKER")
info = t.info
financials = t.quarterly_financials
```

### 2. 技术面数据（yfinance）

```python
hist = t.history(period="1y")
# 计算 50MA、150MA、200MA、当前价 vs 各 MA 的百分比
```

### 3. BAIT 基本面评分（参考 wiki/frameworks/bait.md）

| 维度 | 问题 | 评分 (0-3) |
|------|------|-----------|
| B — Business | 商业模式清晰？护城河？ | |
| A — Addressable Market | TAM $10B+？多年结构性需求？ | |
| I — Industry Tailwind | 行业顺风？监管/宏观支持？ | |
| T — Technical Setup | SEPA Stage 2？趋势模板 ≥5/8？ | |

总分 0–12，≥8 为强基本面。

### 4. SEPA 技术面评估（参考 wiki/frameworks/sepa.md）

判断：
- 当前处于哪个 Stage（1/2/3/4）
- 价格 vs 50MA / 150MA / 200MA
- 是否有明确入场形态（VCP / 杯柄 / 平台突破）
- 趋势模板得分（8 项中几项通过）

### 5. WebSearch 补充

搜索：`"[TICKER] earnings revenue growth 2025 2026 analyst"`
提取：最新财报亮点、分析师观点、近期催化剂。

### 6. 输出报告

保存到 `wiki/tickers/[TICKER]/analysis.md`：

```markdown
# [TICKER] 分析报告 — YYYY-MM-DD

## 公司简介
[行业、市值、核心业务一句话]

## BAIT 评分
| B | A | I | T | 总分 |
|---|---|---|---|------|
| X | X | X | X | X/12 |

[每项1-2句评分依据]

## 技术面（SEPA）
- Stage: [1/2/3/4]
- 趋势模板: X/8
- 价格 vs 50MA: +X%
- 形态: [VCP / 平台 / 无明确形态]

## 财务快照
| 指标 | 数值 |
|------|------|
| 营收 YoY | X% |
| 毛利率 | X% |
| 市值 | $XM |

## 近期催化剂
[1-3条]

## 结论
[一句话：强/中/弱，以及最关键的买入/观察/回避理由]
下一步：`/stock-entry [TICKER]`
```
