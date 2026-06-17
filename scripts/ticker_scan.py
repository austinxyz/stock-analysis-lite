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
  ma200_pct       — price vs 200-day MA (%, null if <200 days history)
  max_gap_up_pct  — largest single-day open gap-up in last 1y (proxy for earnings gap behaviour)
  error           — present only if fetch failed
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


def fetch_ticker(tk: str) -> dict:
    try:
        t = yf.Ticker(tk)

        # Price history — MAs + gap detection
        h = t.history(period="1y", interval="1d")
        if len(h) < 10:
            return {"ticker": tk, "error": "insufficient price history"}

        price = float(h["Close"].iloc[-1])
        ma50 = float(h["Close"].rolling(50).mean().iloc[-1])
        ma50_pct = round((price / ma50 - 1) * 100, 1)

        ma200_pct = None
        if len(h) >= 200:
            ma200 = float(h["Close"].rolling(200).mean().iloc[-1])
            ma200_pct = round((price / ma200 - 1) * 100, 1)

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Hot-sector stock quantitative fundamentals scan")
    parser.add_argument("tickers", nargs="*", metavar="TICKER")
    parser.add_argument("--tickers", nargs="+", dest="extra_tickers", metavar="TICKER")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Output raw JSON lines (one per ticker)")
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

    with ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as ex:
        futures = {ex.submit(fetch_ticker, tk): tk for tk in tickers}
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
