# Skills-Frameworks 对齐 + ticker_scan.py v2 共用数据层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `ticker_scan.py` 升级为 4 个 skills 共用的数据层（双模式 + benchmark），修复 skills 与 frameworks 的偏差（Moneyball 零实现、SEPA RS 无数据、财报/市场环境漏检查等），并把 skill 的故意适配回填进 framework 文档。

**Architecture:** 数据层先行——纯函数（`atr14` / `weighted_return_score` / `trend_template` / `market_env`）TDD，再接线 `--mode full` 和 `--benchmark`；然后 4 个 skill `.md` 逐个改（删 inline python 改调 script、补漏检查、加 Moneyball）；最后 framework/guide 文档回填。spec: `docs/superpowers/specs/2026-07-23-skills-framework-alignment-design.md`。

**Tech Stack:** Python 3.14, pandas, yfinance, pytest 9.0.2。skill/framework 文档为 Markdown。

## Global Constraints

- 新字段缺数据时**省略键**（不输出 null），沿用现有风格。
- scan 模式输出与升级前字段完全一致（向后兼容，批量速度不降）；full 模式 history 用 `period="2y"`，scan 维持 `"1y"`。
- RS 代理：3/6/9/12 月收益按 **40/20/20/20** 加权（交易日窗口 63/126/189/252 bar），rs_score = 股票加权分 − SPY 加权分；`rs_pass = rs_score > 0 且股票 12 月收益 > SPY 12 月收益`。
- market_env 判定：SPY 与 QQQ 都 > MA200 → `bull`；都 < → `bear`；其余 → `chop`。
- 买入区间统一为：**轴心价 → +5%**（0-3% 理想），超 +5% 不追。
- PW EV 触发线：现价 > PW EV × 0.85 → 不追（15% 安全边际下限）。
- 已定裁决不得推翻：ATR 止损保留、入场门槛 ≥3/8 保留、BAIT /12 制保留（均回填 framework 记录）。
- 不做：VCP 自动识别、Base 计数自动化、真 IBD RS 百分位、/morning-check。
- Python: PEP 8 + 类型注解；纯函数无网络，pytest 合成序列覆盖。
- 全部 15 个既有+新增单元测试必须通过（现有 5 个 ma_metrics 测试不回归）。

---

## File Structure

- `scripts/ticker_scan.py`（修改）— 新增 4 个纯函数 + `fetch_ticker(tk, mode, spy_closes)` full 分支 + `fetch_benchmark()` + main() 两个 flag。
- `tests/test_ticker_scan.py`（修改）— 新增纯函数测试。
- `.claude/commands/stock-analyze.md` / `stock-entry.md` / `stock-exit.md` / `ticker-scan.md`（修改）— skill 对齐。
- `wiki/frameworks/sepa.md` / `bait.md` / `hot-sector-method.md`（修改）— 适配回填。
- `docs/workflow-guide.md`、`scripts/ticker_scan_guide.md`（修改）— 文档同步。

---

### Task 1: 纯函数 `atr14` + `weighted_return_score`（TDD）

**Files:**
- Modify: `scripts/ticker_scan.py`（在 `ma_metrics` 之后、`fetch_ticker` 之前插入）
- Test: `tests/test_ticker_scan.py`（追加）

**Interfaces:**
- Produces: `atr14(high: pd.Series, low: pd.Series, close: pd.Series) -> float | None`（<15 bar → None）；`weighted_return_score(closes: pd.Series) -> float | None`（<253 bar → None，加权 % 收益，round 1 位）；模块级常量 `RS_WINDOWS = ((63, 0.4), (126, 0.2), (189, 0.2), (252, 0.2))`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_ticker_scan.py` 末尾追加：

```python
from scripts.ticker_scan import atr14, weighted_return_score


def test_atr14_constant_range():
    close = pd.Series([100.0] * 30)
    high = close + 1.0
    low = close - 1.0
    assert atr14(high, low, close) == 2.0


def test_atr14_short_series_none():
    close = pd.Series([100.0] * 14)
    assert atr14(close + 1, close - 1, close) is None


def test_weighted_return_score_ascending_positive():
    closes = pd.Series([float(x) for x in range(1, 301)])
    score = weighted_return_score(closes)
    assert score is not None and score > 0


def test_weighted_return_score_flat_zero():
    closes = pd.Series([100.0] * 300)
    assert weighted_return_score(closes) == 0.0


def test_weighted_return_score_short_none():
    closes = pd.Series([float(x) for x in range(1, 253)])  # 252 bars
    assert weighted_return_score(closes) is None
```

- [ ] **Step 2: 确认失败**

Run: `python -m pytest tests/test_ticker_scan.py -v`
Expected: FAIL — `ImportError: cannot import name 'atr14'`

- [ ] **Step 3: 最小实现**

在 `scripts/ticker_scan.py` 的 `ma_metrics` 函数之后插入：

```python
RS_WINDOWS = ((63, 0.4), (126, 0.2), (189, 0.2), (252, 0.2))


