"""Twenty isolated, order-free Binance USD-M futures strategy simulations.

Signals use completed one-minute candles. A signal from candle N is filled on the
first observed trade in candle N+1, avoiding same-bar lookahead. This is an
experimental forward test, not evidence that any strategy is profitable.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional


Signal = Optional[str]
SignalFunction = Callable[[list[dict], Optional[float]], Signal]


@dataclass(frozen=True)
class ExitPolicy:
    stop_atr: float = 1.8
    trailing_atr: Optional[float] = 2.0
    target_mode: str = "none"  # none | mean | vwap | swing | rr
    target_r: float = 2.0
    stop_mode: str = "atr"  # atr | swing
    exit_rule: str = "opposite"
    max_hold_bars: int = 240


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    name: str
    signal: SignalFunction
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_hold_bars: int = 240
    exit_policy: ExitPolicy = ExitPolicy()


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2 / (period + 1)
    value = sum(values[:period]) / period
    for item in values[period:]:
        value = alpha * item + (1 - alpha) * value
    return value


def _sma(values: list[float], period: int) -> float | None:
    return sum(values[-period:]) / period if len(values) >= period else None


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(len(values) - period, len(values))]
    gains = sum(max(x, 0.0) for x in changes) / period
    losses = sum(max(-x, 0.0) for x in changes) / period
    if losses == 0:
        return 100.0
    return 100 - 100 / (1 + gains / losses)


def _atr(bars: list[dict], period: int = 14) -> float | None:
    if len(bars) < period + 1:
        return None
    true_ranges = []
    for previous, current in zip(bars[-period - 1:-1], bars[-period:]):
        true_ranges.append(max(
            current["high"] - current["low"],
            abs(current["high"] - previous["close"]),
            abs(current["low"] - previous["close"]),
        ))
    return sum(true_ranges) / period


def _bollinger(values: list[float], period: int = 20, deviations: float = 2.0) -> tuple[float, float, float] | None:
    if len(values) < period:
        return None
    window = values[-period:]
    middle = sum(window) / period
    variance = sum((value - middle) ** 2 for value in window) / period
    width = deviations * math.sqrt(variance)
    return middle - width, middle, middle + width


def _valid(bars: list[dict], minimum: int) -> bool:
    return len(bars) >= minimum and bars[-1]["close"] > 0


def _signal_impulse(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 21):
        return None
    current, previous = bars[-1], bars[-2]
    avg_volume = _sma([bar["volume"] for bar in bars[:-1]], 20)
    if not avg_volume or current["volume"] < avg_volume * 1.8:
        return None
    change = current["close"] / previous["close"] - 1
    candle_range = max(current["high"] - current["low"], current["close"] * 1e-9)
    close_location = (current["close"] - current["low"]) / candle_range
    if change >= 0.004 and close_location >= 0.75:
        return "long"
    if change <= -0.004 and close_location <= 0.25:
        return "short"
    return None


def _signal_heikin_ashi(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 25):
        return None
    ha_open = (bars[0]["open"] + bars[0]["close"]) / 2
    ha_closes = []
    ha_opens = []
    for bar in bars[-25:]:
        ha_close = (bar["open"] + bar["high"] + bar["low"] + bar["close"]) / 4
        ha_opens.append(ha_open)
        ha_closes.append(ha_close)
        ha_open = (ha_open + ha_close) / 2
    ema20 = _ema([bar["close"] for bar in bars], 20)
    if all(c > o for c, o in zip(ha_closes[-3:], ha_opens[-3:])) and bars[-1]["close"] > ema20:
        return "long"
    if all(c < o for c, o in zip(ha_closes[-3:], ha_opens[-3:])) and bars[-1]["close"] < ema20:
        return "short"
    return None


def _signal_deep_pullback(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 25):
        return None
    closes = [bar["close"] for bar in bars]
    volumes = [bar["volume"] for bar in bars[:-1]]
    avg_volume = _sma(volumes, 20)
    ema20, ema9 = _ema(closes, 20), _ema(closes, 9)
    current, previous = bars[-1], bars[-2]
    if not avg_volume or not ema20 or not ema9 or current["volume"] < avg_volume * 2:
        return None
    prior = bars[-6:-1]
    prior_uptrend = prior[0]["close"] > bars[-16]["close"]
    prior_downtrend = prior[0]["close"] < bars[-16]["close"]
    red_count = sum(bar["close"] < bar["open"] for bar in prior[-4:])
    green_count = sum(bar["close"] > bar["open"] for bar in prior[-4:])
    if prior_uptrend and red_count >= 2 and current["close"] > current["open"] and current["close"] > max(ema9, previous["high"]):
        return "long"
    if prior_downtrend and green_count >= 2 and current["close"] < current["open"] and current["close"] < min(ema9, previous["low"]):
        return "short"
    return None


def _ema_cross(bars: list[dict], funding: float | None) -> Signal:
    closes = [bar["close"] for bar in bars]
    if not _valid(bars, 22):
        return None
    prev_fast, prev_slow = _ema(closes[:-1], 9), _ema(closes[:-1], 21)
    fast, slow = _ema(closes, 9), _ema(closes, 21)
    if prev_fast <= prev_slow and fast > slow:
        return "long"
    if prev_fast >= prev_slow and fast < slow:
        return "short"
    return None


def _ema_trend_pullback(bars: list[dict], funding: float | None) -> Signal:
    closes = [bar["close"] for bar in bars]
    if not _valid(bars, 51):
        return None
    fast, slow = _ema(closes, 20), _ema(closes, 50)
    prev_fast = _ema(closes[:-1], 20)
    if prev_fast is None or fast is None or slow is None:
        return None
    if fast > slow and bars[-2]["close"] <= prev_fast and closes[-1] > fast:
        return "long"
    if fast < slow and bars[-2]["close"] >= prev_fast and closes[-1] < fast:
        return "short"
    return None


def _macd_cross(bars: list[dict], funding: float | None) -> Signal:
    closes = [bar["close"] for bar in bars]
    if not _valid(bars, 35):
        return None
    def line(values: list[float]) -> float | None:
        fast, slow = _ema(values, 12), _ema(values, 26)
        return fast - slow if fast is not None and slow is not None else None
    hist = [line(closes[:i]) for i in range(26, len(closes) + 1)]
    hist = [value for value in hist if value is not None]
    if len(hist) < 10:
        return None
    signal_line = _ema(hist, 9)
    previous_signal = _ema(hist[:-1], 9)
    if signal_line is None or previous_signal is None:
        return None
    if hist[-2] <= previous_signal and hist[-1] > signal_line:
        return "long"
    if hist[-2] >= previous_signal and hist[-1] < signal_line:
        return "short"
    return None


def _rsi_reversal(bars: list[dict], funding: float | None) -> Signal:
    closes = [bar["close"] for bar in bars]
    if not _valid(bars, 16):
        return None
    current, previous = _rsi(closes, 14), _rsi(closes[:-1], 14)
    if current is None or previous is None:
        return None
    if previous < 30 <= current:
        return "long"
    if previous > 70 >= current:
        return "short"
    return None


def _bollinger_reentry(bars: list[dict], funding: float | None) -> Signal:
    closes = [bar["close"] for bar in bars]
    if not _valid(bars, 21):
        return None
    prior, current = _bollinger(closes[:-1]), _bollinger(closes)
    if not prior or not current:
        return None
    if closes[-2] < prior[0] and closes[-1] >= current[0]:
        return "long"
    if closes[-2] > prior[2] and closes[-1] <= current[2]:
        return "short"
    return None


def _donchian_breakout(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 21):
        return None
    prior = bars[-21:-1]
    if bars[-1]["close"] > max(bar["high"] for bar in prior):
        return "long"
    if bars[-1]["close"] < min(bar["low"] for bar in prior):
        return "short"
    return None


def _vwap_reclaim(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 21):
        return None
    window = bars[-60:]
    volume = sum(bar["volume"] for bar in window)
    if volume <= 0:
        return None
    vwap = sum(((bar["high"] + bar["low"] + bar["close"]) / 3) * bar["volume"] for bar in window) / volume
    prev_window = bars[-61:-1]
    prev_volume = sum(bar["volume"] for bar in prev_window)
    if prev_volume <= 0:
        return None
    prev_vwap = sum(((bar["high"] + bar["low"] + bar["close"]) / 3) * bar["volume"] for bar in prev_window) / prev_volume
    if bars[-2]["close"] <= prev_vwap and bars[-1]["close"] > vwap:
        return "long"
    if bars[-2]["close"] >= prev_vwap and bars[-1]["close"] < vwap:
        return "short"
    return None


def _supertrend_proxy(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 16):
        return None
    atr = _atr(bars)
    if not atr:
        return None
    midpoint = (bars[-1]["high"] + bars[-1]["low"]) / 2
    prior_mid = (bars[-2]["high"] + bars[-2]["low"]) / 2
    if bars[-2]["close"] <= prior_mid - atr * 2 and bars[-1]["close"] > midpoint - atr * 2:
        return "long"
    if bars[-2]["close"] >= prior_mid + atr * 2 and bars[-1]["close"] < midpoint + atr * 2:
        return "short"
    return None


def _keltner_breakout(bars: list[dict], funding: float | None) -> Signal:
    closes = [bar["close"] for bar in bars]
    if not _valid(bars, 21):
        return None
    ema20, atr = _ema(closes, 20), _atr(bars)
    if not ema20 or not atr:
        return None
    if closes[-1] > ema20 + 1.5 * atr:
        return "long"
    if closes[-1] < ema20 - 1.5 * atr:
        return "short"
    return None


def _squeeze_release(bars: list[dict], funding: float | None) -> Signal:
    closes = [bar["close"] for bar in bars]
    if not _valid(bars, 30):
        return None
    prior = _bollinger(closes[:-1])
    current = _bollinger(closes)
    atr = _atr(bars)
    if not prior or not current or not atr:
        return None
    prior_width = (prior[2] - prior[0]) / prior[1]
    if prior_width < 0.012 and closes[-1] > current[2] and bars[-1]["close"] > bars[-1]["open"]:
        return "long"
    if prior_width < 0.012 and closes[-1] < current[0] and bars[-1]["close"] < bars[-1]["open"]:
        return "short"
    return None


def _stochastic_cross(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 17):
        return None
    def k(window: list[dict]) -> float:
        high = max(bar["high"] for bar in window[-14:])
        low = min(bar["low"] for bar in window[-14:])
        return 50.0 if high == low else 100 * (window[-1]["close"] - low) / (high - low)
    current, previous = k(bars), k(bars[:-1])
    if previous < 20 <= current:
        return "long"
    if previous > 80 >= current:
        return "short"
    return None


def _obv_confirm(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 22):
        return None
    obv = [0.0]
    for previous, current in zip(bars, bars[1:]):
        direction = 1 if current["close"] > previous["close"] else -1 if current["close"] < previous["close"] else 0
        obv.append(obv[-1] + direction * current["volume"])
    price_ema = _ema([bar["close"] for bar in bars], 20)
    if not price_ema:
        return None
    obv_delta = obv[-1] - obv[-11]
    if bars[-1]["close"] > price_ema and obv_delta > 0:
        return "long"
    if bars[-1]["close"] < price_ema and obv_delta < 0:
        return "short"
    return None


def _taker_imbalance(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 21):
        return None
    current = bars[-1]
    total = current["buy_volume"] + current["sell_volume"]
    if total <= 0:
        return None
    buy_ratio = current["buy_volume"] / total
    prior = bars[-21:-1]
    if current["volume"] < (_sma([bar["volume"] for bar in prior], 20) or math.inf) * 1.5:
        return None
    if buy_ratio >= 0.65 and current["close"] > max(bar["high"] for bar in prior[-5:]):
        return "long"
    if buy_ratio <= 0.35 and current["close"] < min(bar["low"] for bar in prior[-5:]):
        return "short"
    return None


def _funding_extreme(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 21) or funding is None:
        return None
    ema20 = _ema([bar["close"] for bar in bars], 20)
    if funding <= -0.0003 and bars[-1]["close"] > ema20:
        return "long"
    if funding >= 0.0003 and bars[-1]["close"] < ema20:
        return "short"
    return None


def _funding_trend(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 21) or funding is None:
        return None
    closes = [bar["close"] for bar in bars]
    fast, slow = _ema(closes, 9), _ema(closes, 21)
    if funding < 0 and fast and slow and fast > slow and closes[-1] > closes[-2]:
        return "long"
    if funding > 0 and fast and slow and fast < slow and closes[-1] < closes[-2]:
        return "short"
    return None


def _multi_timeframe(bars: list[dict], funding: float | None) -> Signal:
    closes = [bar["close"] for bar in bars]
    if not _valid(bars, 60):
        return None
    fifteen_minute = [bars[i + 14]["close"] for i in range(0, len(bars) - 14, 15)]
    ema5, ema20 = _ema(closes, 5), _ema(closes, 20)
    slow15 = _ema(fifteen_minute, 3)
    if ema5 and ema20 and slow15 and closes[-1] > slow15 and ema5 > ema20:
        return "long"
    if ema5 and ema20 and slow15 and closes[-1] < slow15 and ema5 < ema20:
        return "short"
    return None


def _atr_expansion(bars: list[dict], funding: float | None) -> Signal:
    if not _valid(bars, 22):
        return None
    atr = _atr(bars)
    if not atr:
        return None
    prior = bars[-11:-1]
    current = bars[-1]
    if current["high"] - current["low"] < atr * 1.5:
        return None
    if current["close"] > max(bar["high"] for bar in prior) and current["close"] > current["open"]:
        return "long"
    if current["close"] < min(bar["low"] for bar in prior) and current["close"] < current["open"]:
        return "short"
    return None


def _vwap(bars: list[dict], period: int = 60) -> Optional[float]:
    window = bars[-period:]
    volume = sum(bar["volume"] for bar in window)
    if volume <= 0:
        return None
    return sum(((bar["high"] + bar["low"] + bar["close"]) / 3) * bar["volume"] for bar in window) / volume


def _swing_level(bars: list[dict], side: str, entry: float) -> Optional[float]:
    window = bars[-60:]
    pivots = []
    for i in range(1, len(window) - 1):
        if side == "long" and window[i]["high"] >= window[i - 1]["high"] and window[i]["high"] >= window[i + 1]["high"]:
            pivots.append(window[i]["high"])
        elif side == "short" and window[i]["low"] <= window[i - 1]["low"] and window[i]["low"] <= window[i + 1]["low"]:
            pivots.append(window[i]["low"])
    beyond = [value for value in pivots if value > entry] if side == "long" else [value for value in pivots if value < entry]
    return min(beyond) if side == "long" and beyond else max(beyond) if beyond else None


def _initial_levels(spec: StrategySpec, bars: list[dict], side: str, entry: float) -> tuple[float, Optional[float]]:
    """Set the strategy's own invalidation stop and structural/mean target."""
    sign = 1 if side == "long" else -1
    if spec.stop_loss_pct is not None:
        stop = entry * (1 - sign * spec.stop_loss_pct)
        target = entry * (1 + sign * spec.take_profit_pct) if spec.take_profit_pct is not None else None
        return stop, target

    policy = spec.exit_policy
    atr = _atr(bars) or entry * 0.005
    max_distance = max(atr * policy.stop_atr, entry * 0.001)
    if policy.stop_mode == "swing" and len(bars) >= 3:
        recent = bars[-10:]
        structural = min(bar["low"] for bar in recent) - 0.15 * atr if side == "long" else max(bar["high"] for bar in recent) + 0.15 * atr
        if side == "long":
            stop = max(structural, entry - max_distance) if structural < entry else entry - max_distance
        else:
            stop = min(structural, entry + max_distance) if structural > entry else entry + max_distance
    else:
        stop = entry - sign * max_distance

    target: Optional[float] = None
    if policy.target_mode == "rr":
        target = entry + sign * abs(entry - stop) * policy.target_r
    elif policy.target_mode == "swing":
        resistance = _swing_level(bars, side, entry)
        minimum = abs(entry - stop) * min(policy.target_r, 1.5)
        if resistance is not None and abs(resistance - entry) >= minimum:
            target = resistance - sign * atr * 0.1
        else:
            target = entry + sign * abs(entry - stop) * policy.target_r
    elif policy.target_mode in {"mean", "vwap"}:
        target = _sma([bar["close"] for bar in bars], 20) if policy.target_mode == "mean" else _vwap(bars)
        if target is None or (target - entry) * sign <= 0:
            target = entry + sign * abs(entry - stop) * policy.target_r
    if target is not None and (target - entry) * sign <= 0:
        target = entry + sign * abs(entry - stop) * policy.target_r
    return stop, target


