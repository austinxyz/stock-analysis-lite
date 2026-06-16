# 框架综合指南 — 何时用哪个框架

本 Wiki 共有五个分析框架，各司其职。本文说明它们如何协作，以及在不同场景下的优先级。**同时包含 Roth IRA 和应税账户的完整选股流程与决策逻辑。**

---

## 账户全景

| 账户 | 核心定位 | 税务特征 |
|------|---------|---------|
| **Roth IRA** | 高增长、杠杆 ETF、赛道主题仓 | 复利免税，止损决策不受税务约束 |
| **应税账户** | 大盘指数 ETF + 蓝筹长持 + TLH | 短期利得税率高，税务是决策核心变量 |

**账户分工原则：**
- **投机性 / 高增长 / 杠杆 ETF** → Roth（收益复利免税，高换手无税务摩擦）
- **蓝筹 / 大盘指数** → 应税账户（适合长期持有，配合 TLH 优化税务）
- **同一标的如果波动大、换手快** → 优先放 Roth

---

## Roth IRA — 选股逻辑与流程

### 五桶框架

| 桶 | 用途 | 止损规则 |
|----|------|---------|
| 杠杆核心（如 TQQQ）| 长期引擎，以大盘 ETF 为基础放大 | QQQ 跌破 200MA → 减仓 30% |
| 主题个股 | 高增长赛道精选，最多 6 只 | 技术止损 −8% 或跌破 MA50 执行 |
| 赛道 ETF | 七大赛道（电网/存储/光互连/LEO/半导体封装/矿产资源/房地产）主题仓 | 等 /sector-check 触发入场，不追高 |
| 信仰仓（如中概）| 长期主题押注，接受高波动 | 论点破坏时再退，不按技术机械止损 |
| 现金缓冲 | 机动资金，应对触发机会 | 保持最小缓冲，不过度空置 |

### 个股入场标准（Roth）

1. **论文质量**：通过 BAIT ≥3 overlap + Moneyball PW EV 高于当前价 15%+ + 非对称 >2:1
2. **技术确认**：SEPA Stage 2，趋势模板 ≥5/8，有明确轴心点（VCP / 杯柄 / 平台）
3. **仓位限制**：全两个 Roth 合计个股 ≤6 只（满仓时须先清出一只）
4. **市场环境**：SPY/QQQ 在 200MA 之上（熊市暂停新建仓）

### 个股持仓管理（Roth）

| 信号 | 操作 |
|------|------|
| 跌至止损价 | 🛑 Exit 全部（无例外，Roth 无税务顾虑） |
| P&L > +20%，Stage 2 健康 | Hold，上调止损至保本或最近摆动低点 |
| P&L > +20%，跌破 MA50 | Trim 50%，剩余移动止损 |
| 单日 gap +30%（抛物线顶）| Trim 50% 锁利 |
| 论点破坏（changelog 标记）| 降级 Trim 阈值，考虑 Exit |

工具：`/morning-check <TICKER>`（单只深度）/ `/morning-check ALL`（批量扫描）

### 赛道 ETF 入场流程（Roth）

```
[赛道 ETF 触发条件，满足任一]
    ① Chen Yun 近 7 日该赛道 ≥3 只不同 ticker 被提及
    ② ETF 价格 ≤ MA50 −5%（技术回调入场）
    ③ Fear & Greed < 30（极度恐慌机会）
         ↓
    运行 /sector-check --sector <赛道名>
         ↓
    输出：ETF 推荐（费率 × 流动性 × 赛道纯净度）
         + 建议买入股数（基于目标配比缺口）
         ↓
    用户确认 → 执行 → 更新 positions.md
```

不触发时：仅 Watch，不追高入场。

---

## 赛道分析流水线（5 步）

发现 → 论文 → 候选深挖 → 进出场 → 账户/观察列表。工具：`/sector-analyze`。

