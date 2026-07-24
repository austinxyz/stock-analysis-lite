# 设计：4 skills 与 frameworks 对齐 + ticker_scan.py 升级共用数据层

**日期**: 2026-07-23
**背景**: 审查发现 4 个 skills（ticker-scan / stock-analyze / stock-entry / stock-exit）与 `wiki/frameworks/` 方法论存在偏差，且 `scripts/ticker_scan.py` 数据不足以支撑 SEPA 等方法（缺 ATR、量能、52 周高低点、RS 等）。三个 skill 各自内嵌临时 python 重复计算，数据口径不统一。

## 已定裁决（用户拍板）

1. **frameworks 是权威**——skill 的故意适配保留，但必须回填到 framework 文档记录（适配 + 理由）。
2. **ATR 止损保留**（max(2×ATR14, 10%)，上限 20%），回填 sepa.md。
3. **入场门槛保留 ≥3/8**（翻倍小盘常处 Stage1→2 早期），回填 sepa.md。
4. **BAIT 保留 /12 评分制**，回填 bait.md 映射规则（每 lens 2-3 分 = 计入 overlap）。
5. **Moneyball 补实现**：stock-analyze 加 EV 节、stock-entry 加 PW EV 触发线、stock-exit 修 tagline + 读 EV 目标。
6. **ticker_scan.py 升级为 4 skills 共用数据层**（双模式）。

## 审查发现清单（修复对象）

### 硬缺陷
- **B1** stock-analyze inline python：`rolling(252)` 在 1y (~250 bar) 历史上返回 NaN → 52 周高低点算不出。
- **B2** SEPA 趋势模板 #8（RS >70 百分位）无任何数据来源，纯 LLM 猜。
- **B3** Moneyball 框架在所有 skill 中零实现；stock-exit tagline 却写"基于 Moneyball 框架"。
- **B4** script 不输出现价 `price`。

### 漏实现（framework 有、skill 无）
- **G1** stock-entry 缺"财报前 2 周避免入场"检查（sepa.md 第四节）。
- **G2** stock-entry 缺市场环境主开关（sepa.md 第六节：牛 1-2% / 震荡 0.5-1% / 熊 0%）。
- **G3** ticker-scan 2C#2 缺"客户集中度可接受？"（hot-sector-method 2C 表）。
- **G4** stock-entry 买入区间写"轴心上方 0-3%，超 1 ATR 不追"，framework 是"轴心 → +5%，超 5% 不追"。统一为 framework 版（+5% 上限），0-3% 作为"理想区"保留在文案内。

### 文档不同步（skill 量化了 framework 没记录的规则）
- **D1** sepa.md 需补适配表：ATR 止损、≥3/8 门槛、止损 2 日收盘确认、MA150 连续 3 日跌破出场。
- **D2** bait.md 需补 /12 制 ↔ overlap 映射。
- **D3** hot-sector-method.md 需补：市值分档（<2000✅ / 2000-5000⚠️ / >5000❌）、全局止盈量化阈值（3+股 20%+ 集中 2-4 周 → 减 20-30%；赛道 ETF 月涨 >30% → 减 25-30%；VIX>35 → 停新仓）、价格结构否决表交叉引用。
- **D4** workflow-guide.md 同步：第二步加 EV 节说明、第三步加财报规避 + 市场环境 + PW EV 触发线。
- **D5** 2B#5 机构建仓"inst_pct >15 且趋势上升"中"趋势上升"无数据支撑 → 措辞改为"inst_pct > 15 → ✅"（单快照可判定），去掉无据可依的趋势条件。

---

## 1. ticker_scan.py v2 — 共用数据层

### 双模式

```
py scripts/ticker_scan.py T1 T2 ... --json                # scan 模式（默认）：现有 14 字段，批筛
py scripts/ticker_scan.py TICKER --mode full --json       # full 模式：追加深度字段，单股深度 skill 用
py scripts/ticker_scan.py --benchmark --json              # 市场环境：SPY/QQQ vs MA200 → bull/chop/bear
```

`--mode full` 可与 `--benchmark` 同时使用。scan 模式行为与现在完全一致（向后兼容，字段不减）。

### full 模式新增字段（缺数据时省略键，沿用现有风格）