def _exit_rule(rule: str, bars: list[dict], position: dict, funding: Optional[float]) -> Optional[str]:
    side = position["side"]
    sign = 1 if side == "long" else -1
    closes = [bar["close"] for bar in bars]
    current = closes[-1]
    if rule == "none":
        return None
    if rule == "opposite":
        return "signal_invalidation" if (side == "long" and current < closes[-2]) or (side == "short" and current > closes[-2]) else None
    if rule == "ha_flip":
        opens, ha_closes = [], []
        ha_open = (bars[0]["open"] + bars[0]["close"]) / 2
        for bar in bars[-4:]:
            ha_close = (bar["open"] + bar["high"] + bar["low"] + bar["close"]) / 4
            opens.append(ha_open)
            ha_closes.append(ha_close)
            ha_open = (ha_open + ha_close) / 2
        opposite = [c < o for c, o in zip(ha_closes[-2:], opens[-2:])] if side == "long" else [c > o for c, o in zip(ha_closes[-2:], opens[-2:])]
        return "heikin_ashi_reversal" if all(opposite) else None
    if rule == "ema_cross":
        signal = _ema_cross(bars, funding)
        return "ema_cross_reversal" if signal and signal != side else None
    if rule == "ema20":
        average = _ema(closes, 20)
        return "ema20_lost" if average and (current < average if side == "long" else current > average) else None
    if rule == "macd":
        signal = _macd_cross(bars, funding)
        return "macd_reversal" if signal and signal != side else None
    if rule == "rsi_mid":
        value = _rsi(closes)
        return "rsi_mean_reached" if value is not None and (value >= 50 if side == "long" else value <= 50) else None
    if rule == "bb_mid":
        bands = _bollinger(closes)
        return "bollinger_midline_reached" if bands and (current >= bands[1] if side == "long" else current <= bands[1]) else None
    if rule == "donchian10":
        prior = bars[-11:-1]
        return "donchian_trail_broken" if prior and (current < min(b["low"] for b in prior) if side == "long" else current > max(b["high"] for b in prior)) else None
    if rule == "vwap":
        average = _vwap(bars)
        return "vwap_lost" if average and (current < average if side == "long" else current > average) else None
    if rule == "keltner_mid":
        average = _ema(closes, 20)
        return "keltner_midline_lost" if average and (current < average if side == "long" else current > average) else None
    if rule == "stoch_mid":
        value = _stochastic_value(bars)
        return "stochastic_momentum_faded" if value is not None and (value < 50 if side == "long" else value > 50) else None
    if rule == "obv_flip":
        direction = _obv_direction(bars)
        return "obv_flow_reversed" if direction and direction != side else None
    if rule == "taker_flip":
        total = bars[-1]["buy_volume"] + bars[-1]["sell_volume"]
        if total:
            buy_ratio = bars[-1]["buy_volume"] / total
            if (side == "long" and buy_ratio < 0.4) or (side == "short" and buy_ratio > 0.6):
                return "taker_flow_reversed"
    if rule == "funding_normalized":
        if funding is not None and (abs(funding) < 0.0001 or (funding > 0 if side == "long" else funding < 0)):
            return "funding_extreme_normalized"
    if rule == "funding_flip":
        if funding is not None and (funding > 0 if side == "long" else funding < 0):
            return "funding_direction_flipped"
    if rule == "mtf_flip":
        signal = _multi_timeframe(bars, funding)
        return "higher_timeframe_trend_lost" if signal and signal != side else None
    if rule == "atr_channel":
        prior = bars[-11:-1]
        return "range_breakout_failed" if prior and (current < min(b["low"] for b in prior) if side == "long" else current > max(b["high"] for b in prior)) else None
    if rule == "supertrend":
        signal = _supertrend_proxy(bars, funding)
        return "atr_trend_reversed" if signal and signal != side else None
    if rule == "squeeze_mid":
        middle = _bollinger(closes)
        return "squeeze_breakout_failed" if middle and (current < middle[1] if side == "long" else current > middle[1]) else None
    if rule == "pullback_structure":
        average = _ema(closes, 20)
        return "pullback_support_resistance_broken" if average and (current < average if side == "long" else current > average) else None
    return None