```
①发现   /sector-analyze（无参数）  聚合 4 源评分提名候选赛道
②论文   /sector-analyze <主题>     生成 wiki/sectors/<slug>.md（11节 + 可投性判定）
③深挖   /etf-analyze + /stock-analyze  对 §10 载体候选逐个深度分析
④进出场 hot-sector-playbook + /stock-exit --profile hot-sector
⑤录入   positions.py Watch（notes 加【赛道:前缀）→ morning-check 按赛道分组显示
```

**生命周期决定纪律：** 赛道论文 §4 = 萌芽/成长 → 个股走 hot-sector-playbook（免费股/抛物线/无 LTCG）；成熟 → 蓝筹规则。

**ETF 打底 + 个股卫星：** 每赛道以 ETF 为核心仓（固定 %），1–2 只高信念个股为卫星（小仓）。比例见 `data/strategy/roth-2026.md`。

**账户：** 热赛道（萌芽/成长）→ Roth；成熟赛道蓝筹 → 应税。

---

## 应税账户 — 选股逻辑与流程

### 三桶框架

| 桶 | 内容 | 目标占比 |
|----|------|---------|
| ETF 核心（桶 A）| VTI + QQQ（大盘 + 科技双柱）| ~60% |
| 蓝筹个股（桶 B）| 市值 >$100B 护城河企业，≤6 只 | ~38% |
| 待清理（桶 C）| TLH 操作仓、非核心个股 | <5%（尽快清零）|

### ETF 核心（桶 A）— 建仓规则

- **工具**：DCA 自动定投（每周固定金额 VTI + QQQ）
- **不追高**：不做择时，DCA 覆盖所有市场状态
- **TLH 释放资金优先转入桶 A**（ETF Core）
- ETF 重叠检查：避免同时持有 VTI + VOO（冗余）

### 蓝筹个股（桶 B）— 准入标准

| 条件 | 标准 |
|------|------|
| 市值 | >$100B |
| 基本面 | 盈利企业，有可识别护城河 |
| 持有计划 | 买入前明确持有 ≥1 年 |
| 单仓上限 | ≤ 活跃仓位 20% |
| 总数限制 | 桶 B 个股上限 6 只 |
| 来源 | upstream rwh 分析 Initiate/Add 推荐 + `/market-weekly` 周报确认 |

### 蓝筹个股（桶 B）— 退出规则

**应税账户不按技术止损机械执行**（避免触发不必要税务事件）：

| 退出条件 | 操作 |
|---------|------|
| 论点彻底破坏 | 运行 `/stock-analyze TICKER`，确认后分批退出，资金 → VTI |
| 持有不足 1 年时论点破坏 | 评估税务成本（短期 ~50% vs 长期 ~28%），尽量等满 1 年 |
| 技术回调 −10%～−20% | **不退出**，正常波动 |

### 税损收割（TLH）流程

```
[TLH 触发条件]
    持仓浮亏 + Wash Sale 窗口已关闭（上次同标的买入 >30 天）
         ↓
    确认 Wash Sale 安全：
    任何账户（含 IRA）30 日内未买入同标的
         ↓
    卖出亏损仓位 → 锁定资本亏损（可抵消当年资本利得）
         ↓
    资金转入桶 A（VTI 为默认接收方）
         ↓
    30 日内禁止任何账户回购同标的
```

时间线维护：见 `data/strategy/taxable-2026.md`（私有文件，不上传 git）

### 蓝筹候选评估流程（每周）

```
upstream rwh 周报（Initiate / Add 推荐）
         ↓
/market-weekly 自动筛选：
    非持有者推荐 Initiate/Add
    + 当前价在 Entry 区间附近
         ↓
写入 data/morning-checks/taxable-action-YYYY-WXX.md（私有）：
    - TLH 本周操作
    - 蓝筹候选评估（市值 / 槽位 / 资金 / 价格）
    - 下周应税建议
```

---

## 跨账户决策树 — 一只股票放哪？