| 字段 | 定义 | 服务 |
|------|------|------|
| `price` | 最新收盘价 | 所有 skill |
| `atr14` / `atr_pct` | 14 日 ATR（Wilder 简化：TR 14 日滚动均值）/ 占现价 % | entry 止损、exit |
| `vol_avg20_m` | 20 日均量（百万股）| 突破量能基准 |
| `vol_ratio` | 最新日量 / 20 日均量 | 突破确认（≥1.5×）|
| `high_52w` / `low_52w` | 窗口内最高 High / 最低 Low（`.max()`/`.min()`，不用 rolling —— 修 B1）| SEPA #6/#7 |
| `pct_from_52w_high` | (price/high_52w − 1)×100（负数=低于高点）| SEPA #7（≥ −25 为过）|
| `pct_above_52w_low` | (price/low_52w − 1)×100 | SEPA #6（≥ +30 为过）|
| `rs_score` | Minervini 加权代理：股票 3/6/9/12 月收益按 40/20/20/20 加权 − SPY 同法加权，输出差值（正 = 跑赢）| SEPA #8 |
| `rs_pass` | bool：rs_score > 0 且 12 月收益 > SPY 12 月收益 | SEPA #8 判定 |
| `trend_template` | 对象：8 条布尔（`p_gt_ma150_200` / `ma150_gt_ma200` / `ma200_uptrend` / `ma50_gt_ma150_200` / `p_gt_ma50` / `above_low_30` / `near_high_25` / `rs_pass`）+ `score`（X/8）| SEPA 模板整体 |
| `next_earnings_date` / `earnings_in_days` | yfinance calendar/earnings_dates；取未来最近一次 | 财报 2 周规避 |
| `short_pct_float` | 空头占 float %（info.shortPercentOfFloat×100）| 挤压 |
| `float_m` / `shares_out_m` | float / 总股本（百万股）| 稀释、挤压 |
| `cash_m` | 最新季度现金及等价物（百万美元）| 现金跑道 |

### --benchmark 输出（单独一行 JSON）

```json
{"benchmark": true, "spy_vs_ma200_pct": 3.2, "qqq_vs_ma200_pct": 5.1, "market_env": "bull"}
```

判定：SPY 与 QQQ 都 > MA200 → `bull`；都 < MA200 → `bear`；其余 → `chop`。

### 实现约束

- 新逻辑抽纯函数：`atr14(high, low, close)`、`weighted_return_score(closes)`、`trend_template(closes, rs_pass)`、`market_env(spy_pct, qqq_pct)` —— 全部 pytest 覆盖（合成序列，无网络），沿用 `ma_metrics` 模式。
- rs_score 需要 SPY 历史：full 模式下 SPY 只拉一次，多 ticker 复用。
- earnings date 拉取失败 → 省略键，不报错。
- history 窗口 full 模式改 `period="2y"`（保证 12 月收益 + 221 bar MA200 趋势都够），scan 模式维持 1y。
- docstring 字段表同步更新；`scripts/ticker_scan_guide.md` 同步更新。

## 2. Skill 修复

### stock-analyze
- Step 1 inline python 整段删除 → `py scripts/ticker_scan.py TICKER --mode full --benchmark --json`，字段引用改 JSON 键（修 B1/B4）。
- BAIT 节：保留 0-3×4=/12，每 lens 注入 framework 判据提示（B：short interest >10% 高 / >20% 极端、恐惧是否被财报证伪；A：自建模型 vs 共识差 >20%、覆盖分析师数；I：transcript/10-K 注脚/proxy 具体可量化信息；T：多技术因素同价位汇聚）；评分表后加一行 overlap 换算：`overlap = (B≥2) + (A≥2) + (I≥2) + (T≥2)`，输出 "X 因子重叠 — weak/moderate/strong/very strong"（对应 bait.md 裁决表）。
- SEPA 节：8 条直接引用 `trend_template` 字段；#8 用 `rs_pass` + `rs_score` 数字。
- **新增 Section「Moneyball 情景 EV」**（放技术面之后、综合结论之前）：Bull/Base/Bear 表（价格目标 / 时间跨度 / 关键假设 2-3 条 / 概率，概率和=100%；Bull 典型 20-35%、Base 45-60%、Bear 15-30%）；EV 公式 + Expected Return + Asymmetry Ratio；必答三问（bear 成立需什么为真？bear 是否已 priced in？解决不确定性的催化剂？）；终值算式（`[年] EBITDA/营收 $X × [倍数] = $Z/股`）。输出报告模板加对应节。
- 翻倍股专项检查复用 `short_pct_float`/`float_m`/`cash_m`。
- 报告模板脚注框架行改：`Mauboussin BAIT | Minervini SEPA | Moneyball EV`。

### stock-entry
- Step 2 inline python 删除 → `--mode full --benchmark`。
- Step 3 入场条件加两条：
  - `earnings_in_days ≤ 14` → ⚠️ 财报临近，framework 要求财报前 2 周不入场；结论区标注"等财报后"（修 G1）。
  - `market_env`：`bear` → ❌ 不建新仓（framework 第六节）；`chop` → 单笔风险降至 0.5%；`bull` → 1%（修 G2）。
