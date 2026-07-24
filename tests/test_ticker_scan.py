import pandas as pd

from scripts.ticker_scan import ma_metrics, atr14, weighted_return_score


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
