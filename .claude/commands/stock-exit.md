# stock-exit

基于 Moneyball 框架，给出止盈条件、止损触发逻辑和减仓节奏。

## Arguments

Required: `<TICKER>` — 股票代码（如 `POET`, `NVDA`）

## 框架依据

读取 `wiki/frameworks/moneyball.md` 了解退出逻辑。
读取 `wiki/frameworks/sepa.md` 了解 Stage 退出信号。

## Steps

### 1. 读取入场信息

检查 `wiki/tickers/[TICKER]/entry-*.md`（最新一份）提取：
- 入场价、止损位、目标1、目标2
- 入场日期

如无入场文件，让用户提供入场价和止损价。

### 2. 拉取当前价格数据（yfinance）

```python
import yfinance as yf
t = yf.Ticker("TICKER")
hist = t.history(period="3mo")
# 当前价、50MA、200MA、近期成交量
```

### 3. 止损检查（参考 wiki/frameworks/moneyball.md）

硬止损触发条件（任一满足即止损）：
- [ ] 价格跌破止损位
- [ ] 价格收盘跌破 50MA（Stage 2 期间）
- [ ] 论文破坏：核心假设被证伪（如业绩暴雷、重大负面新闻）

**执行原则：** 止损是规则，不是讨论。触发即执行，不等待。

### 4. 止盈节奏（参考 wiki/frameworks/moneyball.md）

```
目标1到达（+15–20%）→ 减仓 50%，移动止损至成本价
目标2到达（+30–50%）→ 减仓至 25%，剩余跟随趋势
Stage 3 信号出现 → 剩余全部清仓
```

### 5. SEPA Stage 退出信号（参考 wiki/frameworks/sepa.md）

Stage 3 / Stage 4 信号（清仓）：
- 价格跌破 150MA
- 50MA 开始下穿 200MA
- 成交量放大下跌（分发信号）

### 6. WebSearch 论文检查

搜索：`"[TICKER] earnings revenue guidance 2025 2026"`
判断核心论文是否仍然成立：
- 营收增速是否维持？
- 行业催化剂是否有变化？
- 管理层是否下调指引？

### 7. 输出退出分析

保存到 `wiki/tickers/[TICKER]/exit-[YYYY-MM-DD].md`：

```markdown
# [TICKER] 退出分析 — YYYY-MM-DD

## 持仓状态
- 入场价：$X（YYYY-MM-DD）
- 当前价：$X（+X% / -X%）
- 硬止损：$X → [已触发 / 未触发]

## 止盈进度
| 目标 | 价位 | 状态 |
|------|------|------|
| 目标1（减50%）| $X | [已到达 / 未到达] |
| 目标2（减至25%）| $X | [已到达 / 未到达] |

## Stage 信号
- 当前 Stage：[2保持 / 3警告 / 4清仓]
- 50MA：$X（现价 +/-X%）
- 200MA：$X（现价 +/-X%）

## 论文状态
[核心假设是否仍成立，1-2句]

## 建议行动
[持有 / 减仓至X% / 全部清仓] — 理由：[1句]
```
