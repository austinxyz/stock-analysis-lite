# 交易复盘闭环（/stock-review）设计文档

**日期：** 2026-07-27
**状态：** 已批准（brainstorming 决策见下）
**目标：** 对过去的 entry/exit 决策做事后复盘——当时的分析对不对、纪律有没有执行、教训如何进入未来决策闭环。

---

## 背景与动机

现有流水线：`/ticker-scan` → `/stock-analyze`（wiki/tickers/X/analysis.md）→ `/stock-entry`（data/tickers/X/entry-日期.md）→ `/stock-exit`（data/tickers/X/exit-日期.md）。

三层文件是天然的「当时判断」快照，但缺三样：

1. **真实成交记录** — `data/positions.md` 为空，无法对照「分析说什么」vs「实际做了什么」
2. **事后验证器** — 没有工具回头检查 Stage 判断、EV 情景、止损位是否被后续走势验证
3. **教训闭环** — ABAT 案例：exit 文件里写了教训「Stage 1 不入场」，但下次 `/stock-entry` 不读它，教训不生效

## 已定决策（brainstorming 结论）

| 决策点 | 结论 |
|--------|------|
| 评判基准 | 过程+结果双轨：分析质量 / 纪律执行 / 结果 三层分开打分 |
| 成交数据源 | 把 `data/positions.md` 用起来做手动交易日志；没记录的交易不能复盘 |
| 触发方式 | 手动：`/stock-review TICKER` 单笔深度 + `/stock-review ALL` 横向汇总 |
| 教训闭环 | `wiki/lessons.md` 全局教训库 + 改造 stock-entry/stock-exit 决策前必读 |

---

## 一、数据层：positions.md 交易日志

格式（追加式表格，一行一笔成交）：

```markdown
# 交易日志

| 日期 | Ticker | 动作 | 价格 | 股数 | 关联文件 | 备注 |
|------|--------|------|------|------|---------|------|
| 2026-06-15 | ABAT | BUY | 4.25 | 100 | entry-2026-06-15.md | 违纪：Stage 1 入场 |
| 2026-06-15 | ABAT | SELL | 3.39 | 100 | exit-2026-06-15.md | 止损 |
```

- 动作枚举：`BUY` / `SELL`（分批用多行）
- `关联文件`指向 `data/tickers/<TICKER>/` 下的 entry/exit 快照；无快照的交易填 `—`（复盘时标注「无分析依据」，本身就是教训）
- 真实买卖后手动记录（或叫 Claude 记）；**没记录的交易不能复盘——这是纪律的一部分**

## 二、新 skill：`.claude/commands/stock-review.md`

### 模式 A：`/stock-review TICKER`（单笔深度复盘）

**输入：** ticker；可选 `--date YYYY-MM-DD` 指定复盘哪一轮交易（默认最近一轮已平仓交易；一轮 = BUY 到对应 SELL 清零）

**步骤：**

1. **读当时判断**：`wiki/tickers/X/analysis.md` + `data/tickers/X/entry-*.md` / `exit-*.md` + `data/positions.md` 中该 ticker 成交行
2. **拉事后走势**：`python scripts/ticker_scan.py X --mode full --json` 取现状；`yfinance` 拉决策日→今天的日线（临时脚本，无需改 ticker_scan.py）
3. **验证可验证预测**（逐条对照，✅/❌/⏳未到期）：
   - Stage 判断：决策日后走势是否符合当时的 Stage 定性
   - 止损位质量：若被打掉——打掉后是 V 型反弹（止损太紧）还是继续跌（止损正确）
   - EV 情景：Bull/Base/Bear 哪个在兑现，概率给得靠谱吗
   - 催化剂：预告的事件（财报/合同）是否如期发生、方向对不对
4. **三层打分**（每层 ✅/⚠️/❌ + 一句理由）：
   - **分析质量**：数据对不对、框架（BAIT/SEPA/Moneyball）用得对不对
   - **纪律执行**：实际成交 vs 分析建议（入场时机、仓位、止损执行）
   - **结果**：该轮盈亏 + 预测兑现率
5. **产出**：
   - 报告存 `data/tickers/X/review-日期.md`
   - 新教训（去重后）追加 `wiki/lessons.md`；已有同类教训则在该条目上加一次「重犯/验证」计数

### 模式 B：`/stock-review ALL`（横向模式汇总）

1. 扫 `data/tickers/*/review-*.md` 全部单笔复盘 + positions.md 全部已平仓轮次
2. 未复盘的已平仓轮次先提示（列清单，建议先跑单笔）
3. 横向统计：胜率、盈亏比、三层打分分布、**重复错误模式**（按 lessons.md 类型标签聚类，如「3 次亏损中 2 次为纪律/Stage违规」）
4. 报告存 `data/reviews/summary-日期.md`

## 三、教训库：wiki/lessons.md

```markdown
# 交易教训库

<!-- 格式：[编号] 日期 ticker | 类型/子类 | 规则一句话 | 来源 | 重犯计数 -->
- [L001] 2026-06-15 ABAT | 纪律/Stage违规 | Stage 1 入场无趋势保护，EV 再高也不豁免 | review | ×1
```

类型标签（初始集，可扩展）：
- `纪律/Stage违规`、`纪律/止损不执行`、`纪律/仓位超标`
- `分析/EV过度自信`、`分析/催化剂误判`、`分析/止损位太紧`
- `记录/无分析入场`（positions.md 有成交但无 entry 快照）

## 四、闭环改造：stock-entry.md / stock-exit.md

各加一个前置步骤（Step 0 之后、计算之前）：

> **教训检查**：读 `wiki/lessons.md`，逐条对照本次决策。命中任何一条 → 在输出显著位置列出 `⚠️ 教训警告 [L00X]：<规则>，本次决策与其冲突的点：<具体说明>`。警告不阻断流程，但必须显示。

## 五、不做的（YAGNI）

- 不做券商 API / CSV 对接（手动日志够用）
- 不自动修改 `wiki/frameworks/*.md`（教训进 lessons.md，框架修订人工决定）
- 不做定时任务 / 自动触发（手动跑）
- 不改 `scripts/ticker_scan.py`（历史价格用临时 yfinance 调用）

## 六、验收标准

1. positions.md 录入 ABAT 两笔历史成交后，`/stock-review ABAT` 产出 `data/tickers/ABAT/review-*.md`：三层打分 = 分析✅/纪律❌/结果❌，且 lessons.md 出现 Stage违规 条目
2. `/stock-review ALL` 在 ≥2 个 ticker 有 review 后产出汇总报告，含重复模式统计
3. 改造后 `/stock-entry` 对一只 Stage 1 股票运行时，输出中出现 `⚠️ 教训警告 [L001]`

## 七、涉及文件清单

| 文件 | 动作 |
|------|------|
| `data/positions.md` | 定义格式 + 录入 ABAT/INTT 历史成交（用户提供或从 exit 文件推断后确认）|
| `.claude/commands/stock-review.md` | 新建（模式 A + B）|
| `wiki/lessons.md` | 新建（格式 + 种子条目）|
| `.claude/commands/stock-entry.md` | 加教训检查步骤 |
| `.claude/commands/stock-exit.md` | 加教训检查步骤 |
| `docs/`（如有 skill 索引/README）| 同步新 skill 说明 |
