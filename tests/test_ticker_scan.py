import pandas as pd

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