```
[新标的进入研究流程]
         │
         ▼
    是蓝筹股？（市值 >$100B，护城河明确，适合长持）
    ├─ 是 → 应税账户桶 B（前提：有槽位 + 在 Entry 区间）
    └─ 否 ↓
         │
    是赛道 ETF？（GRID / SOXX / ARKX / 光互连组合 / REMX；房地产暂无 ETF）
    ├─ 是 → Roth 赛道 ETF 仓（等 /sector-check 触发）
    └─ 否 ↓
         │
    是杠杆 ETF？（TQQQ / TSLL 等）
    ├─ 是 → 仅 Roth（禁止放应税账户）
    └─ 否 ↓
         │
    是高增长个股？（市值 <$100B，波动大，短期催化剂驱动）
    ├─ 是 → Roth 个股仓（≤6 只，SEPA Stage 2 确认）
    └─ 否 → 不符合任何桶，返回 Watch List 等待
```

---

## 框架一览

| 框架 | 文件 | 核心问题 | 适用阶段 |
|------|------|---------|---------|
| **BAIT** | `frameworks/bait.md` | 为什么这只股票现在被错误定价？ | 论文构建 |
| **Moneyball** | `frameworks/moneyball.md` | 预期价值 vs 当前价格的差距是多少？| 论文构建 |
| **Asset Types** | `frameworks/asset-types.md` | 这类商业模式该用什么指标衡量？ | 论文构建 |
| **SEPA** | `frameworks/sepa.md` | 技术上，现在是买入的正确时机吗？ | 入场执行 |
| **Chen Yun 方法论** | `frameworks/chen-yun-method.md` | 这只股票是否属于结构性主题赛道？ | 想法生成 |

---

## 决策树 — 从想法到执行

```
[想法来源]
    │
    ├─ Chen Yun 提示 / 主题赛道扫描
    │       ↓
    │   Step 1: 对照七大赛道 + 翻倍股九大特征 / 多倍股六大类型 / 五大标准（详见 chen-yun-method.md §2A/2B/2C；独立验证财报）
    │       ↓
    │   通过 ≥3 条 → 进入研究流程
    │   通过 1-2 条 → 保留 opinions/ 作主题输入
    │       ↓
    ├─ 自主发现（新闻、财报、sector rotation）
    │
    ↓
[研究阶段] — 构建 wiki/tickers/<TICKER>/thesis.md
    │
    ├─ Asset Types → 确定估值方法和核心指标
    │
    ├─ BAIT → 识别错误定价来源（B/A/I/T 各几个 overlap？）
    │       ≥3 overlap → 高确信度
    │       1 overlap → 有趣但单薄
    │       0 overlap → 不值得深入
    │
    └─ Moneyball → 计算 PW EV 和非对称比
            PW EV > 当前价 15-25% + 非对称 >2:1 → 通过
            否则 → 重新审视假设或放弃
    │
    ↓
[技术确认阶段] — SEPA
    │
    ├─ Stage 分析：是否在 Stage 2？
    │       否 → 进入 Watch 仓，等 Stage 2 确认
    │       是 → 继续
    │
    ├─ 趋势模板：≥5/8 条件通过？
    │       否 → Watch，等更多条件满足
    │       是 → 继续
    │
    └─ 形态识别：VCP / 杯柄 / 平台整理？
            形态未成熟 → Watch，等轴心点形成
            轴心点出现 + 量能配合 → 进入执行阶段
    │
    ↓
[执行阶段] — /morning-check
    │
    ├─ 计算入场区间、止损、T1/T2
    ├─ 验证风险/回报 ≥ 2:1
    ├─ 检查市场环境（SPY/QQQ vs 200MA）
    └─ 输出 Execute / Chase 50% / Wait / Skip 建议
```

---

## 框架叠加矩阵

不同场景下应激活哪些框架：

