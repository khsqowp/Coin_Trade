"""Compact deterministic feature payloads with candle provenance."""
import hashlib
import json
import numpy as np
import pandas as pd
from bisect import bisect_left, bisect_right, insort
from . import indicators as ind


def _number(value):
    """Convert finite scalar to JSON-safe float, otherwise null."""
    return float(value) if value is not None and np.isfinite(value) else None


def _digest(frame):
    """Hash a stable CSV encoding of every included candle field."""
    columns = [c for c in ("t_open_ms", "o", "h", "l", "c", "v", "quote_v", "trades") if c in frame]
    content = frame[columns].to_csv(index=False, float_format="%.12g", lineterminator="\n")
    return hashlib.sha256(content.encode()).hexdigest()


class FeatureStream:
    """Precompute causal series once and expose exact build_features snapshots."""
    def __init__(self, frame):
        self.frame = frame.reset_index(drop=True)
        self.arrays = {k: self.frame[k].to_numpy(float) for k in ("o", "h", "l", "c", "v")}
        self.series = _stream_series(self.arrays, self.frame.t_open_ms.to_numpy())
        self.profile = np.zeros(24, dtype=float)
        self.profile_edges = None
        self.profile_min = self.profile_max = None
        self.profile_index = -1
        self.levels = {"support_resistance": [], "trendlines": {"resistance": [], "support": [], "channel_candidates": []}, "fibonacci": {}}
        self.level_index = -1
        self.sorted_pivots, self.zone_groups = [], []
        self.zone_lows, self.zone_highs = [], []
        self.zone_ends = []
        self.high_points, self.low_points, self.pivot_sequence = [], [], []

    def payload(self, index, timeframe, digest):
        """Build a schema-compatible snapshot using only data through index."""
        self._update_profile(index)
        self._update_levels(index)
        return _stream_payload(self, index, timeframe, digest)

    def _update_profile(self, index):
        """Keep an exact 24-bin prefix histogram, rebuilding only on a new extreme."""
        c, v = self.arrays["c"], self.arrays["v"]
        for pos in range(self.profile_index + 1, index + 1):
            price = c[pos]
            if self.profile_edges is None or price < self.profile_min or price > self.profile_max:
                self.profile, self.profile_edges = np.histogram(c[:pos + 1], bins=24, weights=v[:pos + 1])
                self.profile_min, self.profile_max = float(c[:pos + 1].min()), float(c[:pos + 1].max())
            else:
                width = self.profile_edges[-1] - self.profile_edges[0]
                bucket = min(23, max(0, int((price - self.profile_edges[0]) / width * 24))) if width else 0
                self.profile[bucket] += v[pos]
            self.profile_index = pos

    def _update_levels(self, index):
        """Refresh swing-derived levels only when a new confirmed pivot arrives."""
        if index <= self.level_index:
            return
        structure = self.series["structure"]
        lo = self.level_index + 1
        events = []
        for kind in ("high", "low"):
            key = "swing_" + kind
            events.extend((pos, kind, float(structure[key][pos])) for pos in range(lo, index + 1)
                          if np.isfinite(structure[key][pos]))
        if events:
            for pos, kind, price in sorted(events):
                self._add_pivot(pos, kind, price)
            self.levels = _level_snapshot(self.zone_groups, self.high_points, self.low_points, self.pivot_sequence)
            self.zone_lows = [z["low"] for z in self.zone_groups]
            self.zone_highs = [z["high"] for z in self.zone_groups]
        self.level_index = index

    def nearest_levels(self, price):
        """Return nearest support and resistance zone distances in price units."""
        below = bisect_right(self.zone_highs, price) - 1
        above = bisect_left(self.zone_lows, price)
        return (price - self.zone_highs[below] if below >= 0 else 0.0,
                self.zone_lows[above] - price if above < len(self.zone_lows) else 0.0)

    def _add_pivot(self, pos, kind, price):
        """Insert one confirmed swing into ordered clusters and recent swing caches."""
        insertion = bisect_left(self.sorted_pivots, price)
        insort(self.sorted_pivots, price)
        group_at = bisect_left(self.zone_highs, price)
        start = max(0, group_at - 1)
        old_offset = self.zone_ends[start - 1] if start else 0
        suffix = self.sorted_pivots[old_offset:]
        rebuilt = _cluster_prices(suffix, self.zone_groups[start:], insertion - old_offset)
        self.zone_groups = self.zone_groups[:start] + rebuilt
        self.zone_ends = self.zone_ends[:start]
        total = self.zone_ends[-1] if self.zone_ends else 0
        for group in rebuilt:
            total += group["count"]; self.zone_ends.append(total)
        self.zone_lows = [group["low"] for group in self.zone_groups]
        self.zone_highs = [group["high"] for group in self.zone_groups]
        point = (pos, price)
        series = self.high_points if kind == "high" else self.low_points
        series.append(point)
        self.pivot_sequence.append((pos, price, kind))


