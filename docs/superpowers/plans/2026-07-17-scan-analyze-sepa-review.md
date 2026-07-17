# ticker-scan → stock-analyze 一致性 review 机制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/ticker-scan` 的价格结构核查与 `/stock-analyze` 的 SEPA 判断逻辑对齐，用规则否决表兜住系统性偏差，并对最终 🔥 候选加一层独立 agent 复核。

**Architecture:** 分两层——(1) 数据层：`scripts/ticker_scan.py` 新增 `ma150_pct`、`ma200_trend` 两个字段，提供判断 Stage1 vs Stage2 所需的最小数据；(2) 决策层：`.claude/commands/ticker-scan.md` 重定义 2C 标准#5、加打标签否决表、加独立 agent 复核步骤。数据层是纯 Python，走 TDD；决策层是 LLM 指令文档，改后靠阅读核实。

**Tech Stack:** Python 3.14, pandas, yfinance, pytest 9.0.2。skill 文档为 Markdown。

## Global Constraints

- 新字段向后兼容：数据不足时字段**省略**（不输出 `null` 键），沿用现有 `ma200_pct`/`inst_pct` 的省略风格。
- MA200 趋势窗口 = 21 个交易日；阈值 ±0.5%（>+0.5% → `up`，<-0.5% → `down`，否则 `flat`）。
- 完整 SEPA 第 8 条（相对强度百分位）**不实现**，超出范围。
- 不改动 `/stock-analyze` 的 SEPA 8 条模板逻辑（那是权威版本）。
- 独立 agent 复核**只**覆盖最终 🔥 候选，不覆盖 ⭐/👀。
- Python 代码遵循 PEP 8 + 类型注解（见用户 python 规则）。

---

## File Structure

- `scripts/ticker_scan.py`（修改）— 抽出纯函数 `ma_metrics(closes)` 计算 MA 相关指标；`fetch_ticker()` 调用它；docstring + `print_result()` 同步更新。
- `tests/test_ticker_scan.py`（新建）— `ma_metrics` 的单元测试，用合成 pandas Series，无网络。
- `.claude/commands/ticker-scan.md`（修改）— Stage3 标准#5 重定义、Step6 否决表、新增 Step6.5、输出格式微调。

---

### Task 1: 抽出 `ma_metrics` 纯函数并加单元测试

把 MA 计算从 `fetch_ticker()`（含网络）里抽成纯函数，才能脱离网络做 TDD。本任务只加函数 + 测试，暂不改 `fetch_ticker`（下个任务接线）。

**Files:**
- Modify: `scripts/ticker_scan.py`（在 `_eps_trend` 之后、`fetch_ticker` 之前新增 `ma_metrics`）
- Test: `tests/test_ticker_scan.py`（新建）

**Interfaces:**
- Produces: `ma_metrics(closes: pd.Series) -> dict`。返回键（各自在数据不足时省略）：`ma50_pct: float`、`ma150_pct: float`、`ma200_pct: float`、`ma200_trend: str`（`"up"`/`"down"`/`"flat"`）。所有百分比 = `(price/ma - 1)*100` 四舍五入 1 位；`price` 取 `closes.iloc[-1]`。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_ticker_scan.py`：

```python
import pandas as pd
import pytest

from scripts.ticker_scan import ma_metrics


def test_ascending_series_all_positive_and_trend_up():
    closes = pd.Series([float(x) for x in range(1, 261)])
    m = ma_metrics(closes)
    assert m["ma50_pct"] > 0
    assert m["ma150_pct"] > 0
    assert m["ma200_pct"] > 0
    assert m["ma200_trend"] == "up"


def test_descending_series_all_negative_and_trend_down():
    closes = pd.Series([float(x) for x in range(260, 0, -1)])
    m = ma_metrics(closes)
    assert m["ma50_pct"] < 0
    assert m["ma150_pct"] < 0
    assert m["ma200_pct"] < 0
    assert m["ma200_trend"] == "down"


def test_flat_series_trend_flat():
    closes = pd.Series([100.0] * 260)
    m = ma_metrics(closes)
    assert m["ma50_pct"] == 0.0
    assert m["ma200_trend"] == "flat"


