"""RB1000-US deterministic grid: exactly 200 TRAIN-only US configurations (lane US).

Families are listed in preregistered priority order (a-priori plausibility, see
PREREG_RB1000_US.md). Parameter tuples are enumerated with itertools.product in
declared order, so the grid and its SHA-256 are reproducible.
"""
from __future__ import annotations

import hashlib
import itertools
import json

FAMILIES: tuple[tuple[str, dict[str, tuple]], ...] = (
    ("L01_SECTOR_MOM_CURVE", {
        "lookback_m": (3, 6, 12), "top_k": (1, 2, 3),
        "curve_gate": ("none", "t10y2y_pos", "t10y2y_rise3m")}),
    ("L02_OPEX_WEEK_SPY", {
        "pre_days": (1, 3, 5), "hold_d": (1, 2, 4, 6), "trend": ("none", "sma200")}),
    ("L03_LOWBETA_BAB_XS", {
        "beta_window": (126, 252), "bottom_n": (10, 20, 30, 50), "rebal_d": (21, 63)}),
    ("L04_AMIHUD_ILLIQ_XS", {
        "window": (63, 252), "top_n": (10, 20, 30, 50), "rebal_d": (21, 63)}),
    ("L05_MULTIFACTOR_XS", {
        "factor_set": ("mom_52w", "mom_lowvol", "mom_52w_lowvol"),
        "top_n": (10, 20, 30), "rebal_d": (21, 63)}),
    ("L06_VIX_LEVEL_OVERLAY_SPY", {
        "mode": ("level20", "level25", "level30", "level35", "pct70", "pct80", "pct90"),
        "confirm_d": (1, 3)}),
    ("L07_VIX_SPIKE_REVERSAL_SPY", {
        "vix_thr": (25, 30, 35), "hold_d": (5, 10, 20)}),
    ("L08_SECTOR_RS_RATIO_TREND", {
        "ma_n": (50, 100, 200), "spy_trend": ("none", "spy_sma200"), "rebal_d": (5, 21)}),
    ("L09_GAP_UP_CONTINUATION", {
        "gap_pct": (1, 2, 3), "clv_min": (0.5, 0.8), "hold_d": (3, 10), "stop_atr": (2, 3)}),
    ("L10_CLOSE_AT_LOW_CAPITULATION", {
        "clv_max": (0.1, 0.2), "ret_max_pct": (-1, -2), "hold_d": (2, 5), "stop_atr": (2, 3)}),
    ("L11_52W_HIGH_VOLUME_COMBO", {
        "prox": (0.90, 0.95), "vol_mult": (1.5, 2), "hold_d": (10, 20), "stop_atr": (2, 3)}),
    ("L12_YEAREND_JANUARY_SPY", {
        "entry_before_ye": (2, 5), "hold_d": (10, 21), "trend": ("none", "sma200")}),
)

EXPECTED_COUNTS = {
    "L01_SECTOR_MOM_CURVE": 27, "L02_OPEX_WEEK_SPY": 24, "L03_LOWBETA_BAB_XS": 16,
    "L04_AMIHUD_ILLIQ_XS": 16, "L05_MULTIFACTOR_XS": 18, "L06_VIX_LEVEL_OVERLAY_SPY": 14,
    "L07_VIX_SPIKE_REVERSAL_SPY": 9, "L08_SECTOR_RS_RATIO_TREND": 12,
    "L09_GAP_UP_CONTINUATION": 24, "L10_CLOSE_AT_LOW_CAPITULATION": 16,
    "L11_52W_HIGH_VOLUME_COMBO": 16, "L12_YEAREND_JANUARY_SPY": 8,
}


def build_grid() -> list[dict]:
    """Return the 200 configs in fixed order, each with family and config_id."""
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
    counts: dict[str, int] = {}
    for c in grid:
        counts[c["family"]] = counts.get(c["family"], 0) + 1
    assert counts == EXPECTED_COUNTS, counts
    print(len(grid), grid_sha256(grid))
