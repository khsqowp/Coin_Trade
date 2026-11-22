"""Preregistered stock OHLCV quality filter for train-only research."""

from __future__ import annotations

import numpy as np
import pandas as pd


class SymbolQualityError(ValueError):
    """The source symbol exceeds the preregistered corruption limit."""


MAX_BAD_ROW_FRACTION = 0.05
MAX_CONSECUTIVE_BAD_ROWS = 3
HALT_ZERO_VOLUME_RUN = 5


def _invalid_ohlc(frame: pd.DataFrame) -> pd.Series:
    prices = frame[["open", "high", "low", "close"]]
    numeric = prices.apply(pd.to_numeric, errors="coerce")
    finite_positive = pd.DataFrame(np.isfinite(numeric.to_numpy()) & (numeric.to_numpy() > 0),
                                   index=frame.index, columns=prices.columns)
    ordered = ((frame["high"] >= frame["low"])
               & (frame["open"] >= frame["low"]) & (frame["open"] <= frame["high"])
               & (frame["close"] >= frame["low"]) & (frame["close"] <= frame["high"]))
    return ~(finite_positive.all(axis=1) & ordered)


def _longest_run(mask: pd.Series) -> int:
    longest = current = 0
    for value in mask.tolist():
        current = current + 1 if bool(value) else 0
        longest = max(longest, current)
    return longest


def filter_equity_bars(frame: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame, dict[str, int]]:
    """Drop malformed/halted bars; reject symbols with concentrated OHLC corruption."""
    required = {"open_time", "open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"bar columns missing: {sorted(required - set(frame.columns))}")
    if frame.empty:
        return frame.copy(), {"rows": 0, "invalid_ohlc": 0, "halt_bars": 0}

    invalid = _invalid_ohlc(frame)
    invalid_count = int(invalid.sum())
    invalid_fraction = invalid_count / len(frame)
    if (invalid_fraction > MAX_BAD_ROW_FRACTION
            or _longest_run(invalid) >= MAX_CONSECUTIVE_BAD_ROWS):
        raise SymbolQualityError(
            f"{symbol}: invalid OHLC rows={invalid_count}/{len(frame)} "
            f"({invalid_fraction:.2%}), consecutive_limit={MAX_CONSECUTIVE_BAD_ROWS}"
        )

    halted = pd.Series(False, index=frame.index)
    if "volume" in frame.columns:
        zero_volume = frame["volume"].notna() & (frame["volume"] == 0)
        run_start = None
        for position, is_zero in enumerate(zero_volume.tolist() + [False]):
            if is_zero and run_start is None:
                run_start = position
            elif not is_zero and run_start is not None:
                if position - run_start >= HALT_ZERO_VOLUME_RUN:
                    halted.iloc[run_start:position] = True
                run_start = None

    rejected = invalid | halted
    kept = frame.loc[~rejected].copy().reset_index(drop=True)
    return kept, {"rows": len(frame), "invalid_ohlc": invalid_count,
                  "halt_bars": int(halted.sum())}