def test_short_series_omits_long_ma_fields():
    closes = pd.Series([float(x) for x in range(1, 101)])  # 100 bars
    m = ma_metrics(closes)
    assert "ma50_pct" in m
    assert "ma150_pct" not in m
    assert "ma200_pct" not in m
    assert "ma200_trend" not in m


def test_empty_series_returns_empty_dict():
    assert ma_metrics(pd.Series([], dtype=float)) == {}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_ticker_scan.py -v`
Expected: FAIL — `ImportError` / `cannot import name 'ma_metrics'`

- [ ] **Step 3: 写最小实现**

在 `scripts/ticker_scan.py` 中 `_eps_trend` 函数之后插入：

```python
def ma_metrics(closes: pd.Series) -> dict:
    """Compute MA-based price-structure metrics from a close-price series.

    Pure (no network) so it can be unit-tested with synthetic series.
    Keys are omitted when the series is too short to compute them:
      ma50_pct / ma150_pct / ma200_pct — price vs that MA, in percent.
      ma200_trend — "up"/"down"/"flat", current MA200 vs MA200 21 bars ago
                    (thresholds +/-0.5%). Needs >=221 bars.
    """
    out: dict = {}
    if len(closes) == 0:
        return out
    price = float(closes.iloc[-1])

    for span, key in ((50, "ma50_pct"), (150, "ma150_pct"), (200, "ma200_pct")):
        if len(closes) >= span:
            ma = closes.rolling(span).mean().iloc[-1]
            if pd.notna(ma) and ma != 0:
                out[key] = round((price / ma - 1) * 100, 1)

    if len(closes) >= 221:
        ma200_series = closes.rolling(200).mean()
        cur = ma200_series.iloc[-1]
        prev = ma200_series.iloc[-22]
        if pd.notna(cur) and pd.notna(prev) and prev != 0:
            chg = (cur / prev - 1) * 100
            if chg > 0.5:
                out["ma200_trend"] = "up"
            elif chg < -0.5:
                out["ma200_trend"] = "down"
            else:
                out["ma200_trend"] = "flat"
    return out
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_ticker_scan.py -v`
Expected: PASS（5 passed）

若 `ImportError: No module named 'scripts'`，在 `tests/` 目录新建空 `tests/__init__.py`，并确认从仓库根目录运行 pytest（`scripts/ticker_scan.py` 已有隐式包路径；根目录运行时 `scripts.ticker_scan` 可导入）。若仍失败，改测试导入为在 `test_ticker_scan.py` 顶部加：

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
```

- [ ] **Step 5: 提交**

```bash
git add scripts/ticker_scan.py tests/test_ticker_scan.py
git commit -m "feat: 抽出 ma_metrics 纯函数计算 MA150/MA200趋势"
```

---

### Task 2: `fetch_ticker` 接入 `ma_metrics` + 更新 docstring/print_result

把 `fetch_ticker()` 里的内联 MA 计算换成调用 `ma_metrics`，输出层同步。这一步动网络路径，靠一次真实拉取做冒烟验证（非单元测试）。

**Files:**
- Modify: `scripts/ticker_scan.py`（`fetch_ticker` 内 MA 段、模块 docstring、`print_result`）

**Interfaces:**
- Consumes: `ma_metrics(closes)`（Task 1）
- Produces: `fetch_ticker(tk)` 返回 dict 现在可能含 `ma150_pct`、`ma200_trend` 键（Step6/6.5 的决策层消费）。

- [ ] **Step 1: 替换 `fetch_ticker` 里的 MA 计算**

找到 `scripts/ticker_scan.py` 中这段（约 119–126 行）：

```python
        price = float(h["Close"].iloc[-1])
        ma50 = float(h["Close"].rolling(50).mean().iloc[-1])
        ma50_pct = round((price / ma50 - 1) * 100, 1)

        ma200_pct = None
        if len(h) >= 200:
            ma200 = float(h["Close"].rolling(200).mean().iloc[-1])
            ma200_pct = round((price / ma200 - 1) * 100, 1)
```

