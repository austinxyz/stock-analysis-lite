# /stock-review 真实案例 — MXL（分析质量复盘）

`/stock-review analysis MXL` 的完整真实产出。这不是编出来的教学素材——它记录了一次真实发生的「数据质量事故 → 错误判断 → 事后复盘 → skill 改进」闭环，也正是 `/stock-review` 这个 skill 诞生的直接原因。

---

## 一、由来：一次数据质量事故

**2026-07-26（周日）**，对 MXL 跑 `/stock-entry`，得到的结论是：

> 现价 $91.24，Stage 2 健康趋势，趋势模板 7/8，PW EV 检查通过（$91.24 < EV×0.85 = $98.39）→ **现在可入**

问题是：**$91.24 是 7/23（周四）的收盘价**。7/24（周五）MXL 财报后单日暴跌 -17.9%，真实收盘 $74.92——entry 分析生成时这天早已收盘，但判断完全没有反映它。

根因不在框架，在数据层：yfinance 偶尔延迟发布最近一个交易日的日线，当时的 `scripts/ticker_scan.py` 对缺失日线做了**静默丢弃回退**——没有任何标记，脚本"正常"输出了滞后 1 个交易日、偏高约 21.8% 的价格。Stage 判断、趋势模板、EV 安全边际，全部建立在这个被污染的锚点上。

用户是在 Yahoo Finance 上人工核对时才发现「previous close 对不上」。

## 二、修复 + 引出 review skill

事故触发了两件事：

1. **数据层修复**：`ticker_scan.py` 新增 `price_bar_date` / `latest_bar_missing` / `live_price` 字段——缺最新 K 线时不再静默回退，而是显式暴露信号（详见 `scripts/ticker_scan_guide.md` 的「日线数据延迟发布」章节）。
2. **流程层反思**：判断错了一次不可怕，可怕的是**没有机制发现它错了**。于是提出：需要一个 review skill，事后复盘历史分析文档的质量，把教训沉淀回 4 个分析 skill（`/ticker-scan`、`/stock-analyze`、`/stock-entry`、`/stock-exit`）。

这就是 `/stock-review` 的两种模式：
- **`analysis`（评工具）**：当时 skill 给的判断事后对不对？框架有没有系统性偏差？→ 改进建议进 `wiki/skill-improvements.md`
- **`trade`（评人）**：实际买卖是否守纪律？→ 教训进 `wiki/lessons.md`

## 三、实际效果：这次复盘抓到了什么

7/27 跑 `/stock-review analysis MXL`（产出即本目录的 `review-analysis-2026-07-27.md`），结果：

| 发现 | 类型 | 结论 |
|------|------|------|
| 入场判断基于滞后 1 日、偏高 21.8% 的价格 | 数据/口径错误 | ❌ 本轮最大问题；若用真实价 $74.92，大概率不会给出「现在可入」 |
| Bear 情景 $68 被现价 $63.82 跌破 | 分析/Bear情景低估 | ❌ 现实比最悲观情景更差，EV 框架对「财报超预期反而暴跌」尾部覆盖不足 |
| 止损位 $72.99 被 gap-down 跌破后无 V 型反弹 | — | ✅ 止损设置方向正确（该跌就没回头），滑点属已知 gap-down 规则覆盖范围 |
| analysis.md 同路径覆盖、历史版本无法追溯 | 流程 | ⚠️ 建议改按日期存档，与 entry/exit 一致 |

沉淀出的 3 条 skill 改进建议（见 review 文件「框架改进建议」节）：

1. **【最高优先级】** `/stock-entry` 与 `/stock-analyze` 补数据延迟检查：`latest_bar_missing==true` 时强制用 `live_price` 重评，不得直接用滞后 `price`（数据层已修，决策层 skill 当时还没跟上）
2. Moneyball Bear 情景对高估值+已现抛售信号的标的需预留更大下行空间
3. `analysis.md` 改为按日期存档制

复盘同时暴露了一个自证的教训：7/26 原版 `analysis.md` 已被 7/27 版本覆盖，复盘只能从引用片段还原原始判断——**改进建议 3 正是被这次复盘自己的困境证明的**。

## 四、本目录文件

| 文件 | 角色 |
|------|------|
| `entry-2026-07-26.md` | 事故现场：基于污染数据给出「现在可入」的入场计划 |
| `exit-2026-07-26.md` | 同日持仓评估快照 |
| `review-analysis-2026-07-27.md` | 复盘产出：预测验证 + 框架校准扫描 + 3 条改进建议 |

## 五、相关文件（repo 内）

- `.claude/commands/stock-review.md` — review skill 本体（两模式）
- `scripts/ticker_scan_guide.md` — 数据延迟兜底字段说明（事故的修复产物）
- `wiki/lessons.md` — 教训库；「静默失效」类型标签（机制豁免/复审逾期/触发器设计/口径错误）即源自此类案例
- `wiki/skill-improvements.md` — 框架改进建议库（analysis 模式的沉淀去向）

> 实际使用中，entry/exit/review 文件位于 `data/tickers/<TICKER>/`（被 `.gitignore` 排除的私有目录）；本目录是不含真实成交记录的教学示例。
