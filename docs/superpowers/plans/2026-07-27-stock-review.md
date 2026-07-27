# /stock-review 交易复盘闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立交易复盘闭环——positions.md 交易日志 + `/stock-review` 复盘 skill + wiki/lessons.md 教训库 + stock-entry/exit 教训检查。

**Architecture:** 纯 markdown skill 工程，无 Python 代码改动。`/stock-review` 读三层快照文件（analysis/entry/exit）+ positions.md 成交记录，用 yfinance 临时脚本拉事后走势验证预测，三层打分（分析质量/纪律执行/结果），教训写入 lessons.md；stock-entry/exit 决策前必读 lessons.md 输出重犯警告。

**Tech Stack:** Claude Code commands（`.claude/commands/*.md`）、yfinance（已装）、现有 `scripts/ticker_scan.py`（不改）。

**Spec:** `docs/superpowers/specs/2026-07-27-stock-review-design.md`

## Global Constraints

- 不修改 `scripts/ticker_scan.py`、不新建常驻 Python 脚本（事后走势用临时 `python -c` 调 yfinance）
- 不做券商对接、不做定时任务、不自动改 `wiki/frameworks/*.md`
- 所有新文件 UTF-8；命令文件风格对齐现有 `.claude/commands/*.md`（中文、Steps 编号、输出模板代码块）
- 教训条目格式固定：`- [L编号] 日期 ticker | 类型/子类 | 规则一句话 | 来源 | ×重犯计数`
- 一轮交易 = positions.md 中某 ticker 从 BUY 到持仓清零的 SELL

---

### Task 1: positions.md 交易日志（格式 + 历史成交种子）

**Files:**
- Modify: `data/positions.md`（当前为空文件）

**Interfaces:**
- Produces: 交易日志表格式（列：日期/Ticker/动作/价格/股数/关联文件/备注），Task 3 的 stock-review.md 按此格式解析

- [ ] **Step 1: 写入交易日志内容**

用 Write 覆盖 `data/positions.md`（文件为空，无需保留内容）：

```markdown
# 交易日志

> 真实成交后立即记一行（或让 Claude 记）。**没记录的交易不能复盘——这是纪律的一部分。**
> - 动作：`BUY` / `SELL`（分批交易记多行）
> - 关联文件：指向 `data/tickers/<TICKER>/` 下的 entry/exit 快照；无快照填 `—`（复盘时记为「记录/无分析入场」教训）
> - 一轮交易 = 从 BUY 到持仓清零的 SELL；`/stock-review <TICKER>` 默认复盘最近一轮已平仓交易

| 日期 | Ticker | 动作 | 价格 | 股数 | 关联文件 | 备注 |
|------|--------|------|------|------|---------|------|
| 2026-06-15 | ABAT | BUY | 4.25 | 100 | entry-2026-06-15.md | 违纪：entry 分析判 Stage 1 不入场，仍入场（推断自 exit 文件，待确认）|
| 2026-06-15 | ABAT | SELL | 3.39 | 100 | exit-2026-06-15.md | 止损清仓（推断自 exit 文件，待确认）|
| 2026-06-17 | INTT | BUY | 18.00 | 100 | entry-2026-06-17.md | 持仓中（推断自 exit 文件，待确认）|
```

- [ ] **Step 2: 验证格式**

Run: `python -c "import io; t=io.open('data/positions.md',encoding='utf-8').read(); assert '| 2026-06-15 | ABAT | BUY | 4.25 | 100 |' in t and '| INTT | BUY | 18.00 |' in t; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add data/positions.md
git commit -m "feat(data): positions.md 交易日志格式 + ABAT/INTT 历史成交种子"
```

---

### Task 2: wiki/lessons.md 教训库骨架

**Files:**
- Create: `wiki/lessons.md`

**Interfaces:**
- Produces: 教训条目格式与类型标签集。Task 3（stock-review 追加条目）、Task 4/5（entry/exit 读取检查）依赖此格式

- [ ] **Step 1: 写入教训库骨架**

用 Write 创建 `wiki/lessons.md`：