替换为：

```python
        price = float(h["Close"].iloc[-1])
        ma = ma_metrics(h["Close"])
```

- [ ] **Step 2: 更新 result 组装段**

找到 `fetch_ticker` 中 result dict 组装（约 170–184 行）：

```python
        result: dict = {
            "ticker": tk,
            "exchange": exchange,
            "is_otc": is_otc,
            "market_cap_m": market_cap_m,
            "ma50_pct": ma50_pct,
            "max_gap_up_pct": max_gap_up,
            "eps_trend": eps_trend,
        }
        if ma200_pct is not None:
            result["ma200_pct"] = ma200_pct
        if inst_pct is not None:
            result["inst_pct"] = inst_pct
        result.update(rev_metrics)
        return result
```

替换为：

```python
        result: dict = {
            "ticker": tk,
            "exchange": exchange,
            "is_otc": is_otc,
            "market_cap_m": market_cap_m,
            "max_gap_up_pct": max_gap_up,
            "eps_trend": eps_trend,
        }
        result.update(ma)  # ma50_pct / ma150_pct / ma200_pct / ma200_trend（各自可能省略）
        if inst_pct is not None:
            result["inst_pct"] = inst_pct
        result.update(rev_metrics)
        return result
```

- [ ] **Step 3: 更新模块 docstring 字段列表**

找到 docstring 中（约 22–24 行）：

```
  ma50_pct        — price vs 50-day MA (%)
  ma200_pct       — price vs 200-day MA (%, null if <200 days history)
```

替换为：

```
  ma50_pct        — price vs 50-day MA (%)
  ma150_pct       — price vs 150-day MA (%, omitted if <150 days history)
  ma200_pct       — price vs 200-day MA (%, omitted if <200 days history)
  ma200_trend     — "up"/"down"/"flat": MA200 vs 21 bars ago (omitted if <221 days)
```

- [ ] **Step 4: 更新 `print_result` 加 MA150 + 趋势列**

找到 `print_result` 中（约 200–209 行）：

```python
    ma50 = f"{r['ma50_pct']:+.1f}%"
    ma200 = f"{r['ma200_pct']:+.1f}%" if "ma200_pct" in r else "—"
    gap = f"{r['max_gap_up_pct']:+.1f}%"
    eps = r.get("eps_trend", "—")
    print(
        f"{r['ticker']:8s}{otc_flag:<6s} cap={cap:>10s}  "
        f"rev_yoy={yoy:>8s}{accel} consec={consec}  "
        f"eps={eps:<14s} inst={inst:>6s}  "
        f"ma50={ma50:>7s} ma200={ma200:>7s}  gap_up={gap}"
    )
```

替换为：

```python
    ma50 = f"{r['ma50_pct']:+.1f}%" if "ma50_pct" in r else "—"
    ma150 = f"{r['ma150_pct']:+.1f}%" if "ma150_pct" in r else "—"
    ma200 = f"{r['ma200_pct']:+.1f}%" if "ma200_pct" in r else "—"
    trend = r.get("ma200_trend", "—")
    gap = f"{r['max_gap_up_pct']:+.1f}%"
    eps = r.get("eps_trend", "—")
    print(
        f"{r['ticker']:8s}{otc_flag:<6s} cap={cap:>10s}  "
        f"rev_yoy={yoy:>8s}{accel} consec={consec}  "
        f"eps={eps:<14s} inst={inst:>6s}  "
        f"ma50={ma50:>7s} ma150={ma150:>7s} ma200={ma200:>7s} trend={trend:<5s} gap_up={gap}"
    )
```

- [ ] **Step 5: 单元测试仍通过 + 真实冒烟**

Run: `python -m pytest tests/test_ticker_scan.py -v`
Expected: PASS（5 passed，未回归）

Run: `python scripts/ticker_scan.py NVDA --json`
Expected: 一行 JSON，含 `ma50_pct`、`ma150_pct`、`ma200_pct`、`ma200_trend`（NVDA 历史 >221 天，四个都应在）

