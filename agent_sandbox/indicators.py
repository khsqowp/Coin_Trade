"""Indicators on closed OHLCV bars; insufficient history returns None."""

from typing import Any
import math
import statistics


def ema(values: list[float], period: int) -> float | None:
    series = ema_series(values, period)
    return series[-1] if series else None


def ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    result = [sum(values[:period]) / period]
    alpha = 2 / (period + 1)
    for v in values[period:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [b - a for a, b in zip(values, values[1:])]
    gain = sum(max(c, 0) for c in changes[:period]) / period
    loss = sum(max(-c, 0) for c in changes[:period]) / period
    for c in changes[period:]:
        gain = (gain * (period - 1) + max(c, 0)) / period
        loss = (loss * (period - 1) + max(-c, 0)) / period
    if loss == 0:
        return 100.0 if gain else 50.0
    return 100 - 100 / (1 + gain / loss)


def atr(candles: list[list[Any]], period: int = 14) -> float | None:
    if len(candles) < period:
        return None
    ranges = []
    for i, c in enumerate(candles):
        high, low = float(c[2]), float(c[3])
        prev = float(candles[i - 1][4]) if i else float(c[4])
        ranges.append(max(high - low, abs(high - prev), abs(low - prev)))
    value = sum(ranges[:period]) / period
    for r in ranges[period:]:
        value = (value * (period - 1) + r) / period
    return value


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float | None, float | None, float | None]:
    f, s = ema_series(values, fast), ema_series(values, slow)
    if not s:
        return None, None, None
    line = [a - b for a, b in zip(f[slow - fast :], s)]
    sig = ema(line, signal)
    return line[-1], sig, line[-1] - sig if sig is not None else None


def bollinger(
    values: list[float], period: int = 20, deviations: float = 2
) -> tuple[float | None, float | None, float | None]:
    if len(values) < period:
        return None, None, None
    window = values[-period:]
    mid = statistics.mean(window)
    sd = statistics.pstdev(window)
    return mid + deviations * sd, mid, mid - deviations * sd


def summarize_candles(candles: list[list[Any]]) -> dict[str, Any]:
    if not candles:
        return {"last_close": None, "bars": []}
    closes = [float(c[4]) for c in candles]
    last = closes[-1]
    av = atr(candles)
    m, s, h = macd(closes)
    upper, mid, lower = bollinger(closes)
    result = {
        "last_close": last,
        "rsi": rsi(closes),
        "ema20": ema(closes, 20),
        "ema50": ema(closes, 50),
        "ema200": ema(closes, 200),
        "atr": av,
        "atr_pct": av / last * 100 if av is not None and last else None,
        "macd": m,
        "macd_signal": s,
        "hist": h,
        "bb_upper": upper,
        "bb_mid": mid,
        "bb_lower": lower,
        "pct_b": (
            (last - lower) / (upper - lower)
            if upper is not None and lower is not None and upper != lower
            else None
        ),
        "returns": {
            str(n): (last / closes[-n - 1] - 1) * 100
            for n in (1, 4, 24, 168)
            if len(closes) > n and closes[-n - 1]
        },
        "bars": [[int(c[0]), *[float(v) for v in c[1:6]]] for c in candles[-24:]],
    }
    return result