def _stochastic_value(bars: list[dict]) -> Optional[float]:
    if len(bars) < 14:
        return None
    window = bars[-14:]
    high = max(bar["high"] for bar in window)
    low = min(bar["low"] for bar in window)
    return 50.0 if high == low else 100 * (window[-1]["close"] - low) / (high - low)


def _obv_direction(bars: list[dict]) -> Optional[str]:
    if len(bars) < 11:
        return None
    total = 0.0
    for previous, current in zip(bars[-11:-1], bars[-10:]):
        total += (1 if current["close"] > previous["close"] else -1 if current["close"] < previous["close"] else 0) * current["volume"]
    return "long" if total > 0 else "short" if total < 0 else None


STRATEGIES: tuple[StrategySpec, ...] = (
    StrategySpec("volume_impulse_3_5", "고거래량 급등락 돌파 (손절 3%·익절 5%)", _signal_impulse, 0.03, 0.05, exit_policy=ExitPolicy(trailing_atr=None, exit_rule="none")),
    StrategySpec("heikin_ashi_trend", "하이킨아시 3봉 추세", _signal_heikin_ashi, exit_policy=ExitPolicy(2.0, 2.0, "none", 2.0, "atr", "ha_flip")),
    StrategySpec("deep_pullback_volume_burst", "추세 눌림목 후 거래량 폭발", _signal_deep_pullback, exit_policy=ExitPolicy(1.8, 1.4, "swing", 1.8, "swing", "pullback_structure")),
    StrategySpec("ema_9_21_cross", "EMA 9/21 교차", _ema_cross, exit_policy=ExitPolicy(1.5, 2.0, "none", 2.0, "atr", "ema_cross")),
    StrategySpec("ema_20_50_pullback", "EMA 20/50 추세 눌림", _ema_trend_pullback, exit_policy=ExitPolicy(1.7, 2.0, "swing", 1.8, "swing", "ema20")),
    StrategySpec("macd_12_26_9", "MACD 12/26/9 교차", _macd_cross, exit_policy=ExitPolicy(1.8, 2.2, "none", 2.0, "atr", "macd")),
    StrategySpec("rsi_oversold_reversal", "RSI 과매수·과매도 반전", _rsi_reversal,  max_hold_bars=60, exit_policy=ExitPolicy(1.3, None, "mean", 1.5, "swing", "rsi_mid", 60)),
    StrategySpec("bollinger_reentry", "볼린저밴드 이탈 후 복귀", _bollinger_reentry, max_hold_bars=60, exit_policy=ExitPolicy(1.3, None, "mean", 1.5, "swing", "bb_mid", 60)),
    StrategySpec("donchian_20_breakout", "돈치안 20봉 돌파", _donchian_breakout, exit_policy=ExitPolicy(2.0, 2.5, "none", 2.0, "atr", "donchian10")),
    StrategySpec("rolling_vwap_reclaim", "60분 롤링 VWAP 회복·이탈", _vwap_reclaim, max_hold_bars=120, exit_policy=ExitPolicy(1.4, None, "vwap", 1.5, "swing", "vwap", 120)),
    StrategySpec("supertrend_atr_proxy", "ATR 추세 밴드 반전", _supertrend_proxy, exit_policy=ExitPolicy(2.0, 2.0, "none", 2.0, "atr", "supertrend")),
    StrategySpec("keltner_15_atr", "켈트너 채널 1.5 ATR 돌파", _keltner_breakout, exit_policy=ExitPolicy(1.7, 1.8, "swing", 2.0, "atr", "keltner_mid")),
    StrategySpec("bollinger_squeeze_release", "볼린저 스퀴즈 확장", _squeeze_release, exit_policy=ExitPolicy(1.5, 2.2, "none", 2.0, "atr", "squeeze_mid")),
    StrategySpec("stochastic_14_reversal", "스토캐스틱 14 반전", _stochastic_cross, max_hold_bars=60, exit_policy=ExitPolicy(1.3, None, "mean", 1.5, "swing", "stoch_mid", 60)),
    StrategySpec("obv_trend_confirm", "OBV 거래량 추세 확인", _obv_confirm, exit_policy=ExitPolicy(1.8, 2.0, "none", 2.0, "atr", "obv_flip")),
    StrategySpec("taker_imbalance_breakout", "공격 매수·매도 불균형 돌파", _taker_imbalance, exit_policy=ExitPolicy(1.2, 1.5, "rr", 2.0, "swing", "taker_flip")),
    StrategySpec("funding_extreme_reversal", "극단 펀딩비 역추세", _funding_extreme, max_hold_bars=240, exit_policy=ExitPolicy(1.5, 1.8, "swing", 1.8, "swing", "funding_normalized", 240)),
    StrategySpec("funding_aligned_momentum", "펀딩비 방향성 모멘텀", _funding_trend, exit_policy=ExitPolicy(1.5, 2.0, "none", 2.0, "atr", "funding_flip")),
    StrategySpec("multi_timeframe_1m_15m", "1분·15분 다중시간대 추세", _multi_timeframe, exit_policy=ExitPolicy(2.0, 2.5, "none", 2.0, "atr", "mtf_flip")),
    StrategySpec("atr_range_expansion", "ATR 변동성 확장 돌파", _atr_expansion, exit_policy=ExitPolicy(1.5, 2.0, "rr", 2.0, "atr", "atr_channel")),
)


