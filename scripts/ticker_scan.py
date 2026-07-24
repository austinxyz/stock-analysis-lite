#!/usr/bin/env python3
"""
ticker_scan.py — quantitative fundamentals layer for /ticker-scan skill

Fetches yfinance data for hot-sector stock screening (2A/2B/2C scoring).
Called by the /ticker-scan skill before LLM qualitative evaluation.

Usage:
  py scripts/ticker_scan.py GCTS LWLG AAOI
  py scripts/ticker_scan.py GCTS LWLG --json

JSON fields per ticker (one line per ticker):
  ticker          — uppercase symbol
  exchange        — e.g. "NMS", "NYQ", "OTC"
  is_otc          — bool; OTC/Pink → excluded from scan
  market_cap_m    — market cap in USD millions (null if unavailable)
  revenue_yoy_pct — latest Q revenue vs same Q prior year (%, null if <5Q data)
  revenue_accel   — bool: last QoQ growth > prior QoQ (null if <3Q data)
  consecutive_growth_q — quarters of consecutive revenue growth (from most recent)
  eps_trend       — "loss→profit" | "profit→loss" | "improving" | "declining" | "stable" | "unknown"
  inst_pct        — institutional ownership % (null if unavailable)
  ma50_pct        — price vs 50-day MA (%)
  ma150_pct       — price vs 150-day MA (%, omitted if <150 days history)
  ma200_pct       — price vs 200-day MA (%, omitted if <200 days history)
  ma200_trend     — "up"/"down"/"flat": MA200 vs 21 bars ago (omitted if <221 days)
  max_gap_up_pct  — largest single-day open gap-up in last 1y (proxy for earnings gap behaviour)
  error           — present only if fetch failed

Full mode (--mode full) additional fields (each omitted when unavailable):
  price / atr14 / atr_pct
  vol_avg20_m / vol_ratio
  high_52w / low_52w / pct_from_52w_high / pct_above_52w_low
  rs_score / rs_pass          — weighted 3/6/9/12m return vs SPY (40/20/20/20)
  trend_template              — Minervini 8-point booleans + score (0-8)
  next_earnings_date / earnings_in_days
  short_pct_float / float_m / shares_out_m / cash_m
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OTC_MARKERS = {"OTC", "PNK", "OTCMKTS", "OTCQB", "OTCQX", "BTS", "GREY"}


def _is_otc(exchange: str) -> bool:
    ex = (exchange or "").upper()
    return ex in OTC_MARKERS or "OTC" in ex


def _revenue_metrics(fin: pd.DataFrame) -> dict:
    for name in ("Total Revenue", "Revenue"):
        if name in fin.index:
            rev = fin.loc[name].dropna().sort_index(ascending=False)
            break
    else:
        return {}

    vals = list(rev.values)
    result: dict = {}

    # YoY: latest Q vs same Q 4 quarters ago; fallback to sequential QoQ
    if len(vals) >= 5 and vals[4] != 0:
        result["revenue_yoy_pct"] = round((vals[0] / vals[4] - 1) * 100, 1)
    elif len(vals) >= 2 and vals[1] != 0:
        result["revenue_yoy_pct"] = round((vals[0] / vals[1] - 1) * 100, 1)

    # Acceleration: last QoQ growth rate vs prior QoQ growth rate
    if len(vals) >= 3 and vals[1] != 0 and vals[2] != 0:
        g1 = vals[0] / vals[1] - 1
        g2 = vals[1] / vals[2] - 1
        result["revenue_accel"] = bool(g1 > g2)

    # Consecutive quarters of revenue growth (most-recent streak)
    consec = 0
    for i in range(len(vals) - 1):
        if vals[i] > vals[i + 1]:
            consec += 1
        else:
            break
    result["consecutive_growth_q"] = consec

    return result


def _eps_trend(fin: pd.DataFrame) -> str:
    for name in (
        "Net Income",
        "Net Income Common Stockholders",
        "Net Income Applicable To Common Shares",
    ):
        if name in fin.index:
            ni = fin.loc[name].dropna().sort_index(ascending=False)
            break
    else:
        return "unknown"

    vals = list(ni.values)
    if len(vals) < 2:
        return "unknown"

    recent = vals[0]
    past = vals[1:5]

    if recent > 0 and any(v < 0 for v in past):
        return "loss→profit"
    if recent < 0 and len(past) >= 2 and all(v > 0 for v in past[:2]):
        return "profit→loss"
    if recent > 0 and vals[0] > vals[1]:
        return "improving"
    if recent < 0:
        return "declining"
    return "stable"


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


def fetch_ticker(tk: str, mode: str = "scan", spy_closes: pd.Series | None = None) -> dict:
    try:
        t = yf.Ticker(tk)

        # Price history — MAs + gap detection
        h = t.history(period="2y" if mode == "full" else "1y", interval="1d")
        if len(h) < 10:
            return {"ticker": tk, "error": "insufficient price history"}

        ma = ma_metrics(h["Close"])

        # Largest single-day open gap-up (proxy for earnings gap behaviour)
        gap_series = (h["Open"] - h["Close"].shift(1)) / h["Close"].shift(1) * 100
        max_gap_up = round(float(gap_series.max()), 1)

        # Exchange + market cap via fast_info (no HTTP overhead)
        exchange = ""
        market_cap_m = None
        try:
            fi = t.fast_info
            exchange = str(getattr(fi, "exchange", "") or "")
            mc = getattr(fi, "market_cap", None)
            if mc:
                market_cap_m = round(mc / 1_000_000, 1)
        except Exception:
            info = t.info
            exchange = info.get("exchange", "")
            mc = info.get("marketCap")
            if mc:
                market_cap_m = round(mc / 1_000_000, 1)

        is_otc = _is_otc(exchange)

        # Institutional ownership (requires t.info — slower)
        inst_pct = None
        try:
            val = t.info.get("heldPercentInstitutions")
            if val is not None:
                inst_pct = round(val * 100, 1)
        except Exception:
            pass

        # Quarterly fundamentals
        rev_metrics: dict = {}
        eps_trend = "unknown"
        try:
            fin = t.quarterly_financials
            if fin is not None and not fin.empty:
                rev_metrics = _revenue_metrics(fin)
                eps_trend = _eps_trend(fin)
        except Exception:
            pass

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

        return result

    except Exception as e:
        return {"ticker": tk, "error": str(e)}


def print_result(r: dict) -> None:
    if "error" in r:
        print(f"{r['ticker']:8s}  ERROR: {r['error']}")
        return
    otc_flag = " [OTC]" if r.get("is_otc") else ""
    cap = f"${r['market_cap_m']:,.0f}M" if r.get("market_cap_m") else "—"
    yoy = f"{r['revenue_yoy_pct']:+.1f}%" if "revenue_yoy_pct" in r else "—"
    accel = "↑" if r.get("revenue_accel") else " "
    consec = f"{r.get('consecutive_growth_q', 0)}Q"
    inst = f"{r['inst_pct']:.1f}%" if "inst_pct" in r else "—"
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Hot-sector stock quantitative fundamentals scan")
    parser.add_argument("tickers", nargs="*", metavar="TICKER")
    parser.add_argument("--tickers", nargs="+", dest="extra_tickers", metavar="TICKER")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Output raw JSON lines (one per ticker)")
    parser.add_argument("--mode", choices=("scan", "full"), default="scan",
                        help="scan=批量筛选字段；full=单股深度字段（ATR/52w/RS/财报日等）")
    args = parser.parse_args()

    tickers = [t.upper() for t in (args.tickers or [])]
    if args.extra_tickers:
        tickers += [t.upper() for t in args.extra_tickers]
    tickers = list(dict.fromkeys(tickers))

    if not tickers:
        print("Usage: ticker_scan.py TICKER1 TICKER2 ... [--json]")
        sys.exit(1)

    if not args.as_json:
        print(f"Scanning {len(tickers)} ticker(s): {', '.join(tickers)}\n")

    spy_closes = None
    if args.mode == "full":
        try:
            spy_closes = yf.Ticker("SPY").history(period="2y", interval="1d")["Close"]
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as ex:
        futures = {ex.submit(fetch_ticker, tk, args.mode, spy_closes): tk for tk in tickers}
        results: dict[str, dict] = {}
        for f in as_completed(futures):
            results[futures[f]] = f.result()

    for tk in tickers:
        r = results[tk]
        if args.as_json:
            print(json.dumps(r))
        else:
            print_result(r)


if __name__ == "__main__":
    main()