def atr14(high: pd.Series, low: pd.Series, close: pd.Series) -> float | None:
    """14-day ATR (simple rolling mean of True Range). None if <15 bars."""
    if len(close) < 15:
        return None
    prev = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev).abs(), (low - prev).abs()], axis=1
    ).max(axis=1)
    val = tr.rolling(14).mean().iloc[-1]
    return float(val) if pd.notna(val) else None


def weighted_return_score(closes: pd.Series) -> float | None:
    """Minervini-style weighted return: 40% 3m + 20% each 6/9/12m (%, rounded).

    Trading-day windows 63/126/189/252 bars. None if <253 bars.
    """
    if len(closes) < 253:
        return None
    price = float(closes.iloc[-1])
    score = 0.0
    for bars, weight in RS_WINDOWS:
        past = float(closes.iloc[-(bars + 1)])
        if past == 0:
            return None
        score += weight * (price / past - 1) * 100
    return round(score, 1)
```

- [ ] **Step 4: 确认通过**

Run: `python -m pytest tests/test_ticker_scan.py -v`
Expected: PASS（10 passed：既有 5 + 新 5）

- [ ] **Step 5: 提交**

```bash
git add scripts/ticker_scan.py tests/test_ticker_scan.py
git commit -m "feat: 数据层新增 atr14 与 RS 加权收益纯函数"
```

---

### Task 2: 纯函数 `trend_template` + `market_env`（TDD）

**Files:**
- Modify: `scripts/ticker_scan.py`（在 `weighted_return_score` 之后插入）
- Test: `tests/test_ticker_scan.py`（追加）

**Interfaces:**
- Consumes: 无（独立纯函数；`trend_template` 内部自行计算 MA/52w，不调 `ma_metrics`）。
- Produces: `trend_template(closes: pd.Series, highs: pd.Series, lows: pd.Series, rs_pass: bool | None) -> dict` — <200 bar 返回 `{}`；否则返回 8 个布尔键 `p_gt_ma150_200` / `ma150_gt_ma200` / `ma200_uptrend` / `ma50_gt_ma150_200` / `p_gt_ma50` / `above_low_30` / `near_high_25` / `rs_pass`（None→False）+ `score`（0-8 int）。`market_env(spy_vs_ma200_pct: float, qqq_vs_ma200_pct: float) -> str`（"bull"/"bear"/"chop"）。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_ticker_scan.py`：

```python
from scripts.ticker_scan import market_env, trend_template


def _series(vals):
    s = pd.Series(vals)
    return s, s * 1.01, s * 0.99  # closes, highs, lows


def test_trend_template_ascending_all_pass():
    closes, highs, lows = _series([float(x) for x in range(1, 301)])
    tt = trend_template(closes, highs, lows, rs_pass=True)
    assert tt["score"] == 8
    assert all(
        tt[k]
        for k in (
            "p_gt_ma150_200", "ma150_gt_ma200", "ma200_uptrend",
            "ma50_gt_ma150_200", "p_gt_ma50", "above_low_30",
            "near_high_25", "rs_pass",
        )
    )


def test_trend_template_descending_all_fail():
    closes, highs, lows = _series([float(x) for x in range(300, 0, -1)])
    tt = trend_template(closes, highs, lows, rs_pass=False)
    assert tt["score"] == 0


def test_trend_template_short_series_empty():
    closes, highs, lows = _series([float(x) for x in range(1, 200)])  # 199 bars
    assert trend_template(closes, highs, lows, rs_pass=True) == {}


def test_trend_template_rs_none_counts_false():
    closes, highs, lows = _series([float(x) for x in range(1, 301)])
    tt = trend_template(closes, highs, lows, rs_pass=None)
    assert tt["rs_pass"] is False and tt["score"] == 7


def test_market_env_quadrants():
    assert market_env(3.0, 5.0) == "bull"
    assert market_env(-2.0, -1.0) == "bear"
    assert market_env(3.0, -1.0) == "chop"
    assert market_env(-3.0, 1.0) == "chop"
```

- [ ] **Step 2: 确认失败**

Run: `python -m pytest tests/test_ticker_scan.py -v`
Expected: FAIL — `ImportError: cannot import name 'market_env'`

- [ ] **Step 3: 最小实现**

在 `weighted_return_score` 之后插入：

