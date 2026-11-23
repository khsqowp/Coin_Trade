"""Preregistered stock OHLCV quality filter for train-only research."""

from __future__ import annotations

import numpy as np
import pandas as pd


class SymbolQualityError(ValueError):
    """The source symbol exceeds the preregistered corruption limit."""


MAX_BAD_ROW_FRACTION = 0.05
MAX_CONSECUTIVE_BAD_ROWS = 3
HALT_ZERO_VOLUME_RUN = 5
KRX_TICK_SIZE_TABLE = (
    (1_000, 1), (5_000, 5), (10_000, 10), (50_000, 50),
    (100_000, 100), (500_000, 500), (float("inf"), 1_000),
)


def tick_size(price: float) -> int:
    """Return the preregistered KRX tick size for a positive price."""
    value = float(price)
    for upper_bound, size in KRX_TICK_SIZE_TABLE:
        if value < upper_bound:
            return size
    return 1_000


def _price_halt(frame: pd.DataFrame) -> pd.Series:
    prices = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    values = prices.to_numpy(dtype=float)
    return pd.Series(~(np.isfinite(values).all(axis=1) & (values > 0).all(axis=1)),
                      index=frame.index)


def _beyond_tick(left: pd.Series, right: pd.Series) -> pd.Series:
    gap = (left - right).abs()
    tolerance = [min(tick_size(a), tick_size(b)) for a, b in zip(left, right)]
    return gap > pd.Series(tolerance, index=left.index)


def _invalid_ohlc(frame: pd.DataFrame) -> pd.Series:
    prices = frame[["open", "high", "low", "close"]]
    numeric = prices.apply(pd.to_numeric, errors="coerce")
    finite_positive = pd.DataFrame(np.isfinite(numeric.to_numpy()) & (numeric.to_numpy() > 0),
                                   index=frame.index, columns=prices.columns)
    valid_prices = finite_positive.all(axis=1)
    ordered = numeric["high"] >= numeric["low"]
    valid_numeric = numeric.loc[valid_prices]
    for price_name, bound_name, above in (
        ("open", "high", True), ("close", "high", True),
        ("open", "low", False), ("close", "low", False),
    ):
        price, bound = valid_numeric[price_name], valid_numeric[bound_name]
        outside = price > bound if above else price < bound
        invalid_rows = outside & _beyond_tick(price, bound)
        ordered.loc[invalid_rows.index] &= ~invalid_rows
    return valid_prices & ~ordered


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

    price_halted = _price_halt(frame)
    invalid = _invalid_ohlc(frame) & ~price_halted
    invalid_count = int(invalid.sum())
    invalid_fraction = invalid_count / len(frame)
    if (invalid_fraction > MAX_BAD_ROW_FRACTION
            or _longest_run(invalid) >= MAX_CONSECUTIVE_BAD_ROWS):
        raise SymbolQualityError(
            f"{symbol}: invalid OHLC rows={invalid_count}/{len(frame)} "
            f"({invalid_fraction:.2%}), consecutive_limit={MAX_CONSECUTIVE_BAD_ROWS}"
        )

    halted = price_halted.copy()
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