Run: `python scripts/ticker_scan.py NVDA`
Expected: 文本行含 `ma150=` 和 `trend=` 两列，无异常

- [ ] **Step 6: 提交**

```bash
git add scripts/ticker_scan.py
git commit -m "feat: ticker_scan 输出 ma150_pct 和 ma200_trend 字段"
```

---

### Task 3: 重定义 Stage3 2C 标准#5（skill 文档）

**Files:**
- Modify: `.claude/commands/ticker-scan.md`（Stage3 表，约 155 行的标准#5 行）

**Interfaces:**
- Consumes: `ma50_pct`、`ma150_pct`、`ma200_pct`、`ma200_trend`（Task 2 产出的字段）

- [ ] **Step 1: 替换标准#5 表格行**

找到 `.claude/commands/ticker-scan.md` Stage3 表格里这一行（约 155 行）：

```
| 5 | 价格结构配合（Stage 2，非 Stage 4 崩坏）| **yfinance** | `ma50_pct > 0 AND ma200_pct > -20` | ✅/⚠️/❌ + MA 数字 |
```

替换为：

```
| 5 | 价格结构配合（区分 Stage2 健康 vs Stage1 未确认反转）| **yfinance** | 四条子检查见下 | ✅/⚠️/❌ + MA 数字 |
```

- [ ] **Step 2: 在 Stage3 表格下方（约 157 行"每条输出"那句之前）插入判定细则**

紧接 Stage3 表格之后插入：

```markdown
**标准#5 判定细则（四条子检查，对齐 `/stock-analyze` SEPA 趋势模板）：**

| 子检查 | 数据来源 | 条件 |
|--------|---------|------|
| a. 价 > MA50 | yfinance | `ma50_pct > 0` |
| b. 价 > MA150 | yfinance | `ma150_pct > 0` |
| c. 价 > MA200 | yfinance | `ma200_pct > 0` |
| d. MA200 未走弱 | yfinance | `ma200_trend != "down"` |

- 四条全满足 → ✅ **Stage2健康趋势**
- 部分满足（如价站上 MA50 但 MA150/MA200 未突破，或 MA200 刚转平）→ ⚠️ **Stage1→2过渡**
- `ma150_pct < 0` 或 `ma200_trend == "down"` → ❌ **Stage1未确认底部反转**（明确用此措辞，禁止写成"价格结构健康"）
- 字段缺失（历史不足）→ ⚠️，注明"MA150/MA200趋势数据不足，需完整 SEPA 核实"
```

- [ ] **Step 3: 核实改动**

Run: `grep -n "Stage1未确认底部反转\|四条子检查\|ma200_trend" .claude/commands/ticker-scan.md`
Expected: 命中 Stage3 表格行 + 新增细则块（至少 3 处）

- [ ] **Step 4: 提交**

```bash
git add .claude/commands/ticker-scan.md
git commit -m "feat: ticker-scan 2C标准#5 对齐 SEPA 四条子检查"
```

---

### Task 4: Step6 打标签否决表（skill 文档）

**Files:**
- Modify: `.claude/commands/ticker-scan.md`（Step6 标签规则表之后，约 170 行）

**Interfaces:**
- Consumes: Task 3 定义的标准#5 三态结果（✅/⚠️/❌）

- [ ] **Step 1: 在 Step6 现有标签规则表之后插入否决表**

找到 `.claude/commands/ticker-scan.md` Step6 里标签规则表结尾这一行（约 170 行）：

```
| ❌ 筛除 | 未通过 Stage 1 或 Stage 2 |
```

在它之后（表格结束后）插入：

```markdown

**否决表（价格结构一票否决，优先级高于上表）：**

不论 2A/2B/2C 其余项多高，2C标准#5 结果强制封顶标签：

| 2C标准#5 结果 | 否决动作 |
|--------------|---------|
| ❌ Stage1未确认底部反转 | 标签封顶 **👀观察**，即使 2B/2C 其余很强 |
| ⚠️ Stage1→2过渡 且本应判 🔥 | 降为 **⭐翻倍候选** |

发生降级时，综合排名表"标签"列必须附一句原因（如"MA200仍下降，Stage1底部反转未确认"）。
```