```python
def trend_template(
    closes: pd.Series,
    highs: pd.Series,
    lows: pd.Series,
    rs_pass: bool | None,
) -> dict:
    """Evaluate the Minervini 8-point trend template. {} if <200 bars.

    ma200_uptrend uses the same 21-bar/+0.5% rule as ma_metrics.
    52-week window = last 252 bars (or all available if 200-251).
    rs_pass=None is treated as False (data unavailable counts as fail).
    """
    if len(closes) < 200:
        return {}
    price = float(closes.iloc[-1])
    ma50 = float(closes.rolling(50).mean().iloc[-1])
    ma150 = float(closes.rolling(150).mean().iloc[-1])
    ma200 = float(closes.rolling(200).mean().iloc[-1])

    uptrend = False
    if len(closes) >= 221:
        ma200_series = closes.rolling(200).mean()
        prev = ma200_series.iloc[-22]
        if pd.notna(prev) and prev != 0:
            uptrend = (float(ma200_series.iloc[-1]) / float(prev) - 1) * 100 > 0.5

    hi52 = float(highs.iloc[-252:].max())
    lo52 = float(lows.iloc[-252:].min())

    checks = {
        "p_gt_ma150_200": price > ma150 and price > ma200,
        "ma150_gt_ma200": ma150 > ma200,
        "ma200_uptrend": uptrend,
        "ma50_gt_ma150_200": ma50 > ma150 and ma50 > ma200,
        "p_gt_ma50": price > ma50,
        "above_low_30": lo52 > 0 and price >= lo52 * 1.30,
        "near_high_25": hi52 > 0 and price >= hi52 * 0.75,
        "rs_pass": bool(rs_pass),
    }
    checks["score"] = sum(1 for v in checks.values() if v is True)
    return checks


def market_env(spy_vs_ma200_pct: float, qqq_vs_ma200_pct: float) -> str:
    """SPY+QQQ both above MA200 -> bull; both below -> bear; else chop."""
    if spy_vs_ma200_pct > 0 and qqq_vs_ma200_pct > 0:
        return "bull"
    if spy_vs_ma200_pct < 0 and qqq_vs_ma200_pct < 0:
        return "bear"
    return "chop"
```

- [ ] **Step 4: 确认通过**

Run: `python -m pytest tests/test_ticker_scan.py -v`
Expected: PASS（15 passed）

- [ ] **Step 5: 提交**

```bash
git add scripts/ticker_scan.py tests/test_ticker_scan.py
git commit -m "feat: 数据层新增 SEPA 趋势模板与市场环境纯函数"
```

---

### Task 3: `--mode full` 接线 + docstring/guide 同步

**Files:**
- Modify: `scripts/ticker_scan.py`（`fetch_ticker` 签名与 full 分支、`main()`、模块 docstring）
- Modify: `scripts/ticker_scan_guide.md`（JSON 字段表补 full 模式字段）

**Interfaces:**
- Consumes: Task 1/2 的 `atr14` / `weighted_return_score` / `trend_template`。
- Produces: `fetch_ticker(tk: str, mode: str = "scan", spy_closes: pd.Series | None = None) -> dict`；full 模式追加键 `price` / `atr14` / `atr_pct` / `vol_avg20_m` / `vol_ratio` / `high_52w` / `low_52w` / `pct_from_52w_high` / `pct_above_52w_low` / `rs_score` / `rs_pass` / `trend_template` / `next_earnings_date` / `earnings_in_days` / `short_pct_float` / `float_m` / `shares_out_m` / `cash_m`（各自缺数据省略）。CLI：`--mode {scan,full}`。

- [ ] **Step 1: 改 `fetch_ticker` 签名与 history 窗口**

签名改为：

```python
def fetch_ticker(tk: str, mode: str = "scan", spy_closes: pd.Series | None = None) -> dict:
```

history 行改为：

```python
        h = t.history(period="2y" if mode == "full" else "1y", interval="1d")
```

- [ ] **Step 2: 在 `result.update(rev_metrics)` 之后、`return result` 之前插入 full 分支**

```python
        if mode == "full":
            closes = h["Close"]
            price = float(closes.iloc[-1])
            result["price"] = round(price, 2)

            a = atr14(h["High"], h["Low"], closes)
            if a is not None:
                result["atr14"] = round(a, 2)
                result["atr_pct"] = round(a / price * 100, 1)

            vol20 = h["Volume"].rolling(20).mean().iloc[-1]
            if pd.notna(vol20) and vol20 > 0:
                result["vol_avg20_m"] = round(float(vol20) / 1e6, 2)
                result["vol_ratio"] = round(float(h["Volume"].iloc[-1]) / float(vol20), 2)

            w = h.iloc[-252:]
            hi52 = float(w["High"].max())
            lo52 = float(w["Low"].min())
            result["high_52w"] = round(hi52, 2)
            result["low_52w"] = round(lo52, 2)
            if hi52 > 0:
                result["pct_from_52w_high"] = round((price / hi52 - 1) * 100, 1)
            if lo52 > 0:
                result["pct_above_52w_low"] = round((price / lo52 - 1) * 100, 1)

            rs_pass: bool | None = None
            stock_score = weighted_return_score(closes)
            spy_score = weighted_return_score(spy_closes) if spy_closes is not None else None
            if stock_score is not None and spy_score is not None:
                rs_score = round(stock_score - spy_score, 1)
                r12_stock = float(closes.iloc[-1]) / float(closes.iloc[-253]) - 1
                r12_spy = float(spy_closes.iloc[-1]) / float(spy_closes.iloc[-253]) - 1
                rs_pass = bool(rs_score > 0 and r12_stock > r12_spy)
                result["rs_score"] = rs_score
                result["rs_pass"] = rs_pass

            tt = trend_template(closes, h["High"], h["Low"], rs_pass)
            if tt:
                result["trend_template"] = tt

            try:
                import datetime as _dt

                cal = t.calendar
                dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
                if dates:
                    ed = dates[0]
                    if hasattr(ed, "date"):
                        ed = ed.date()
                    days = (ed - _dt.date.today()).days
                    if days >= 0:
                        result["next_earnings_date"] = ed.isoformat()
                        result["earnings_in_days"] = days
            except Exception:
                pass

            try:
                info = t.info
                spf = info.get("shortPercentOfFloat")
                if spf is not None:
                    result["short_pct_float"] = round(spf * 100, 1)
                fs = info.get("floatShares")
                if fs:
                    result["float_m"] = round(fs / 1e6, 1)
                so = info.get("sharesOutstanding")
                if so:
                    result["shares_out_m"] = round(so / 1e6, 1)
            except Exception:
                pass

            try:
                qbal = t.quarterly_balance_sheet
                if qbal is not None and not qbal.empty:
                    for name in (
                        "Cash And Cash Equivalents",
                        "Cash Cash Equivalents And Short Term Investments",
                    ):
                        if name in qbal.index:
                            v = qbal.loc[name].dropna()
                            if len(v):
                                result["cash_m"] = round(float(v.iloc[0]) / 1e6, 1)
                                break
            except Exception:
                pass
```