def _stream_series(a, timestamps):
    """Calculate prefix-invariant indicator, candle, and structure arrays once."""
    c, h, l, o, v = (a[k] for k in ("c", "h", "l", "o", "v"))
    line, signal, hist = ind.macd(c)
    patterns = ind.candle_patterns(o, h, l, c)
    structure = ind.market_structure(h, l)
    structure["swing_high_count"] = np.isfinite(structure["swing_high"]).cumsum()
    structure["swing_low_count"] = np.isfinite(structure["swing_low"]).cumsum()
    mid, upper, lower = ind.bollinger(c)
    return {"atr": ind.atr(h, l, c), "ema12": ind.ema(c, 12), "ema26": ind.ema(c, 26),
        "sma20": ind.sma(c, 20), "macd": line, "macd_signal": signal, "macd_hist": hist,
        "rsi14": ind.rsi(c), "di": ind.adx_di(h, l, c), "mid": mid, "upper": upper,
        "lower": lower, "vwap": ind.vwap(h, l, c, v, timestamps), "patterns": patterns,
        "structure": structure}


def _cluster_prices(values, old_groups=(), changed_index=0):
    """Apply the project tolerance rule to an ordered suffix of swing prices."""
    groups = []
    cursor = 0
    while cursor < len(values):
        price = values[cursor]
        group = {"mean": float(price), "count": 1, "low": float(price), "high": float(price)}
        cursor += 1
        while cursor < len(values) and abs(values[cursor] - group["mean"]) / max(abs(values[cursor]), 1e-12) <= .005:
            value = values[cursor]; group["mean"] = (group["mean"] * group["count"] + value) / (group["count"] + 1)
            group["count"] += 1; group["low"] = min(group["low"], value); group["high"] = max(group["high"], value)
            cursor += 1
        groups.append(group)
        old_index = len(groups) - 1
        if cursor > changed_index and old_index < len(old_groups) and _same_cluster(group, old_groups[old_index]):
            return groups + list(old_groups[old_index + 1:])
    return groups


def _same_cluster(left, right):
    """Detect when an incremental recluster has converged to its old suffix."""
    return (left["count"] == right["count"] and left["low"] == right["low"] and
            left["high"] == right["high"] and abs(left["mean"] - right["mean"]) <= 1e-12 * max(1.0, abs(left["mean"])))


def _level_snapshot(groups, high_points, low_points, pivots):
    """Materialize current support/resistance, trendline, and Fibonacci levels."""
    sr = [{"low": z["low"], "high": z["high"], "touches": z["count"]} for z in groups]
    resistance, support = _lines(high_points[-3:]), _lines(low_points[-3:])
    channels = [{"support": support[-1], "resistance": resistance[-1]}] if support and resistance else []
    return {"support_resistance": sr, "trendlines": {"resistance": resistance, "support": support,
            "channel_candidates": channels}, "fibonacci": _fib(pivots)}


def _lines(points):
    """Connect the latest confirmed pivots using the project trendline contract."""
    return [{"start_index": points[0][0], "end_index": point[0], "start_price": points[0][1],
             "end_price": point[1]} for point in points[1:]]


def _fib(pivots):
    """Calculate retracements/extensions for the latest opposite swing pair."""
    if len(pivots) < 2 or pivots[-1][2] == pivots[-2][2]:
        return {}
    a, b = pivots[-2][1], pivots[-1][1]
    move = b - a
    return {str(r): float(b - move * r) for r in (.236, .382, .5, .618, .786)} | {
        "extension_1.272": float(a + move * 1.272), "extension_1.618": float(a + move * 1.618)}


def _stream_payload(stream, index, timeframe, digest):
    """Shape one precomputed prefix snapshot exactly like the standard builder."""
    a, s, frame = stream.arrays, stream.series, stream.frame
    at = lambda key: _number(s[key][index])
    p = float(a["c"][index]); st = s["structure"]
    di = [values[index] for values in s["di"]]
    hist = stream.profile; edges = stream.profile_edges
    vp = _profile(hist, edges)
    patterns = {key: bool(values[index]) for key, values in s["patterns"].items()}
    timestamp = int(frame.t_open_ms.iloc[index]) + {"1m": 60_000, "5m": 300_000, "30m": 1_800_000, "60m": 3_600_000}[timeframe] - 1
    structure = {"label": st["labels"][index], "event": st["events"][index],
        "high": _number(st["swing_high"][index]), "low": _number(st["swing_low"][index])}
    return {"timeframe": timeframe, "anchor_time": pd.to_datetime(timestamp, unit="ms", utc=True).isoformat(),
        "anchor_price": p, "atr14": at("atr"), "indicators": {"ema12": at("ema12"), "ema26": at("ema26"),
        "sma20": at("sma20"), "macd": at("macd"), "macd_signal": at("macd_signal"), "macd_hist": at("macd_hist"),
        "rsi14": at("rsi14"), "adx14": _number(di[2]), "plus_di14": _number(di[0]), "minus_di14": _number(di[1]),
        "bollinger_mid": at("mid"), "bollinger_upper": at("upper"), "bollinger_lower": at("lower"),
        "vwap_utc_day": at("vwap"), "volume_profile": vp}, "patterns": patterns, "structure": structure,
        "levels": {**stream.levels, "swing_counts": {"high": int(st["swing_high_count"][index]),
        "low": int(st["swing_low_count"][index])}}, "input_sha256": digest}


