# 框架/Skill 改进建议库

> 由 `/stock-review analysis` 复盘追加。记的是**分析方法/框架本身**可能存在的系统性问题，不是交易纪律（那是 `wiki/lessons.md`）。
> 本文件只记录建议，**不自动修改** `wiki/frameworks/*.md` 或 `.claude/commands/*.md`——是否采纳、如何改，由人工决定。

## 条目格式

```
- [S编号] 日期 ticker | 涉及文件/规则 | 问题描述 | 建议动作 | 来源 | ×重复出现计数
```

- 编号从 S001 递增，只增不删；建议被采纳并已修改框架后，行尾加 `（已采纳：YYYY-MM-DD 改了什么）`
- 同类建议再次出现：不新增条目，原条目重复计数 +1 并追加 `; 重复: 日期 ticker`

## 问题类型

| 类型 | 说明 |
|------|------|
| 触发器设计 | 论点破裂条件锚定错了对象（如该锚事件却锚了价格阈值）|
| 复审时效 | analysis.md 长期未更新但基本面/价格已大幅变化 |
| 参数校准 | 框架里的具体数值（止损倍数、EV情景概率等）在多次复盘中系统性偏离实际 |
| 数据口径 | 脚本/数据源口径不一致导致判断输入被污染（非框架逻辑问题，修脚本不改框架）|

## 建议条目

- [S001] 2026-07-27 MXL | `.claude/commands/stock-entry.md`、`.claude/commands/stock-analyze.md` | 两个skill的Step1拉数据后未检查`latest_bar_missing`/`live_price`字段，导致entry-2026-07-26.md基于滞后1个交易日、偏高21.8%的价格（7/23收盘$91.24而非真实7/24收盘$74.92）做出"现在可入"判断（`scripts/ticker_scan.py`当时对缺失日线静默回退，本session内已在数据层修复但决策层skill未跟上）| 补一段：若`latest_bar_missing==true`，强制改用`live_price`重新评估入场条件/技术面判断 | review | ×1
- [S002] 2026-07-27 MXL | Moneyball情景框架（`stock-analyze.md`第六节）| Bear情景目标价$68被现价$63.82跌破，对"forward P/E已显著偏高+近期已有系统性抛售信号"的标的，Bear情景锚定"回归历史估值中位数"不够，低估了"基本面质疑引发恐慌性抛售"的尾部风险 | 此类标的Bear目标再下修10-15%或Bear概率上调 | review | ×1
- [S003] 2026-07-27 MXL | `wiki/tickers/[TICKER]/analysis.md` 存档方式 | 当前同路径直接覆盖，历史判断（7/26原版本）无法追溯，本次复盘只能从7/27版本的对比引用片段还原 | 改为按日期存档（`analysis-YYYY-MM-DD.md`）或覆盖前先归档到changelog.md，与entry/exit的命名规则保持一致 | review | ×1