- [ ] **Step 3: main() 加 `--mode`，full 模式预拉 SPY**

argparse 加：

```python
    parser.add_argument("--mode", choices=("scan", "full"), default="scan",
                        help="scan=批量筛选字段；full=单股深度字段（ATR/52w/RS/财报日等）")
```

ThreadPool 调用前（`if not args.as_json:` 块之后）插入：

```python
    spy_closes = None
    if args.mode == "full":
        try:
            spy_closes = yf.Ticker("SPY").history(period="2y", interval="1d")["Close"]
        except Exception:
            pass
```

submit 行改为：

```python
        futures = {ex.submit(fetch_ticker, tk, args.mode, spy_closes): tk for tk in tickers}
```

- [ ] **Step 4: 模块 docstring 追加 full 字段段落**

docstring 的 scan 字段列表之后追加：

```
Full mode (--mode full) additional fields (each omitted when unavailable):
  price / atr14 / atr_pct
  vol_avg20_m / vol_ratio
  high_52w / low_52w / pct_from_52w_high / pct_above_52w_low
  rs_score / rs_pass          — weighted 3/6/9/12m return vs SPY (40/20/20/20)
  trend_template              — Minervini 8-point booleans + score (0-8)
  next_earnings_date / earnings_in_days
  short_pct_float / float_m / shares_out_m / cash_m
```

- [ ] **Step 5: `scripts/ticker_scan_guide.md` JSON 字段表同步**

在 `"max_gap_up_pct"` 行之后（JSON 示例 `}` 之前）追加注释块：

```
  // ---- 以下字段仅 --mode full 输出（单股深度，各自缺数据省略）----
  "price": 8.42,              // 最新收盘价
  "atr14": 0.61, "atr_pct": 7.2,          // 14日ATR / 占现价%
  "vol_avg20_m": 3.1, "vol_ratio": 1.8,   // 20日均量(百万股) / 今日量比
  "high_52w": 12.4, "low_52w": 3.1,       // 52周高低
  "pct_from_52w_high": -32.1, "pct_above_52w_low": 171.6,
  "rs_score": 14.2, "rs_pass": true,      // RS加权收益差 vs SPY
  "trend_template": {"score": 6},          // SEPA 8条布尔+score
  "next_earnings_date": "2026-08-07", "earnings_in_days": 15,
  "short_pct_float": 12.3, "float_m": 45.2, "shares_out_m": 51.0,
  "cash_m": 88.5
```

- [ ] **Step 6: 回归 + 冒烟**

Run: `python -m pytest tests/test_ticker_scan.py -q`
Expected: 15 passed

Run: `python scripts/ticker_scan.py NVDA --json`
Expected: 字段与升级前 scan 输出完全一致（无新键）

Run: `python scripts/ticker_scan.py NVDA --mode full --json`
Expected: 含 `price`、`atr14`、`trend_template`（score 0-8）、`rs_score`、`high_52w`、`short_pct_float` 等

- [ ] **Step 7: 提交**

```bash
git add scripts/ticker_scan.py scripts/ticker_scan_guide.md
git commit -m "feat: ticker_scan 新增 --mode full 深度字段（ATR/52w/RS/趋势模板/财报日/筹码/现金）"
```

---

### Task 4: `--benchmark` 市场环境

**Files:**
- Modify: `scripts/ticker_scan.py`（新增 `fetch_benchmark()`、main() flag）

**Interfaces:**
- Consumes: `ma_metrics`、`market_env`（Task 2）。
- Produces: `fetch_benchmark() -> dict`，输出 `{"benchmark": true, "spy_vs_ma200_pct": X, "qqq_vs_ma200_pct": Y, "market_env": "bull|bear|chop"}`；CLI `--benchmark`（可单独用，也可与 ticker 同用，benchmark 行先输出）。

- [ ] **Step 1: 实现 `fetch_benchmark`（放在 `fetch_ticker` 之后）**

```python
def fetch_benchmark() -> dict:
    """SPY/QQQ vs MA200 -> market environment (bull/chop/bear)."""
    out: dict = {"benchmark": True}
    for sym, key in (("SPY", "spy_vs_ma200_pct"), ("QQQ", "qqq_vs_ma200_pct")):
        try:
            h = yf.Ticker(sym).history(period="2y", interval="1d")
            m = ma_metrics(h["Close"])
            if "ma200_pct" in m:
                out[key] = m["ma200_pct"]
        except Exception:
            pass
    if "spy_vs_ma200_pct" in out and "qqq_vs_ma200_pct" in out:
        out["market_env"] = market_env(out["spy_vs_ma200_pct"], out["qqq_vs_ma200_pct"])
    return out
```