```markdown
# 交易教训库

> 由 `/stock-review` 复盘追加；`/stock-entry` 与 `/stock-exit` 决策前必读本文件做重犯检查。
> 人工也可手动补充条目。框架级修订（改 `wiki/frameworks/*.md`）由人工决定，本文件不自动改框架。

## 条目格式

```
- [L编号] 日期 ticker | 类型/子类 | 规则一句话 | 来源 | ×重犯计数
```

- 编号从 L001 递增，只增不删；教训被推翻时在行尾加 `（已废弃：原因)`
- 同类教训再次出现：不新增条目，原条目重犯计数 +1 并在行尾追加 `; 重犯: 日期 ticker`

## 类型标签

| 类型 | 子类示例 |
|------|---------|
| 纪律 | Stage违规、止损不执行、仓位超标、追高超买入区 |
| 分析 | EV过度自信、催化剂误判、止损位太紧、Bear情景低估 |
| 记录 | 无分析入场（positions.md 有成交但无 entry 快照）|

## 教训条目

（暂无——首次 `/stock-review` 后生成）
```

注意：文件内嵌套的三反引号代码块与外层冲突时，实际写入用上述内容原样（内层格式块用缩进或保持 ``` 均可，以渲染可读为准）。

- [ ] **Step 2: 验证**

Run: `python -c "import io; t=io.open('wiki/lessons.md',encoding='utf-8').read(); assert '类型标签' in t and 'L编号' in t; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add wiki/lessons.md
git commit -m "feat(wiki): lessons.md 教训库骨架（格式 + 类型标签）"
```

---

### Task 3: /stock-review skill（模式 A 单笔 + 模式 B 汇总）

**Files:**
- Create: `.claude/commands/stock-review.md`

**Interfaces:**
- Consumes: Task 1 positions.md 表格式；Task 2 lessons.md 条目格式
- Produces: `data/tickers/<TICKER>/review-YYYY-MM-DD.md`（模式 A）、`data/reviews/summary-YYYY-MM-DD.md`（模式 B）；lessons.md 新条目

- [ ] **Step 1: 写入 skill 文件**

用 Write 创建 `.claude/commands/stock-review.md`：

````markdown
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
````

- [ ] **Step 2: 验证文件结构**

Run: `python -c "import io; t=io.open('.claude/commands/stock-review.md',encoding='utf-8').read(); assert '模式 A' in t and '模式 B' in t and '三层打分' in t and 'lessons.md' in t; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/stock-review.md
git commit -m "feat(skill): /stock-review 交易复盘（单笔三层打分 + ALL 横向汇总）"
```

---

### Task 4: stock-entry.md 教训检查步骤

**Files:**
- Modify: `.claude/commands/stock-entry.md`（在「### 1. 读取分析报告」之前插入）

**Interfaces:**
- Consumes: Task 2 lessons.md 条目格式

- [ ] **Step 1: 插入教训检查步骤**

用 Edit，old_string：

```markdown
## Steps

### 1. 读取分析报告
```

new_string：

```markdown
## Steps

### 0. 教训检查（必做）

读 `wiki/lessons.md` 的「教训条目」节，逐条对照本次入场决策。命中任何一条（如标的当前 Stage 与教训冲突、仓位/止损方式重蹈覆辙）→ 在最终输出的**显著位置**列出：

> ⚠️ 教训警告 [L00X]：<规则原文>。本次决策冲突点：<具体说明>

警告不阻断流程，但必须显示。lessons.md 不存在或无条目 → 跳过本步。

---

### 1. 读取分析报告
```

- [ ] **Step 2: 同步输出模板**

用 Edit 在 entry 输出模板「## 当前状态」块尾部加一行。old_string：

```markdown
- PW EV 对照：现价 $X vs EV×0.85 = $X → [✅ 可入 / ❌ 不追]
```

new_string：

```markdown
- PW EV 对照：现价 $X vs EV×0.85 = $X → [✅ 可入 / ❌ 不追]
- 教训检查：[✅ 无命中 / ⚠️ 命中 L00X（见下方警告）]
```

- [ ] **Step 3: 验证**

Run: `python -c "import io; t=io.open('.claude/commands/stock-entry.md',encoding='utf-8').read(); assert '### 0. 教训检查' in t and '教训警告 [L00X]' in t and t.count('教训检查') >= 2; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/stock-entry.md
git commit -m "feat(skill): stock-entry 决策前读 lessons.md 重犯检查"
```

---

### Task 5: stock-exit.md 教训检查步骤

**Files:**
- Modify: `.claude/commands/stock-exit.md`（在「### 1. 读取入场信息」之前插入）

**Interfaces:**
- Consumes: Task 2 lessons.md 条目格式

- [ ] **Step 1: 插入教训检查步骤**

用 Edit，old_string：

```markdown
## Steps

### 1. 读取入场信息
```

new_string：

```markdown
## Steps

### 0. 教训检查（必做）

读 `wiki/lessons.md` 的「教训条目」节，逐条对照本次持仓决策（常见命中：止损不执行、到止盈位不减仓、论文破坏仍持有）。命中 → 在最终输出的**显著位置**列出：

> ⚠️ 教训警告 [L00X]：<规则原文>。本次决策冲突点：<具体说明>

警告不阻断流程，但必须显示。lessons.md 不存在或无条目 → 跳过本步。

---

### 1. 读取入场信息
```

- [ ] **Step 2: 同步输出模板**

用 Edit 在 exit 输出模板「## 建议行动」之前加教训行。old_string：

```markdown
## 建议行动
[持有 / 减仓至 X% / 触发自由股规则（卖50%）/ 全部清仓] — 理由：[1句]
```

new_string：

```markdown
## 教训检查
[✅ 无命中 / ⚠️ 教训警告 L00X：<冲突点>]

## 建议行动
[持有 / 减仓至 X% / 触发自由股规则（卖50%）/ 全部清仓] — 理由：[1句]
```

- [ ] **Step 3: 验证**

Run: `python -c "import io; t=io.open('.claude/commands/stock-exit.md',encoding='utf-8').read(); assert '### 0. 教训检查' in t and t.count('教训') >= 3; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/stock-exit.md
git commit -m "feat(skill): stock-exit 决策前读 lessons.md 重犯检查"
```

---

### Task 6: 文档同步（README + workflow-guide）

**Files:**
- Modify: `README.md`（Skills 表加一行）
- Modify: `docs/workflow-guide.md`（流程图与末尾加第五步）

- [ ] **Step 1: README skills 表加行**

用 Edit，old_string：

```markdown
| `/stock-exit <TICKER>` | 止盈条件、减仓逻辑 |
```

new_string：

```markdown
| `/stock-exit <TICKER>` | 止盈条件、减仓逻辑 |
| `/stock-review <TICKER\|ALL>` | 平仓后复盘：三层打分（分析/纪律/结果），教训入 `wiki/lessons.md` |
```

- [ ] **Step 2: workflow-guide 流程图更新**

用 Edit，old_string：

```
/stock-exit TICKER      ← 管理：什么时候减仓？什么时候止损？
```

new_string：

```
/stock-exit TICKER      ← 管理：什么时候减仓？什么时候止损？
      ↓
/stock-review TICKER    ← 复盘：分析对吗？纪律守了吗？教训进 lessons.md
```

再在文件末尾追加（用 Edit 或读尾部后 append）：

```markdown

---

## 第五步：复盘 — `/stock-review`

平仓后跑 `/stock-review TICKER`：三层打分（**分析质量 / 纪律执行 / 结果** 分开评，避免用盈亏倒推分析对错）；教训写入 `wiki/lessons.md`，下次 `/stock-entry`、`/stock-exit` 决策前自动做重犯检查。定期跑 `/stock-review ALL` 看重复错误模式。

前提：真实成交要记在 `data/positions.md`（没记录的交易不能复盘）。
```

- [ ] **Step 3: 验证**

Run: `python -c "import io; a=io.open('README.md',encoding='utf-8').read(); b=io.open('docs/workflow-guide.md',encoding='utf-8').read(); assert 'stock-review' in a and b.count('stock-review') >= 2; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add README.md docs/workflow-guide.md
git commit -m "docs: README/workflow-guide 加入 /stock-review 第五步"
```

---

### Task 7: 验收运行（spec 验收标准 1-3）

**Files:**
- Create（由 skill 运行产出）: `data/tickers/ABAT/review-*.md`、`data/reviews/summary-*.md`
- Modify（由 skill 运行产出）: `wiki/lessons.md`

- [ ] **Step 1: 跑 `/stock-review ABAT`**

按 `.claude/commands/stock-review.md` 模式 A 完整执行（读快照 → 拉 ABAT 事后日线 → 预测验证 → 三层打分 → 写报告 + lessons）。
Expected：`data/tickers/ABAT/review-<今日>.md` 存在；三层打分 = 分析✅ / 纪律❌ / 结果❌；`wiki/lessons.md` 出现 `[L001] ... 纪律/Stage违规`

- [ ] **Step 2: 跑 `/stock-review ALL`**

Expected：`data/reviews/summary-<今日>.md` 存在；含 1 轮已复盘（ABAT）、INTT 列入持仓中、重复错误模式表含 纪律/Stage违规 ×1

- [ ] **Step 3: 教训警告 spot check**

对 ABAT 模拟执行 `/stock-entry ABAT` 的 Step 0（只做教训检查，不产出完整入场计划）：读 lessons.md + 跑 `python scripts/ticker_scan.py ABAT --mode full --json` 判断当前 Stage。
Expected：若 ABAT 仍非 Stage 2，输出含 `⚠️ 教训警告 [L001]`

- [ ] **Step 4: Commit**

```bash
git add data/tickers/ABAT/ data/reviews/ wiki/lessons.md
git commit -m "feat(review): ABAT 首轮复盘 + ALL 汇总（验收 /stock-review 闭环）"
```