class PaperStrategyEngine:
    """Isolated virtual ledgers consuming one shared public futures trade stream."""

    def __init__(
        self,
        state_path: str | Path | None = None,
        *,
        strategies: Iterable[StrategySpec] = STRATEGIES,
        symbols: Iterable[str] = ("BTC", "ETH"),
        starting_equity: float = 142.0,
        fee_rate: float = 0.0005,
        slippage_rate: float = 0.0002,
        allocation_fraction: float = 0.95,
    ) -> None:
        self.state_path = Path(state_path or os.environ.get("CRYPTO_PAPER_STATE_PATH", "/app/data/crypto_paper_strategies.json"))
        self.strategies = tuple(strategies)
        self.symbols = tuple(sorted(set(symbols)))
        self.starting_equity = float(starting_equity)
        self.fee_rate = float(fee_rate)
        self.slippage_rate = float(slippage_rate)
        self.allocation_fraction = float(allocation_fraction)
        self.bars: dict[str, list[dict]] = {symbol: [] for symbol in self.symbols}
        self.current: dict[str, dict] = {}
        self.last_prices: dict[str, float] = {}
        self.funding: dict[str, dict] = {}
        self.portfolios = {spec.strategy_id: self._empty_portfolio() for spec in self.strategies}
        self.spec_by_id = {spec.strategy_id: spec for spec in self.strategies}
        if len(self.spec_by_id) != len(self.strategies):
            raise ValueError("strategy ids must be unique")
        self._load()
        if not self.state_path.exists():
            self._persist()

    def _empty_portfolio(self) -> dict:
        return {
            "starting_equity": self.starting_equity,
            "equity": self.starting_equity,
            "realized_pnl": 0.0,
            "fees_paid": 0.0,
            "funding_pnl": 0.0,
            "trades": 0,
            "wins": 0,
            "positions": {},
            "recent_trades": [],
            "last_exit_bar_count": {},
        }

    def _load(self) -> None:
        try:
            state = json.loads(self.state_path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        for symbol in self.symbols:
            self.bars[symbol] = state.get("bars", {}).get(symbol, [])[-300:]
            current = state.get("current", {}).get(symbol)
            if current:
                self.current[symbol] = current
            price = state.get("last_prices", {}).get(symbol)
            if price:
                self.last_prices[symbol] = float(price)
            funding = state.get("funding", {}).get(symbol)
            if funding:
                self.funding[symbol] = funding
        for strategy_id in self.portfolios:
            saved = state.get("portfolios", {}).get(strategy_id)
            if saved:
                self.portfolios[strategy_id].update(saved)

    def on_funding(self, symbol: str, exchange_event_ts: int, next_funding_ts: int, rate: float) -> None:
        if symbol not in self.symbols:
            return
        previous = self.funding.get(symbol)
        settled = False
        if previous and int(exchange_event_ts) >= int(previous["next_funding_ts"]):
            settlement_ts = int(previous["next_funding_ts"])
            for strategy_id, portfolio in self.portfolios.items():
                position = portfolio["positions"].get(symbol)
                if not position or position["entry_ts"] >= settlement_ts or position.get("last_funding_ts") == settlement_ts:
                    continue
                side_sign = 1 if position["side"] == "long" else -1
                amount = -side_sign * position["notional"] * float(previous["rate"])
                portfolio["equity"] += amount
                portfolio["realized_pnl"] += amount
                portfolio["funding_pnl"] += amount
                position["last_funding_ts"] = settlement_ts
                settled = True
        self.funding[symbol] = {"rate": float(rate), "next_funding_ts": int(next_funding_ts)}
        if settled:
            self._persist()

    def on_trade(self, symbol: str, timestamp_ms: int, price: float, quantity: float, buyer_is_maker: bool) -> None:
        if symbol not in self.bars or price <= 0 or quantity <= 0:
            return
        minute = int(timestamp_ms) // 60_000
        self.last_prices[symbol] = float(price)
        bar = self.current.get(symbol)
        if bar is not None and minute < bar["minute"]:
            return
        if bar is None:
            self.current[symbol] = self._new_bar(minute, price, quantity, buyer_is_maker)
            return
        if minute == bar["minute"]:
            bar["high"] = max(bar["high"], price)
            bar["low"] = min(bar["low"], price)
            bar["close"] = float(price)
            bar["volume"] += float(quantity)
            volume_key = "sell_volume" if buyer_is_maker else "buy_volume"
            bar[volume_key] += float(quantity)
            if self._manage_open_positions(symbol, int(timestamp_ms), float(price)):
                self._persist()
            return

        closed = bar
        self.bars[symbol].append(closed)
        self.bars[symbol] = self.bars[symbol][-300:]
        self.current[symbol] = self._new_bar(minute, price, quantity, buyer_is_maker)
        self._manage_closed_bar(symbol, int(timestamp_ms), float(price))
        self._manage_open_positions(symbol, int(timestamp_ms), float(price))
        for strategy in self.strategies:
            signal = strategy.signal(self.bars[symbol], self.funding.get(symbol, {}).get("rate"))
            if signal not in {"long", "short"}:
                continue
            portfolio = self.portfolios[strategy.strategy_id]
            if portfolio.get("last_exit_bar_count", {}).get(symbol) == len(self.bars[symbol]):
                continue
            existing = portfolio["positions"].get(symbol)
            if existing and existing["side"] == signal:
                continue
            if existing:
                self._close(strategy, portfolio, symbol, int(timestamp_ms), float(price), "opposite_signal")
            self._open(strategy, portfolio, symbol, int(timestamp_ms), float(price), signal)
        self._persist()

    @staticmethod
    def _new_bar(minute: int, price: float, quantity: float, buyer_is_maker: bool) -> dict:
        return {
            "minute": int(minute), "open": float(price), "high": float(price), "low": float(price),
            "close": float(price), "volume": float(quantity),
            "buy_volume": 0.0 if buyer_is_maker else float(quantity),
            "sell_volume": float(quantity) if buyer_is_maker else 0.0,
        }

    def _open(self, strategy: StrategySpec, portfolio: dict, symbol: str, ts: int, price: float, side: str) -> None:
        if portfolio["equity"] <= 0:
            return
        side_sign = 1 if side == "long" else -1
        entry = price * (1 + side_sign * self.slippage_rate)
        notional = portfolio["equity"] * self.allocation_fraction / max(len(self.symbols), 1)
        fee = notional * self.fee_rate
        stop_price, target_price = _initial_levels(strategy, self.bars[symbol], side, entry)
        portfolio["equity"] -= fee
        portfolio["realized_pnl"] -= fee
        portfolio["fees_paid"] += fee
        portfolio["positions"][symbol] = {
            "side": side, "entry_price": entry, "entry_ts": ts, "entry_bar_count": len(self.bars[symbol]),
            "notional": notional, "stop_loss_pct": strategy.stop_loss_pct,
            "take_profit_pct": strategy.take_profit_pct, "stop_price": stop_price,
            "target_price": target_price, "max_hold_bars": strategy.max_hold_bars,
            "entry_fee": fee,
        }

    def _manage_closed_bar(self, symbol: str, ts: int, price: float) -> None:
        bars = self.bars[symbol]
        funding = self.funding.get(symbol, {}).get("rate")
        for strategy in self.strategies:
            portfolio = self.portfolios[strategy.strategy_id]
            position = portfolio["positions"].get(symbol)
            if not position:
                continue
            policy = strategy.exit_policy
            if strategy.stop_loss_pct is None and policy.trailing_atr is not None:
                atr = _atr(bars)
                if atr:
                    sign = 1 if position["side"] == "long" else -1
                    candidate = bars[-1]["close"] - sign * atr * policy.trailing_atr
                    if position["side"] == "long":
                        position["stop_price"] = max(position["stop_price"], candidate)
                    else:
                        position["stop_price"] = min(position["stop_price"], candidate)
            reason = _exit_rule(policy.exit_rule, bars, position, funding)
            if reason:
                self._close(strategy, portfolio, symbol, ts, price, reason)

    def _manage_open_positions(self, symbol: str, ts: int, price: float) -> bool:
        closed = False
        for strategy in self.strategies:
            portfolio = self.portfolios[strategy.strategy_id]
            position = portfolio["positions"].get(symbol)
            if not position:
                continue
            stop = position.get("stop_price")
            target = position.get("target_price")
            if stop is not None and (price <= stop if position["side"] == "long" else price >= stop):
                self._close(strategy, portfolio, symbol, ts, price, "invalidation_stop")
                closed = True
            elif target is not None and (price >= target if position["side"] == "long" else price <= target):
                self._close(strategy, portfolio, symbol, ts, price, "structural_or_mean_target")
                closed = True
            position = portfolio["positions"].get(symbol)
            if position and len(self.bars[symbol]) - position["entry_bar_count"] >= position["max_hold_bars"]:
                self._close(strategy, portfolio, symbol, ts, price, "time_exit")
                closed = True
        return closed

    def _close(self, strategy: StrategySpec, portfolio: dict, symbol: str, ts: int, price: float, reason: str) -> None:
        position = portfolio["positions"].pop(symbol, None)
        if not position:
            return
        side_sign = 1 if position["side"] == "long" else -1
        exit_price = price * (1 - side_sign * self.slippage_rate)
        gross = position["notional"] * side_sign * (exit_price / position["entry_price"] - 1)
        exit_fee = position["notional"] * self.fee_rate
        net_trade_pnl = gross - exit_fee - position.get("entry_fee", 0.0)
        equity_change = gross - exit_fee
        portfolio["equity"] += equity_change
        portfolio["realized_pnl"] += equity_change
        portfolio["fees_paid"] += exit_fee
        portfolio["trades"] += 1
        if net_trade_pnl > 0:
            portfolio["wins"] += 1
        portfolio.setdefault("last_exit_bar_count", {})[symbol] = len(self.bars[symbol])
        trade = {
            "strategy_id": strategy.strategy_id, "symbol": symbol, "side": position["side"],
            "entry_ts": position["entry_ts"], "exit_ts": ts,
            "entry_price": position["entry_price"], "exit_price": exit_price,
            "gross_pnl": gross, "net_pnl": net_trade_pnl,
            "exit_reason": reason, "fees_round_trip": position["notional"] * self.fee_rate * 2,
        }
        portfolio["recent_trades"].append(trade)
        portfolio["recent_trades"] = portfolio["recent_trades"][-500:]

    def summary(self) -> dict:
        result = {}
        for strategy in self.strategies:
            portfolio = self.portfolios[strategy.strategy_id]
            unrealized = 0.0
            for symbol, position in portfolio["positions"].items():
                price = self.last_prices.get(symbol)
                if price:
                    side_sign = 1 if position["side"] == "long" else -1
                    unrealized += position["notional"] * side_sign * (price / position["entry_price"] - 1)
            result[strategy.strategy_id] = {
                "name": strategy.name,
                "equity": portfolio["equity"],
                "realized_pnl": portfolio["realized_pnl"],
                "unrealized_pnl": unrealized,
                "total_pnl": portfolio["realized_pnl"] + unrealized,
                "fees_paid": portfolio["fees_paid"],
                "funding_pnl": portfolio["funding_pnl"],
                "trades": portfolio["trades"],
                "wins": portfolio["wins"],
                "win_rate_pct": 100 * portfolio["wins"] / portfolio["trades"] if portfolio["trades"] else None,
                "open_positions": portfolio["positions"],
            }
        return result

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "symbols": list(self.symbols),
            "assumptions": {
                "starting_equity_per_strategy_usdt": self.starting_equity,
                "allocation_fraction": self.allocation_fraction,
                "leverage": 1,
                "fee_per_side": self.fee_rate,
                "slippage_per_side": self.slippage_rate,
                "signal_timeframe": "1m",
                "execution": "next observed trade after candle close",
                "strategy_exit_policies": {
                    spec.strategy_id: {
                        "fixed_stop_pct": spec.stop_loss_pct,
                        "fixed_take_profit_pct": spec.take_profit_pct,
                        "policy": asdict(spec.exit_policy),
                        "max_hold_bars": spec.max_hold_bars,
                    }
                    for spec in self.strategies
                },
            },
            "bars": self.bars,
            "current": self.current,
            "last_prices": self.last_prices,
            "funding": self.funding,
            "portfolios": self.portfolios,
            "summary": self.summary(),
        }
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")))
        os.replace(temp, self.state_path)