- [ ] **Step 2: main() 加 flag，允许无 ticker 仅 benchmark**

argparse 加：

```python
    parser.add_argument("--benchmark", action="store_true",
                        help="输出 SPY/QQQ vs MA200 市场环境行")
```

`if not tickers:` 块改为：

```python
    if not tickers and not args.benchmark:
        print("Usage: ticker_scan.py TICKER1 TICKER2 ... [--json] [--mode full] [--benchmark]")
        sys.exit(1)
```

在 ticker 扫描循环之前插入：

```python
    if args.benchmark:
        b = fetch_benchmark()
        print(json.dumps(b) if args.as_json else
              f"MARKET   env={b.get('market_env', '—')}  "
              f"SPY vs MA200={b.get('spy_vs_ma200_pct', '—')}%  "
              f"QQQ vs MA200={b.get('qqq_vs_ma200_pct', '—')}%")
```

ticker 为空时跳过 ThreadPool（把扫描块包进 `if tickers:`）。

- [ ] **Step 3: 回归 + 冒烟**

Run: `python -m pytest tests/test_ticker_scan.py -q` → 15 passed
Run: `python scripts/ticker_scan.py --benchmark --json` → 一行 benchmark JSON，含 market_env
Run: `python scripts/ticker_scan.py NVDA --mode full --benchmark --json` → 第一行 benchmark，第二行 NVDA full

- [ ] **Step 4: 提交**

```bash
git add scripts/ticker_scan.py
git commit -m "feat: ticker_scan 新增 --benchmark 市场环境判定"
```

---

### Task 5: stock-analyze 对齐（数据层 + BAIT 判据 + Moneyball EV）

**Files:**
- Modify: `.claude/commands/stock-analyze.md`

行号为约数——**以引用文本为锚**。

- [ ] **Step 1: 替换 Step 1 整段 inline python**

把 `### 1. 拉取量化数据（yfinance）` 标题到该 python 代码块结束（`print(f"空头={short_pct:.1f}%..." ...)` 之后的 ` ``` `）整段替换为：

````markdown
### 1. 拉取量化数据（共用数据层）

```bash
python scripts/ticker_scan.py TICKER --mode full --benchmark --json
```

输出两行 JSON：第一行 benchmark（`spy_vs_ma200_pct` / `qqq_vs_ma200_pct` / `market_env`），第二行 ticker 深度数据。本报告使用的关键字段：

- 价格/波动：`price`、`atr14`、`atr_pct`、`ma50_pct`、`ma150_pct`、`ma200_pct`、`ma200_trend`
- 52 周位置：`high_52w`、`low_52w`、`pct_from_52w_high`、`pct_above_52w_low`
- SEPA：`trend_template`（8 条布尔 + score）、`rs_score`、`rs_pass`
- 财务：`revenue_yoy_pct`、`consecutive_growth_q`、`eps_trend`、`cash_m`、`market_cap_m`
- 筹码：`short_pct_float`、`float_m`、`shares_out_m`、`inst_pct`
- 日历：`next_earnings_date`、`earnings_in_days`
````

- [ ] **Step 2: BAIT 节注入 framework 判据 + overlap 换算**

在 BAIT 评分表（`| **T — Technical** | ... |` 行）之后、`**解读：**` 之前插入：

```markdown
**各维度评分判据（对齐 `wiki/frameworks/bait.md`）：**

- **B**：可识别的情绪催化剂？恐惧是否被财报数据证伪？short interest >10% = 高、>20% = 极端
- **A**：自建模型 vs 共识差 >20%（关键指标）？覆盖分析师 <3 名？有被媒体/卖方跳过的具体财务行项？
- **I**：transcript Q&A / 10-K 注脚 / proxy / investor day 中有具体、可量化、未被报道的信息？
- **T**：多个技术因素在同一价位汇聚？（高空头 + 回购 + 指数机制 + 期权结构）

**Overlap 换算（裁决以此为准，/12 总分仅展示）：**
`overlap = (B≥2) + (A≥2) + (I≥2) + (T≥2)` → 1 弱 / 2 中等 / 3 强 / 4 极强（对应 bait.md 裁决表）
```

- [ ] **Step 3: SEPA 节改用 trend_template 字段**

把 SEPA 节 8 条表格下方 `**Stage 判断：**` 之前，紧接 8 条表格后插入：

```markdown
8 条状态直接读 Step 1 的 `trend_template` 字段（`score` = X/8）；#8 用 `rs_pass` 判定并附 `rs_score` 数字（正 = 跑赢 SPY 加权收益）。禁止在无数据时凭印象打 ✅。
```

并把 8 条表格中第 8 行 `| 8 | 相对强度 > 70百分位 | ✅/⚠️/❌ |` 改为：

```markdown
| 8 | 相对强度跑赢大盘（`rs_pass`，代理 IBD RS>70）| ✅/❌ + rs_score |
```

- [ ] **Step 4: 新增 Moneyball 节 + 后续节改号**

把 `### 6. 综合结论` 改为 `### 7. 综合结论`，`### 7. 输出报告` 改为 `### 8. 输出报告`。在（原）`### 6. 综合结论` 之前插入：

