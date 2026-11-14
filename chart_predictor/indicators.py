"""Causal, numpy/pandas technical indicators; no external TA library."""
import numpy as np
import pandas as pd


def sma(values, period):
    """SMA: trailing arithmetic mean, requiring a complete window."""
    return pd.Series(values, dtype=float).rolling(period, min_periods=period).mean().to_numpy()


def ema(values, period):
    """EMA: recursive alpha=2/(period+1), initialized by first observation."""
    return pd.Series(values, dtype=float).ewm(span=period, adjust=False, min_periods=1).mean().to_numpy()


def macd(values, fast=12, slow=26, signal=9):
    """MACD is fast EMA minus slow EMA; signal is EMA of MACD."""
    line = ema(values, fast) - ema(values, slow)
    return line, ema(line, signal), line - ema(line, signal)


def rsi(values, period=14):
    """Wilder RSI using exponentially smoothed positive and negative deltas."""
    delta = pd.Series(values, dtype=float).diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    ratio = gain / loss.replace(0, np.nan)
    result = 100 - 100 / (1 + ratio)
    result = result.where(loss.ne(0), 100.0).where(gain.ne(0) | loss.ne(0), 50.0)
    return result.to_numpy()


def true_range(high, low, close):
    """True range is max(high-low, abs(high-prev close), abs(low-prev close))."""
    h, l, c = map(lambda x: np.asarray(x, dtype=float), (high, low, close))
    prev = np.r_[np.nan, c[:-1]]
    return np.nanmax(np.vstack((h - l, abs(h - prev), abs(l - prev))), axis=0)


def atr(high, low, close, period=14):
    """ATR is Wilder-smoothed true range."""
    tr = pd.Series(true_range(high, low, close))
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean().to_numpy()


def adx_di(high, low, close, period=14):
    """Return +DI, -DI, ADX using Wilder-smoothed directional movement."""
    h, l = np.asarray(high, float), np.asarray(low, float)
    up, down = np.diff(h, prepend=np.nan), -np.diff(l, prepend=np.nan)
    plus, minus = np.where((up > down) & (up > 0), up, 0), np.where((down > up) & (down > 0), down, 0)
    tr = pd.Series(true_range(h, l, close))
    smooth = lambda x: pd.Series(x).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    base = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    pdi, mdi = 100 * smooth(plus) / base, 100 * smooth(minus) / base
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return pdi.to_numpy(), mdi.to_numpy(), dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean().to_numpy()


def bollinger(values, period=20, deviations=2):
    """Bollinger bands: SMA +/- deviations times population rolling stdev."""
    series = pd.Series(values, dtype=float)
    mid = series.rolling(period, min_periods=period).mean()
    width = series.rolling(period, min_periods=period).std(ddof=0) * deviations
    return mid.to_numpy(), (mid + width).to_numpy(), (mid - width).to_numpy()


