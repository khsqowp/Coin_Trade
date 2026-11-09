import math
import pytest
from indicators import rsi, ema, atr, macd, bollinger, summarize_candles


def candles(values):
    return [[i * 900000, v, v + 1, v - 1, v, 10] for i, v in enumerate(values)]


def test_rsi_hand_wilder():
    # Two-period gains [1, 0], losses [0, 1]; then gain 2 updates to 1.25 / 0.25.
    assert rsi([10, 11, 10], 2) == 50
    assert rsi([10, 11, 10, 12], 2) == pytest.approx(100 - 100 / 6)
    assert rsi(list(range(16))) == 100
    assert rsi(list(range(16, 0, -1))) == 0
    assert rsi([1] * 15) == 50
    assert rsi([1] * 14) is None


def test_ema_hand():
    # Seed mean 2, alpha 1/2: 3, then 4.
    assert ema([1, 2, 3, 4, 5], 3) == 4
    assert ema([1, 2], 3) is None


def test_atr_hand():
    data = [[0, 10, 11, 9, 10, 1], [1, 12, 13, 11, 12, 1], [2, 13, 14, 12, 13, 1]]
    # True ranges 2,3,2; seed 2.5, Wilder update 2.25.
    assert atr(data, 2) == 2.25
    assert atr(data, 14) is None


def test_macd_hand():
    # fast=2: seed 1.5 -> 2.5 -> 3.5 -> 4.5; slow=3: 2 ->3 ->4.
    assert macd([1, 2, 3, 4, 5], 2, 3, 2) == pytest.approx((0.5, 0.5, 0))
    assert macd([1, 2]) == (None, None, None)


def test_bollinger_population():
    upper, mid, lower = bollinger([1, 2, 3], 3, 2)
    assert mid == 2 and upper == pytest.approx(2 + 2 * math.sqrt(2 / 3))
    assert lower == pytest.approx(2 - 2 * math.sqrt(2 / 3))


def test_summary():
    s = summarize_candles(candles(list(range(1, 251))))
    assert s["last_close"] == 250 and len(s["bars"]) == 24
    assert s["ema200"] is not None and s["returns"]["1"] == pytest.approx(
        (250 / 249 - 1) * 100
    )
    assert summarize_candles([])["last_close"] is None