```markdown
### 6. Moneyball 情景 EV（对齐 `wiki/frameworks/moneyball.md`）

三情景概率和必须 = 100%。每个情景给终值算式（`[年] EBITDA/营收 $X × [倍数] = $Z/股`）。

| 情景 | 目标价 | 时间跨度 | 关键假设（2-3条） | 概率 |
|------|--------|---------|------------------|------|
| 🐂 Bull | $X | X 年 | ... | 20-35% |
| Base | $Y | X 年 | ... | 45-60% |
| 🐻 Bear | $Z | X 年 | ... | 15-30% |

```
EV = Bull×P + Base×P + Bear×P
Expected Return = (EV − 现价) / 现价
Asymmetry = Bull 上行% / Bear 下行%
```

**必答三问：**
1. Bear 成立需要什么为真？当前数据支持吗？
2. Bear 是否已 priced in？（已跌 30%+ 时 bear 数学要重算）
3. 解决不确定性的具体催化剂是什么？（下次财报 / FDA / 合同）

**PW EV 触发线**（synthesis.md 优先级规则）：现价 > EV × 0.85 → 即使 BAIT 强、SEPA 好也不追。

---
```

- [ ] **Step 5: 输出报告模板同步**

模板中 `## 五、翻倍股专项` 之后、`## 六、风险` 之前插入：

```markdown
## 六、Moneyball 情景 EV

| 情景 | 目标价 | 概率 | 关键假设 |
|------|--------|------|---------|
| 🐂 Bull | $X | X% | [1-2句] |
| Base | $Y | Y% | [1-2句] |
| 🐻 Bear | $Z | Z% | [1-2句] |

**EV：$W | 现价：$P | 预期收益：+X% | 非对称比：X:1**
**PW EV 触发线：现价 [≤/＞] EV×0.85 = $X → [可追 / 不追]**

---
```

原 `## 六、风险` 改 `## 七、风险`，原 `## 七、结论` 改 `## 八、结论`。BAIT 表格总评行后加 `**Overlap：X 因子重叠 — [弱/中等/强/极强]**`。脚注 `*框架：Mauboussin BAIT | Minervini SEPA*` 改为 `*框架：Mauboussin BAIT | Minervini SEPA | Moneyball EV*`。

- [ ] **Step 6: 核实 + 提交**

Run: `grep -n "mode full\|Moneyball\|overlap\|rs_pass\|EV × 0.85\|EV×0.85" .claude/commands/stock-analyze.md`
Expected: 各处命中（≥6 行）；`grep -c "rolling(252)" .claude/commands/stock-analyze.md` = 0（bug 代码已删）

```bash
git add .claude/commands/stock-analyze.md
git commit -m "feat: stock-analyze 接共用数据层+BAIT判据+Moneyball EV 节"
```

---

### Task 6: stock-entry 对齐（数据层 + 财报/市场环境 + 买入区 + PW EV）

**Files:**
- Modify: `.claude/commands/stock-entry.md`

- [ ] **Step 1: 替换 Step 2 inline python**

把 `### 2. 拉取当前价格数据 + ATR（yfinance）` 标题及其整个 python 代码块替换为：

````markdown
### 2. 拉取当前数据（共用数据层）

```bash
python scripts/ticker_scan.py TICKER --mode full --benchmark --json
```

使用字段：`price`、`atr14`、`atr_pct`、`ma50_pct`/`ma150_pct`/`ma200_pct`、`vol_avg20_m`、`vol_ratio`、`trend_template.score`、`earnings_in_days`、benchmark 行 `market_env`。
````

- [ ] **Step 2: Step 3 入场条件加两条检查 + 买入区改口径**

在 checklist（4 个 `- [ ]`）末尾追加：

```markdown
- [ ] 财报距离：`earnings_in_days > 14`（≤14 → ⚠️ SEPA 规则：财报前 2 周不入场，结论标"等财报后"）
- [ ] 市场环境（`market_env`）：`bear` → ❌ 不建新仓（SEPA 第六节主开关）；`chop` → 单笔风险降至 0.5%；`bull` → 1%
```

把 `**入场区间：** 轴心点上方 0-3% 为理想区。超出 1 ATR 以上不追。` 替换为：

```markdown
**入场区间：** 轴心价 → +5% 为买入区（0-3% 理想）。超过 +5% 不追，等下次形态（SEPA 原典口径）。
```

- [ ] **Step 3: Step 5 之后加 PW EV 触发线**

在 Step 5（目标价 + R/R）代码块之后、自由股规则行之前插入：

```markdown
**Moneyball PW EV 触发线（必查）：**
读 `wiki/tickers/[TICKER]/analysis.md` 的「Moneyball 情景 EV」节：
- 现价 ≤ EV × 0.85 → ✅ 有安全边际，可执行入场
- 现价 > EV × 0.85 → ❌ 不追，等回调或等 EV 重估（synthesis.md 优先级规则 #5）
- analysis.md 无 EV 节 → 先重跑 `/stock-analyze [TICKER]`
```