def vwap(high, low, close, volume, timestamps_ms):
    """UTC-day anchored VWAP using typical price times base volume."""
    frame = pd.DataFrame({"p": (np.asarray(high) + np.asarray(low) + np.asarray(close)) / 3,
                          "v": np.asarray(volume), "day": np.asarray(timestamps_ms) // 86_400_000})
    numerator = (frame.p * frame.v).groupby(frame.day).cumsum()
    denominator = frame.v.groupby(frame.day).cumsum().replace(0, np.nan)
    return (numerator / denominator).to_numpy()


def volume_profile(high, low, close, volume, bins=24, value_area=0.70):
    """Return volume-at-close histogram POC and contiguous 70% value area."""
    prices, weights = np.asarray(close, float), np.asarray(volume, float)
    hist, edges = np.histogram(prices, bins=bins, weights=weights)
    centers = (edges[:-1] + edges[1:]) / 2
    poc = int(np.argmax(hist))
    left = right = poc
    target, accumulated = hist.sum() * value_area, hist[poc]
    while accumulated < target and (left > 0 or right < len(hist) - 1):
        take_left = left > 0 and (right == len(hist) - 1 or hist[left - 1] >= hist[right + 1])
        if take_left:
            left -= 1
            accumulated += hist[left]
        else:
            right += 1
            accumulated += hist[right]
    return {"poc": float(centers[poc]), "vah": float(edges[right + 1]), "val": float(edges[left])}


def confirmed_swings(high, low, lag=3):
    """Emit pivot values at confirmation index; anchors are lag bars earlier."""
    h, l = np.asarray(high, float), np.asarray(low, float)
    sh, sl = np.full(len(h), np.nan), np.full(len(l), np.nan)
    for confirm in range(2 * lag, len(h)):
        anchor = confirm - lag
        left, right = anchor - lag, confirm + 1
        if h[anchor] >= np.max(h[left:right]):
            sh[confirm] = h[anchor]
        if l[anchor] <= np.min(l[left:right]):
            sl[confirm] = l[anchor]
    return sh, sl


def market_structure(high, low, lag=3):
    """Return confirmed swing labels and BOS/CHoCH events, causal by construction."""
    sh, sl = confirmed_swings(high, low, lag)
    labels, events, prev_hi, prev_lo, trend = [], [], None, None, 0
    for i in range(len(sh)):
        label, event = None, None
        if np.isfinite(sh[i]):
            label = "HH" if prev_hi is not None and sh[i] > prev_hi else "LH" if prev_hi is not None else "H"
            prev_hi = sh[i]
        if np.isfinite(sl[i]):
            label = "HL" if prev_lo is not None and sl[i] > prev_lo else "LL" if prev_lo is not None else "L"
            prev_lo = sl[i]
        if label in ("HH", "HL"):
            new = 1
        elif label in ("LH", "LL"):
            new = -1
        else:
            new = trend
        if new and trend and new != trend:
            event = "CHoCH"
        elif label in ("HH", "LL"):
            event = "BOS"
        if new:
            trend = new
        labels.append(label)
        events.append(event)
    return {"swing_high": sh, "swing_low": sl, "labels": labels, "events": events}


def candle_patterns(open_, high, low, close):
    """Boolean pattern arrays based only on current and earlier OHLC rows."""
    o, h, l, c = map(lambda x: np.asarray(x, float), (open_, high, low, close))
    body, span = abs(c - o), np.maximum(h - l, 1e-12)
    bull_engulf = np.r_[False, (c[1:] > o[1:]) & (c[:-1] < o[:-1]) & (o[1:] <= c[:-1]) & (c[1:] >= o[:-1])]
    bear_engulf = np.r_[False, (c[1:] < o[1:]) & (c[:-1] > o[:-1]) & (o[1:] >= c[:-1]) & (c[1:] <= o[:-1])]
    lower, upper = np.minimum(o, c) - l, h - np.maximum(o, c)
    hammer = (lower >= 2 * body) & (upper <= body) & (body / span < .4)
    shooting = (upper >= 2 * body) & (lower <= body) & (body / span < .4)
    doji = body / span <= .1
    inside = np.r_[False, (h[1:] < h[:-1]) & (l[1:] > l[:-1])]
    morning = np.zeros(len(c), bool)
    evening = np.zeros(len(c), bool)
    for i in range(2, len(c)):
        small = abs(c[i-1] - o[i-1]) < .35 * max(h[i-1] - l[i-1], 1e-12)
        morning[i] = c[i-2] < o[i-2] and small and c[i] > o[i] and c[i] > (o[i-2] + c[i-2]) / 2
        evening[i] = c[i-2] > o[i-2] and small and c[i] < o[i] and c[i] < (o[i-2] + c[i-2]) / 2
    return {"bull_engulfing": bull_engulf, "bear_engulfing": bear_engulf, "hammer_pin": hammer,
            "shooting_star_pin": shooting, "morning_star": morning, "evening_star": evening,
            "doji": doji, "inside_bar": inside}


def support_resistance(high, low, lag=3, tolerance=0.005):
    """Cluster already-confirmed swing prices into horizontal price zones."""
    sh, sl = confirmed_swings(high, low, lag)
    values = sorted(np.r_[sh[np.isfinite(sh)], sl[np.isfinite(sl)]].tolist())
    zones = []
    for price in values:
        if zones and abs(price - zones[-1]["mean"]) / max(abs(price), 1e-12) <= tolerance:
            zone = zones[-1]
            zone["prices"].append(price)
            zone["mean"] = float(np.mean(zone["prices"]))
        else:
            zones.append({"mean": float(price), "prices": [float(price)]})
    return [{"low": min(z["prices"]), "high": max(z["prices"]), "touches": len(z["prices"])} for z in zones]


def trendline_candidates(high, low, lag=3):
    """Connect the latest three confirmed swing highs and lows as candidate lines."""
    sh, sl = confirmed_swings(high, low, lag)
    result = {}
    for key, values in (("resistance", sh), ("support", sl)):
        points = [(i, float(v)) for i, v in enumerate(values) if np.isfinite(v)][-3:]
        result[key] = [{"start_index": points[0][0], "end_index": p[0], "start_price": points[0][1],
                        "end_price": p[1]} for p in points[1:]]
    result["channel_candidates"] = []
    if result["support"] and result["resistance"]:
        result["channel_candidates"] = [{"support": result["support"][-1], "resistance": result["resistance"][-1]}]
    return result


def fibonacci_levels(high, low, lag=3):
    """Retracements/extensions for the most recent pair of confirmed opposite swings."""
    sh, sl = confirmed_swings(high, low, lag)
    pivots = sorted([(i, float(v), "high") for i, v in enumerate(sh) if np.isfinite(v)] +
                    [(i, float(v), "low") for i, v in enumerate(sl) if np.isfinite(v)])
    if len(pivots) < 2 or pivots[-1][2] == pivots[-2][2]:
        return {}
    (_, a, _), (_, b, _) = pivots[-2:]
    move = b - a
    return {str(r): float(b - move * r) for r in (0.236, 0.382, 0.5, 0.618, 0.786)} | {
        "extension_1.272": float(a + move * 1.272), "extension_1.618": float(a + move * 1.618)}