| 场景 | 账户 | Chen Yun | BAIT | Moneyball | Asset Types | SEPA | /morning-check |
|------|------|:--------:|:----:|:---------:|:-----------:|:----:|:--------------:|
| 初步筛选新标的 | 通用 | ✅ 主 | — | — | — | — | — |
| 构建完整论文 | 通用 | 参考 | ✅ 主 | ✅ 主 | ✅ 主 | 辅 | — |
| 财报后更新（/stock-refresh）| 通用 | — | ✅ 复查 | ✅ 复查 | — | ✅ 复查 | — |
| Roth 个股每日入场 | Roth | — | — | — | — | ✅ 隐式 | ✅ 主 |
| Roth 持仓 Hold/Trim/Exit | Roth | — | — | — | — | Stage 判断 | ✅ 主 |
| 应税蓝筹候选评估 | 应税 | — | ✅ 护城河 | ✅ EV | ✅ 主 | — | — |
| 应税蓝筹退出判断 | 应税 | — | ✅ 论点审查 | — | — | — | — |
| 主题赛道轮动判断 | Roth | ✅ 主 | B层 | — | — | — | — |
| ETF 深度分析（/etf-analyze）| Roth | 参考 | — | 场景 | — | ✅ 主 | — |
| 赛道 ETF 定投（/sector-check）| Roth | ✅ 主 | B层 | — | — | 触发判断 | ✅ 主 |
| 应税 DCA / TLH 操作 | 应税 | — | — | — | — | — | `/market-weekly` |

---

## 框架间的关键连接点

### Chen Yun ↔ BAIT
- Chen Yun 的"盈利拐点"= BAIT **B 层**（市场情绪滞后于运营数据）
- Chen Yun 的"订单积压可见性"= BAIT **A 层**（分析性低效，大多数模型低估积压价值）
- Chen Yun 的七大赛道选题 = 主题性 **I 层**（散户尚未发现的行业信息不对称）

### BAIT ↔ Moneyball
- BAIT 识别**为什么**存在错误定价
- Moneyball 量化**错误定价有多大**（PW EV vs 当前价）
- 两者结合：BAIT 给出定性确信度，Moneyball 给出定量买入触发线

### SEPA ↔ Moneyball
- Moneyball 的 Bear Case 价格 = SEPA 的最终止损参考线
- Moneyball 的 Bull/Base Case 价格 = SEPA 的 T1/T2 目标
- SEPA 的入场时机可以提高 Moneyball 期望值的实现概率

### SEPA ↔ Chen Yun
- Chen Yun 的金字塔建仓与 SEPA 的 Pyramiding 原则一致
- Chen Yun 的"不怕追高"与 SEPA 的"买入区 = Pivot +5%" 形成对照：
  SEPA 有明确上限，Chen Yun 更注重趋势持续而非精确入场价
- 两者在止盈上有共识：仓位上涨 100% 后先收回成本（Chen Yun 免费股 = SEPA Phase 2 止损移至保本）

---

## 优先级规则

1. **研究质量优先于信号速度**：Chen Yun 提示是起点，不是终点。2A/2B/2C 三层筛选 + 独立财报验证是必须步骤（翻倍股九大特征 → 多倍股六大类型 → 五大标准）。
2. **BAIT 确信度决定仓位大小**：1 overlap = 试仓；3+ overlap = 满仓
3. **SEPA Stage 是硬门槛**：Stage 4 下跌趋势中，无论 BAIT 多强，不建新仓
4. **Moneyball PW EV 是买入触发线**：当前价 > PW EV 时，即使 BAIT 强、SEPA 好，也不追高
5. **市场环境是总开关**：熊市（SPY/QQQ < 200MA，或 `/market-daily` 5-signal 框架 ≤2/5 积极）期间，所有新仓决策暂停；出现 Distribution Warning（Golden Cross 股大量抛售）时不抄底

---

## 交叉引用

- 上游框架：`frameworks/bait.md`、`frameworks/moneyball.md`、`frameworks/asset-types.md`
- Overlay 框架：`frameworks/chen-yun-method.md`、`frameworks/sepa.md`
- 执行工具（Roth）：`/morning-check`（日常入场 + 批量扫描）、`/sector-check`（赛道 ETF 定投）、`/etf-analyze`（ETF 深度分析）
- 执行工具（应税）：`/market-weekly`（生成每周应税行动建议，私有文件）、`/stock-refresh`（论文更新）
- 执行工具（通用）：`/stock-analyze`（深度分析新标的或退出评估）
- 账户策略文件（私有，不上传 git）：`data/strategy/roth-2026.md`、`data/strategy/taxable-2026.md`
- Skill：`finance-market-analysis:sepa-strategy`（完整 SEPA 分析）
