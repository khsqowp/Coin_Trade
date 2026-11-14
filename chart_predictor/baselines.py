"""Deterministic baseline predictions sharing the fixed prediction schema."""
import hashlib
import numpy as np
import pandas as pd
from .features import _digest
from .schema import HORIZON

WIDTH = {"1m": 1, "5m": 5, "30m": 30, "60m": 60}


def emit_baseline(name, candles, symbol, timeframe, anchor_time, seed=0, input_sha256=None):
    """Build momentum, seeded-random, or always-flat prediction."""
    if name not in {"momentum", "random", "flat", "always_up", "always_down"}:
        raise ValueError("unknown baseline")
    frame = candles.sort_values("t_open_ms").reset_index(drop=True)
    close = frame.c.to_numpy(float)
    horizon, step = HORIZON[timeframe], WIDTH[timeframe]
    if name == "momentum":
        move = close[-1] - close[max(0, len(close) - (5 * step + 1))]
        direction = "up" if move > 0 else "down" if move < 0 else "flat"
    elif name == "flat":
        direction = "flat"
    elif name in {"always_up", "always_down"}:
        direction = "up" if name == "always_up" else "down"
    else:
        rng = np.random.default_rng(seed)
        direction = str(rng.choice(["up", "down", "flat"]))
    price = float(close[-1])
    atr = float(np.nan_to_num(np.mean(np.abs(np.diff(close[-15:]))), nan=0.0)) or price * .001
    side = "long" if direction == "up" else "short" if direction == "down" else "none"
    return {"symbol": symbol, "timeframe": timeframe, "anchor_time": anchor_time,
        "created_at": pd.Timestamp.now(tz="UTC").isoformat(), "model": f"baseline_{name}",
        "prompt_version": "baseline-v1", "code_sha": "baseline-v1", "input_sha256": input_sha256 or _digest(frame),
        "direction": direction, "confidence": .5, "path": [{"minutes": horizon * n // 4,
        "price": price + (atr * (1 if direction == "up" else -1 if direction == "down" else 0) * n / 4)}
        for n in (1, 2, 3, 4)], "target_low": price - atr, "target_high": price + atr,
        "invalidation": price - atr if side == "long" else price + atr if side == "short" else price,
        "side": side, "leverage_suggestion": 1, "rationale": [f"deterministic {name} baseline"]}


def expected_stats():
    """State expected class baselines and values requiring empirical scores."""
    return {"momentum": {"expected_accuracy": None, "coverage": 1.0,
            "basis": "empirical serial persistence; estimate from scored split"},
        "random": {"expected_accuracy_if_labels_balanced": 1 / 3, "coverage": 1.0,
            "basis": "seeded uniform up/down/flat; class imbalance changes accuracy"},
        "flat": {"expected_accuracy": "realized flat-label prevalence", "coverage": 1.0,
            "basis": "always predicts flat"},
        "always_up": {"expected_accuracy": "realized up-label prevalence", "binary_accuracy": None,
            "coverage": 1.0, "basis": "constant up class; binary score excludes flat labels"},
        "always_down": {"expected_accuracy": "realized down-label prevalence", "binary_accuracy": None,
            "coverage": 1.0, "basis": "constant down class; binary score excludes flat labels"}}