- 买入区间统一：**轴心价 → +5% 为买入区**（0-3% 理想），超 +5% 不追（修 G4，替换"超 1 ATR 不追"）。
- Step 5 后加 **Moneyball 触发线**：读 analysis.md EV 节 → `现价 > PW EV × 0.85 → 不追，等回调或重估`（15% 安全边际下限；analysis.md 无 EV 节 → 提示先重跑 /stock-analyze）。
- 输出模板加：市场环境行、财报距离行、PW EV 对照行。

### stock-exit
- 首行描述改：`基于免费股策略（hot-sector）+ SEPA 止损纪律 + Moneyball 目标价管理`（修 B3 标签）。
- Step 2 inline python 删除 → `--mode full`。
- Step 1 读取内容加：analysis.md 的 EV / Bull / Bear 目标价；输出模板「止盈进度」表加一行 `Moneyball EV $X` 对照，现价 > Bull 目标 → 提示估值透支考虑加速减仓。

### ticker-scan
- 2C#2 判断列补"客户集中度可接受？"（WebSearch backlog 时顺带查，无数据 ⚠️ 不影响主判定）（修 G3）。
- Stage 2 的 2B#5 判断规则改为 `inst_pct > 15 → ✅；5–15 → ⚠️；<5 或无数据 → ❌/LLM 判断`（修 D5）。

## 3. Framework 回填

### sepa.md（第七节「在本 Wiki 中的应用」后加「本 wiki 适配记录」表）
| 适配 | 原典 | 本 wiki | 理由 |
|------|------|---------|------|
| 止损宽度 | ≤7-8% 硬止损 | max(2×ATR14, 10%)，上限 20% | 翻倍小盘日波 5-10%，固定窄止损被噪音洗出 |
| 入场资格 | <5/8 Skip | ≥3/8 可进入场评估（缺失项必须列明）| 翻倍候选常处 Stage1→2 早期，5/8 会系统性错过 |
| 止损确认 | 触价即止损 | 连续 2 日收盘低于止损位 | 高波动小盘单日插针频繁 |
| MA 出场 | +15% 后沿 20MA 移动 | 连续 3 日跌破 MA150 出场 | 与 /stock-exit 免费股周期匹配（更长持有）|

### bait.md（Verdict 节后加映射）
- 本 wiki /stock-analyze 用 0-3×4=/12 制；换算：每 lens ≥2 分 = 计入 overlap，overlap 数对应本表裁决（1 弱 / 2 中 / 3 强 / 4 极强）。/12 总分仅作展示，裁决以 overlap 为准。

### hot-sector-method.md
- 2B 六大类型表 #6 补注：`市值分档：<$2B ✅ / $2-5B ⚠️ / >$5B ❌（五大公式#5 用 <$5B）`。
- 2B#5 补注：`inst_pct >15% ✅ / 5-15% ⚠️`。
- 四、风险纪律「止盈提醒」行补量化：`3+ 持仓各涨 20%+ 集中 2-4 周 → 全组合减 20-30%；赛道 ETF 单月 >30% → 赛道内减 25-30%；VIX>35 → 停新仓`。
- 2C#5 行补交叉引用：`→ 详见 /ticker-scan 四条子检查 + 价格结构否决表`。

### workflow-guide.md
- 第二步加「Moneyball EV」小节（表样例 + PW EV 定义）。
- 第三步加：财报前 2 周不入场、市场环境开关表、PW EV 触发线（现价 > EV×0.85 不追）。

## 4. 测试

- 纯函数 pytest（`tests/test_ticker_scan.py` 扩展）：
  - `atr14`：合成 OHLC，已知 TR 验证。
  - `weighted_return_score`：线性上涨 vs 平盘 SPY → 正分；下跌 vs 上涨 SPY → 负分。
  - `trend_template`：构造 8/8 全过序列、0/8 全挂序列、边界（正好 −25% 高点距离）。
  - `market_env`：四象限（+,+→bull；−,−→bear；+,−→chop）。
- 现有 5 个 ma_metrics 测试不回归。
- 冒烟：`py scripts/ticker_scan.py NVDA --mode full --benchmark --json` 字段齐全；scan 模式输出与升级前字段一致。

## 不做的事

- 不实现 VCP 形态自动识别 / Base 计数自动化（LLM 定性判断保留，volume 字段仅辅助）。
- 不实现真 IBD RS 百分位（需全市场 universe），用加权收益差代理。
- 不改 /morning-check 等本仓库不存在的 skill。
- 不动 positions/entry-exit 历史输出文件。
- scan 模式不加新必拉字段（保持批量速度）。