def _profile(hist, edges):
    """Convert prefix volume bins into the shared POC and 70% value area."""
    centers = (edges[:-1] + edges[1:]) / 2
    poc = int(np.argmax(hist)); left = right = poc
    target, accumulated = hist.sum() * .70, hist[poc]
    while accumulated < target and (left > 0 or right < len(hist) - 1):
        take_left = left > 0 and (right == len(hist) - 1 or hist[left - 1] >= hist[right + 1])
        if take_left: left -= 1; accumulated += hist[left]
        else: right += 1; accumulated += hist[right]
    return {"poc": float(centers[poc]), "vah": float(edges[right + 1]), "val": float(edges[left])}


def build_features(candles_df_upto_anchor: pd.DataFrame, timeframe: str, _digest_override=None,
                   _stream=None, _index=None) -> dict:
    """Build latest-value features from rows no later than the supplied anchor."""
    frame = candles_df_upto_anchor if _stream is not None else candles_df_upto_anchor.copy().reset_index(drop=True)
    if frame.empty:
        raise ValueError("at least one candle is required")
    required = {"t_open_ms", "o", "h", "l", "c", "v"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing candle columns: {sorted(missing)}")
    if _stream is not None:
        payload = _stream.payload(_index, timeframe, _digest_override or _digest(frame))
        return payload
    o, h, l, c, v = (frame[k].to_numpy(float) for k in ("o", "h", "l", "c", "v"))
    mline, signal, hist = ind.macd(c)
    pdi, mdi, adx = ind.adx_di(h, l, c)
    mid, upper, lower = ind.bollinger(c)
    structure = ind.market_structure(h, l)
    patterns = ind.candle_patterns(o, h, l, c)
    recent = {key: bool(values[-1]) for key, values in patterns.items()}
    latest_structure = {"label": structure["labels"][-1], "event": structure["events"][-1]}
    last_swing = {"high": _number(structure["swing_high"][-1]), "low": _number(structure["swing_low"][-1])}
    swing_counts = {"high": int(np.isfinite(structure["swing_high"]).sum()),
                    "low": int(np.isfinite(structure["swing_low"]).sum())}
    levels = {"support_resistance": ind.support_resistance(h, l),
              "trendlines": ind.trendline_candidates(h, l), "fibonacci": ind.fibonacci_levels(h, l)}
    width_ms = {"1m": 60_000, "5m": 300_000, "30m": 1_800_000, "60m": 3_600_000}[timeframe]
    timestamp = int(frame.t_open_ms.iloc[-1]) + width_ms - 1
    anchor_time = pd.to_datetime(timestamp, unit="ms", utc=True).isoformat()
    payload = {"timeframe": timeframe, "anchor_time": anchor_time, "anchor_price": float(c[-1]),
        "atr14": _number(ind.atr(h, l, c)[-1]),
        "indicators": {"ema12": _number(ind.ema(c, 12)[-1]), "ema26": _number(ind.ema(c, 26)[-1]),
            "sma20": _number(ind.sma(c, 20)[-1]), "macd": _number(mline[-1]),
            "macd_signal": _number(signal[-1]), "macd_hist": _number(hist[-1]),
            "rsi14": _number(ind.rsi(c)[-1]), "adx14": _number(adx[-1]),
            "plus_di14": _number(pdi[-1]), "minus_di14": _number(mdi[-1]),
            "bollinger_mid": _number(mid[-1]), "bollinger_upper": _number(upper[-1]),
            "bollinger_lower": _number(lower[-1]),
            "vwap_utc_day": _number(ind.vwap(h, l, c, v, frame.t_open_ms)[-1]),
            "volume_profile": ind.volume_profile(h, l, c, v)},
        "patterns": recent, "structure": {**latest_structure, **last_swing}, "levels": {**levels, "swing_counts": swing_counts},
        "input_sha256": _digest_override or _digest(frame)}
    json.dumps(payload, allow_nan=False)
    return payload