- [ ] **Step 4: Step 6 仓位公式随市场环境**

把 `单笔风险 = 总资金 × 1%` 行改为：

```
单笔风险 = 总资金 × R%（R 由 market_env 决定：bull=1%，chop=0.5%，bear=不建仓）
建议股数 = (总资金 × R%) ÷ (入场价 - 止损价)
```

- [ ] **Step 5: 输出模板加三行**

模板 `## 当前状态` 列表追加：

```markdown
- 市场环境：[bull / chop / bear]（SPY vs MA200 X% | QQQ X%）→ 单笔风险 R%
- 财报距离：X 天 [✅ >14 / ⚠️ ≤14 等财报后]
- PW EV 对照：现价 $X vs EV×0.85 = $X → [✅ 可入 / ❌ 不追]
```

- [ ] **Step 6: 核实 + 提交**

Run: `grep -n "mode full\|earnings_in_days\|market_env\|EV × 0.85\|轴心价 → +5%" .claude/commands/stock-entry.md`
Expected: ≥5 处命中；`grep -c "rolling(50)" .claude/commands/stock-entry.md` = 0

```bash
git add .claude/commands/stock-entry.md
git commit -m "feat: stock-entry 接数据层+财报/市场环境检查+PW EV 触发线"
```

---

### Task 7: stock-exit tagline/EV + ticker-scan 小修

**Files:**
- Modify: `.claude/commands/stock-exit.md`
- Modify: `.claude/commands/ticker-scan.md`

- [ ] **Step 1: stock-exit tagline 修正**

第 3 行 `基于 Moneyball 框架，给出翻倍候选股的止损触发逻辑、止盈节奏和减仓建议。` 替换为：

```markdown
基于免费股策略（hot-sector）+ SEPA 止损纪律 + Moneyball 目标价管理，给出翻倍候选股的止损触发逻辑、止盈节奏和减仓建议。
```

- [ ] **Step 2: stock-exit Step 1 加 EV 读取**

Step 1 提取列表追加一条：

```markdown
- `wiki/tickers/[TICKER]/analysis.md` 的 Moneyball EV / Bull / Bear 目标价（无则跳过 EV 对照）
```

- [ ] **Step 3: stock-exit Step 2 替换 inline python**

把 `### 2. 拉取当前价格数据（yfinance）` 标题及整个 python 代码块替换为：

````markdown
### 2. 拉取当前数据（共用数据层）

```bash
python scripts/ticker_scan.py TICKER --mode full --json
```

使用字段：`price`、`atr14`、`atr_pct`、`ma50_pct`/`ma150_pct`/`ma200_pct`、`vol_ratio`、`ma200_trend`。
````

- [ ] **Step 4: stock-exit 止盈进度表加 EV 行**

输出模板「止盈进度」表在自由股行之后加：

```markdown
| Moneyball EV 对照 | EV $X / Bull $X | 现价 > Bull 目标 → ⚠️ 估值透支，考虑加速减仓 |
```

- [ ] **Step 5: ticker-scan 两处小修**

2C 表 #2 行替换为：

```markdown
| 2 | 积压订单覆盖 ≥2 季度收入（客户集中度可接受？）| WebSearch | query: `"[TICKER] backlog guidance Q1 Q2 2026"`，顺带留意客户集中度；集中度无数据 → 注明 ⚠️ 不影响主判定 | ✅/⚠️/❌ + 原文摘录 |
```

Stage 2 六大类型表 #5 行判断规则 `` `inst_pct > 5` → ⚠️；`inst_pct > 15` 且趋势上升 → ✅ `` 替换为：

```markdown
`inst_pct > 15` → ✅；5–15 → ⚠️；<5 或无数据 → LLM 判断
```

- [ ] **Step 6: 核实 + 提交**

Run: `grep -n "免费股策略（hot-sector）\|Moneyball EV\|客户集中度\|inst_pct > 15" .claude/commands/stock-exit.md .claude/commands/ticker-scan.md`
Expected: 4 处均命中；`grep -c "rolling(50)" .claude/commands/stock-exit.md` = 0

```bash
git add .claude/commands/stock-exit.md .claude/commands/ticker-scan.md
git commit -m "fix: stock-exit 框架标签/EV对照 + ticker-scan 客户集中度与机构规则"
```

---

### Task 8: Framework 回填 + workflow-guide 同步

**Files:**
- Modify: `wiki/frameworks/sepa.md`、`wiki/frameworks/bait.md`、`wiki/frameworks/hot-sector-method.md`、`docs/workflow-guide.md`

- [ ] **Step 1: sepa.md 加适配表**

在 `## 七、在本 Wiki 中的应用` 表格之后、`## 交叉引用` 之前插入：

