# stock-review

对过去的交易做事后复盘：当时的分析对不对（分析质量）、有没有按分析执行（纪律）、结果如何（盈亏 + 预测兑现）。教训写入 `wiki/lessons.md` 形成闭环。

## Arguments

Required: `<TICKER>` 或 `ALL`
Optional: `--date YYYY-MM-DD` — 指定复盘哪一轮交易（按该轮 BUY 日期；默认最近一轮已平仓交易）

---

## 模式 A：`/stock-review TICKER`（单笔深度复盘）

### 1. 读当时判断

- `data/positions.md` — 该 ticker 全部成交行；确定复盘轮次（BUY→持仓清零的 SELL）。**无成交记录 → 停止**，提示先补 positions.md
- `data/tickers/[TICKER]/entry-*.md`、`exit-*.md` — 该轮对应快照（按关联文件列 / 日期就近匹配）。无 entry 快照 → 继续复盘，但直接记教训「记录/无分析入场」
- `wiki/tickers/[TICKER]/analysis.md` — 当时的 BAIT / SEPA Stage / Moneyball EV 情景

### 2. 拉事后走势

```bash
python scripts/ticker_scan.py TICKER --mode full --json
```

再拉决策日→今天的日线（临时脚本，起点=该轮 BUY 日往前推 30 天，便于看入场前形态）：

```bash
python -c "
import yfinance as yf, sys
sys.stdout.reconfigure(encoding='utf-8')
h = yf.Ticker('TICKER').history(start='YYYY-MM-DD', interval='1d')
for d, r in h.iterrows():
    print(d.date(), round(r['Close'],2), int(r['Volume']))
"
```

### 3. 验证可验证预测

逐条对照当时文件里的预测，标 ✅兑现 / ❌证伪 / ⏳未到期：

| 预测 | 验证方法 |
|------|---------|
| Stage 判断 | 决策日后走势是否符合当时 Stage 定性（如判 Stage 1 → 后续确实横盘/下行？）|
| 止损位质量 | 若被打掉：打掉后 20 个交易日内 V 型反弹收复（止损太紧）还是继续跌（止损正确）|
| EV 情景 | 现价落在 Bull/Base/Bear 哪个轨道；当时概率给得是否靠谱 |
| 催化剂 | 预告的事件（财报/合同/政策）是否如期发生、方向对不对 |
| 目标价 | T1/T2 是否到达过 |

### 4. 三层打分

每层 ✅/⚠️/❌ + 一句理由：

| 层 | 评什么 | 与结果无关性 |
|----|--------|------------|
| **分析质量** | 数据对不对、框架（BAIT/SEPA/Moneyball）用得对不对、预测兑现率 | 不看盈亏 |
| **纪律执行** | 实际成交 vs 分析建议：入场时机/价位、仓位、止损执行、减仓节奏 | 不看盈亏 |
| **结果** | 该轮盈亏金额与 %、持仓天数 | 只看盈亏 |

> 四象限解读：分析✅纪律✅结果❌ = 正常亏损（过程对，接受）；分析❌结果✅ = 运气（危险，勿强化）；纪律❌ = 无论结果都要记教训。

### 5. 输出报告

保存到 `data/tickers/[TICKER]/review-[YYYY-MM-DD].md`（日期=复盘日）：
> 产出属私有交易数据（`.gitignore` 已排除 `data/` 相关路径），**勿 commit**。

```markdown
# [TICKER] 交易复盘 — YYYY-MM-DD

## 复盘轮次
- BUY YYYY-MM-DD $X ×N股 → SELL YYYY-MM-DD $X ×N股
- 盈亏：$X（±X%）| 持仓 X 天
- 关联：entry-*.md / exit-*.md / analysis.md（日期）

## 预测验证
| 预测（出处） | 当时判断 | 实际走势 | 裁决 |
|------|---------|---------|------|
| Stage（entry）| ... | ... | ✅/❌/⏳ |
| 止损位（entry）| $X | 打掉后... | ✅/❌ |
| EV 情景（analysis）| Bull $X/Base $X/Bear $X | 现价 $X 落在... | ... |
| 催化剂（analysis）| ... | ... | ... |

## 三层打分
| 层 | 评分 | 理由 |
|----|------|------|
| 分析质量 | ✅/⚠️/❌ | [1句] |
| 纪律执行 | ✅/⚠️/❌ | [1句] |
| 结果 | ✅/⚠️/❌ | [1句] |

## 教训
- [新教训 → 已追加 lessons.md L00X / 重犯 → L00X 计数+1 / 无新教训]

## 下一步
- [重入条件 / watchlist / 无]
```

### 6. 教训写入

- 新教训：按 lessons.md 条目格式追加，编号顺延，来源填 `review`
- 与既有条目同类：不新增，原条目 `×N` 计数 +1 并加 `; 重犯: 日期 ticker`

---

## 模式 B：`/stock-review ALL`（横向模式汇总）

### 1. 盘点

- 扫 `data/tickers/*/review-*.md` 全部单笔复盘
- 扫 `data/positions.md` 全部已平仓轮次；**未复盘的已平仓轮次列清单**，建议先跑单笔（不强制阻断）
- 未平仓持仓单独列出（不参与胜率统计）

### 2. 横向统计

- 胜率 = 盈利轮次 / 已复盘平仓轮次；盈亏比 = 平均盈利 / 平均亏损
- 三层打分分布（各层 ✅/⚠️/❌ 计数）
- **重复错误模式**：按 lessons.md 类型标签聚类（如「3 次亏损中 2 次为 纪律/Stage违规」）
- 四象限统计：过程对结果差（正常）vs 过程错结果好（运气，重点警示）

### 3. 输出

保存到 `data/reviews/summary-[YYYY-MM-DD].md`：
> 产出属私有交易数据（`.gitignore` 已排除 `data/` 相关路径），**勿 commit**。

```markdown
# 交易复盘汇总 — YYYY-MM-DD

## 总览
- 已复盘轮次：X | 胜率：X% | 盈亏比：X | 总盈亏：$X
- 未复盘的已平仓轮次：[清单或 无]
- 持仓中：[清单]

## 三层打分分布
| 层 | ✅ | ⚠️ | ❌ |
|----|----|----|----|

## 重复错误模式
| 类型 | 次数 | 涉及 | 对应教训 |
|------|------|------|---------|

## 建议
- [最高频错误 → 建议动作（如：考虑将 L00X 升级为框架硬规则，人工修订 frameworks/）]
```