- [ ] **Step 2: 核实改动**

Run: `grep -n "否决表\|一票否决\|标签封顶" .claude/commands/ticker-scan.md`
Expected: 命中新增否决表块（至少 3 处）

- [ ] **Step 3: 提交**

```bash
git add .claude/commands/ticker-scan.md
git commit -m "feat: ticker-scan 打标签加价格结构否决表"
```

---

### Task 5: 新增 Step6.5 独立 agent 复核 + 输出格式微调（skill 文档）

**Files:**
- Modify: `.claude/commands/ticker-scan.md`（Step6 之后、Step7"保存输出文件"之前插入 Step6.5；并微调输出格式说明）

**Interfaces:**
- Consumes: 否决表跑完后仍为 🔥 的候选列表

- [ ] **Step 1: 在 Step6 末尾、`### 7. 保存输出文件` 之前插入 Step6.5**

找到 `.claude/commands/ticker-scan.md` 中 `### 7. 保存输出文件`（约 217 行）这一行，在它之前插入：

```markdown
### 6.5 独立复核（仅对最终 🔥 候选）

否决表跑完后，若仍有候选保持 🔥 多倍候选（通常 1–3 只），对**每个** 🔥 候选用 Agent 工具起一个独立子 agent 做 outside-view 复核。

**子 agent 输入（干净上下文，不携带本次 scan 的推理过程）：** ticker、现价、`ma50_pct`/`ma150_pct`/`ma200_pct`/`ma200_trend`、`eps_trend`、`revenue_yoy_pct`、backlog 摘要（若 Stage2/3 已 WebSearch 到）。

**子 agent 任务：** 独立套用 SEPA 逻辑，只回 (1) Stage 判断 1–4；(2) 一句话理由。不看 scan 已给的标签。

**处理结果：**
- 子 agent 判断与 scan 一致（都指向 Stage2 健康）→ 无需额外标注
- 不一致（子 agent 认为 Stage1/3/4）→ 综合排名表该候选"建议"列追加 `⚠️独立复核不一致（子agent判Stage X），/stock-analyze 前先人工确认`；标签本身不强行覆盖（人是最终判断者）

🔥 候选为 0 时跳过本步。
```

- [ ] **Step 2: 微调输出格式说明**

找到 Step6"输出格式"里综合排名表下游行动那段（约 212 行）：

```
**下一步行动：** `/stock-analyze <TICKER>` 对 🔥/⭐ 做完整 15 节论文；👀 等触发条件后再跑 `/ticker-scan <TICKER>` 单股验证
```

替换为：

```
**下一步行动：** `/stock-analyze <TICKER>` 对 🔥/⭐ 做完整深度分析；👀 等触发条件后再跑 `/ticker-scan <TICKER>` 单股验证。🔥 候选若带"独立复核不一致"警示，先人工确认价格结构再决定是否进 `/stock-analyze`
```

- [ ] **Step 3: 核实改动**

Run: `grep -n "6.5 独立复核\|outside-view\|独立复核不一致" .claude/commands/ticker-scan.md`
Expected: 命中新增 Step6.5 块 + 输出格式警示（至少 3 处）

- [ ] **Step 4: 提交**

```bash
git add .claude/commands/ticker-scan.md
git commit -m "feat: ticker-scan 新增 Step6.5 独立 agent 复核 🔥 候选"
```

---

## 验证全流程（全部任务完成后）

- [ ] `python -m pytest tests/test_ticker_scan.py -v` → 5 passed
- [ ] `python scripts/ticker_scan.py NVDA PATH --json` → 两行 JSON，字段完整
- [ ] 通读 `.claude/commands/ticker-scan.md`：Stage3 标准#5 四条子检查、Step6 否决表、Step6.5 独立复核三处齐全，措辞用"Stage1未确认底部反转"而非"价格结构健康"
- [ ] `git log --oneline -6` → 6 个 feat 提交（Task1–5，其中 Task1/2 各一，Task3/4/5 各一）
