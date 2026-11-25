"""RB500-US deterministic grid: exactly 500 TRAIN-only US daily configurations.

Families are listed in preregistered priority order. Parameter tuples are
enumerated with itertools.product in declared order, so the grid and its
SHA-256 are reproducible. Numeric 0 for a stop means "no stop".
"""
from __future__ import annotations

import hashlib
import itertools
import json

FAMILIES: tuple[tuple[str, dict[str, tuple]], ...] = (
    ("F01_MOM_12_1_XS", {
        "lookback_m": (6, 12), "skip_m": (0, 1), "top_n": (10, 20, 30, 50),
        "hold_d": (21, 63), "gate": ("none", "breadth50_sma200")}),
    ("F02_LOWVOL_QUALITY_XS", {
        "vol_window": (63, 252), "bottom_n": (10, 20, 30, 50), "hold_d": (21, 63),
        "gate": ("none", "breadth50_sma200"), "quality": ("none", "pos_12m")}),
    ("F03_RSI2_PULLBACK", {
        "rsi_thr": (5, 10, 15), "trend_sma": (100, 200), "max_hold": (5, 10),
        "stop_atr": (0, 2, 3)}),
    ("F04_DOWN_STREAK_REBOUND", {
        "streak_n": (2, 3, 4), "trend_sma": (100, 200), "hold_d": (3, 5, 10),
        "stop_atr": (2, 3)}),
    ("F05_GAP_DOWN_REVERSAL", {
        "gap_pct": (1, 2, 3), "trend": ("none", "sma200"), "hold_d": (3, 5, 10),
        "stop_atr": (2, 3)}),
    ("F06_NEAR_52W_HIGH", {
        "prox": (0.90, 0.95, 0.98), "trend": ("none", "sma200"), "hold_d": (10, 20, 40),
        "stop_atr": (2, 3)}),
    ("F07_VOLUME_SURGE_UP", {
        "vol_mult": (2, 3, 4), "trend": ("none", "sma50"), "hold_d": (3, 5, 10),
        "stop_atr": (2, 3)}),
    ("F08_MA_CROSS_REGIME", {
        "pair": ("10_50", "20_100", "50_200"), "regime": ("none", "breadth50_sma200"),
        "max_hold": (60, 120, 250), "stop_atr": (3, 4)}),
    ("F09_TURN_OF_MONTH", {
        "days_before_end": (1, 2, 3), "hold_d": (3, 5, 8, 10), "trend": ("none", "sma200")}),
    ("F10_VOL_BREAKOUT_CLOSE", {
        "k": (0.3, 0.5, 0.7, 1.0), "trend": ("none", "sma50", "sma200"),
        "hold_d": (1, 2, 3), "stop_atr": (0, 2)}),
    ("F11_SHORT_REVERSAL_XS", {
        "lookback_d": (5, 21), "bottom_n": (10, 20, 30), "hold_d": (5, 21),
        "gate": ("none", "breadth50_sma200")}),
    ("F12_DONCHIAN_TREND", {
        "entry_n": (20, 55, 120), "exit_m": (10, 20), "stop_atr": (2, 3, 4),
        "regime": ("none", "breadth50_sma200")}),
)


def build_grid() -> list[dict]:
    """Return the 500 configs in fixed order, each with family and config_id."""
    configs: list[dict] = []
    for family, axes in FAMILIES:
        names = tuple(axes)
        for values in itertools.product(*axes.values()):
            configs.append({"config_id": len(configs) + 1, "family": family,
                            **dict(zip(names, values))})
    return configs


def grid_sha256(configs: list[dict] | None = None) -> str:
    configs = build_grid() if configs is None else configs
    payload = "\n".join(json.dumps(c, sort_keys=True, separators=(",", ":")) for c in configs)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    grid = build_grid()
    print(len(grid), grid_sha256(grid))