```markdown
### 本 wiki 适配记录（对原典的故意偏离，均已裁决保留）

| 适配 | 原典 | 本 wiki | 理由 |
|------|------|---------|------|
| 止损宽度 | ≤7-8% 硬止损 | max(2×ATR14, 10%)，上限 20% | 翻倍小盘日波 5-10%，固定窄止损被噪音洗出 |
| 入场资格 | <5/8 Skip | ≥3/8 可进入场评估（缺失项必须列明） | 翻倍候选常处 Stage1→2 早期，5/8 会系统性错过 |
| 止损确认 | 触价即止损 | 连续 2 日收盘低于止损位才触发 | 高波动小盘单日插针频繁 |
| MA 出场 | +15% 后沿 20MA 移动止损 | 连续 3 日跌破 MA150 出场 | 与免费股长持周期匹配 |
| RS 数据 | IBD RS 百分位 | rs_score：3/6/9/12月收益 40/20/20/20 加权 vs SPY | 无全市场 universe，用加权收益差代理 |
```

- [ ] **Step 2: bait.md 加 /12 映射**

在 `## BAIT Verdict` 表之后、Template verdict 引文之前插入：

```markdown
**本 wiki /stock-analyze 换算规则**：skill 使用 0-3 分 × 4 维 = /12 制展示粒度；裁决换算 `overlap = (B≥2)+(A≥2)+(I≥2)+(T≥2)`，overlap 数对应上表（1 弱 / 2 中 / 3 强 / 4 极强）。/12 总分仅作展示，裁决以 overlap 为准。
```

- [ ] **Step 3: hot-sector-method.md 三处量化回填**

六大类型表 #5 行 `| 5 | 机构开始建仓 | 13F 或成交量异常增加？ |` 改为：

```markdown
| 5 | 机构开始建仓 | 13F 或成交量异常增加？（量化：inst_pct >15% ✅ / 5-15% ⚠️）|
```

六大类型表 #6 行 `| 6 | 市值小，上涨空间大 | **必须主板上市，非 OTC** |` 改为：

```markdown
| 6 | 市值小，上涨空间大 | **必须主板上市，非 OTC**（量化分档：<$2B ✅ / $2-5B ⚠️ / >$5B ❌；五大公式#5 用 <$5B）|
```

四、风险纪律表「止盈提醒」行 `| **止盈提醒** | 多只核心持仓同时大幅上涨后，主动锁定本金 + 部分盈利，不追高 |` 改为：

```markdown
| **止盈提醒** | 多只核心持仓同时大幅上涨后，主动锁定本金 + 部分盈利，不追高（量化：3+ 持仓各涨 20%+ 集中 2-4 周 → 全组合减 20-30%；赛道 ETF 单月 >30% → 赛道内减 25-30%；VIX>35 → 停新仓）|
```

2C 表 #5 行 `| 5 | **基本面 + 技术面配合** | 财报验证后，价格结构（周/月K）是否同步确认？ |` 改为：

```markdown
| 5 | **基本面 + 技术面配合** | 财报验证后，价格结构（周/月K）是否同步确认？→ 日线代理见 `/ticker-scan` 四条子检查 + 价格结构否决表 |
```

- [ ] **Step 4: workflow-guide.md 同步**

第二步（`研究报告保存：` 行之前）插入：

```markdown
### Moneyball 情景 EV — 翻倍路径的概率化

| 情景 | 目标价 | 概率 |
|------|--------|------|
| 🐂 Bull | $X | 20-35% |
| Base | $Y | 45-60% |
| 🐻 Bear | $Z | 15-30% |

**EV = Σ(目标价 × 概率)**。买入触发线：**现价 ≤ EV × 0.85**（15% 安全边际）才可执行入场；高于此线即使技术面好也不追。
```

第三步「金字塔式建仓」之前插入：

```markdown
### 入场前三道闸（顺序检查）

1. **财报距离**：财报前 2 周不入场（`earnings_in_days ≤ 14` → 等财报后）
2. **市场环境**：SPY+QQQ 都在 MA200 上 = bull（单笔风险 1%）；都在下 = bear（不建新仓）；其余 chop（0.5%）
3. **PW EV 触发线**：现价 > EV × 0.85 → 不追
```

- [ ] **Step 5: 核实 + 提交**

Run: `grep -n "本 wiki 适配记录\|overlap = \|量化分档\|入场前三道闸\|EV × 0.85" wiki/frameworks/sepa.md wiki/frameworks/bait.md wiki/frameworks/hot-sector-method.md docs/workflow-guide.md`
Expected: 各文件均命中

```bash
git add wiki/frameworks/sepa.md wiki/frameworks/bait.md wiki/frameworks/hot-sector-method.md docs/workflow-guide.md
git commit -m "docs: frameworks 回填 skill 适配记录 + workflow-guide 同步 EV/三道闸"
```

---

## 验证全流程（全部任务完成后）

- [ ] `python -m pytest tests/test_ticker_scan.py -q` → 15 passed
- [ ] `python scripts/ticker_scan.py NVTS --json` → 与升级前 scan 字段一致
- [ ] `python scripts/ticker_scan.py NVTS --mode full --benchmark --json` → benchmark 行 + full 字段齐全
- [ ] 4 个 skill `.md` 无残留 inline yfinance 代码块（`grep -l "yf.Ticker" .claude/commands/` 只应剩 0 个文件）
- [ ] spec 的 B1-B4 / G1-G4 / D1-D5 逐项能指到对应改动
- [ ] `git log --oneline -8` → 8 个提交（Task 1-8 各一）
