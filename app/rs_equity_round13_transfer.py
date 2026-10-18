"""Transfer the source-declared Round13 account-policy batches to equities."""
from __future__ import annotations

import sys
from typing import Any

import numpy as np
import pandas as pd

from app.crypto_round13_extension import groups as extension_groups
from app.crypto_round13_final_batch import groups as final_groups


def round13_configs() -> list[dict[str, Any]]:
    configs = []
    for section, title, rows in extension_groups() + final_groups():
        configs.extend(
            {"phase": f"R13-{section}", "policy_group": title, **row}
            for row in rows
        )
    return configs


def posterior_trade_scale(
    returns: list[float] | np.ndarray, mode: str, window: int
) -> float:
    """Apply Round13's Beta(10,10) win or shrunken payoff scale."""
    if mode not in ("win", "payoff"):
        raise ValueError("unknown sizing mode")
    if window < 1:
        raise ValueError("window must be positive")
    recent = np.asarray(returns[-window:], dtype=float)
    if not np.isfinite(recent).all():
        raise ValueError("trade returns must be finite")
    positive = recent[recent > 0]
    negative = -recent[recent <= 0]
    probability = (len(positive) + 10) / (len(recent) + 20)
    if mode == "win":
        return float(np.clip((probability - 0.35) / 0.25, 0.25, 1.0))
    mean_win = (positive.sum() + 0.2) / (len(positive) + 10)
    mean_loss = (negative.sum() + 0.2) / (len(negative) + 10)
    edge = probability - (1 - probability) / (mean_win / mean_loss)
    return float(0.25 + 0.75 * np.clip(edge / 0.25, 0, 1))


def completed_reference_scales(
    dates: pd.DatetimeIndex,
    records: list[dict[str, Any]],
    mode: str,
    window: int,
) -> dict[pd.Timestamp, float]:
    """Map each close to a scale using only trades exited by that close."""
    ordered = sorted(records, key=lambda trade: (trade["exit"], trade["id"]))
    completed: list[float] = []
    cursor = 0
    scales = {}
    for i, date in enumerate(dates):
        while cursor < len(ordered) and ordered[cursor]["exit"] <= i:
            completed.append(ordered[cursor]["return_pct"] / 100)
            cursor += 1
        scales[pd.Timestamp(date)] = posterior_trade_scale(
            completed, mode, window
        )
    return scales


class OnlineCompletedTradeScale:
    """Stock-engine adapter for Round13's online completed-trade sizing."""

    def __init__(self, mode: str, window: int):
        if mode not in ("win", "payoff") or window < 1:
            raise ValueError("invalid online sizing policy")
        self.mode = mode
        self.window = window
        self.seen: dict[int, dict[str, Any]] = {}
        self.completed: list[float] = []
        self.last_i: int | None = None

    def get(self, date: pd.Timestamp, default: float = 0.0) -> float:
        """Return a scale based on completed positions visible at this open."""
        local = sys._getframe(1).f_locals
        required = {"i", "s", "dates", "positions", "a", "fee", "hold_days"}
        if not required.issubset(local):
            raise RuntimeError("online scale called outside the portfolio engine")
        i, s, dates = local["i"], local["s"], local["dates"]
        if s != i - 1 or date != dates[s]:
            raise ValueError("online sizing requires next-open execution")
        if i == 1 or self.last_i is None or i <= self.last_i:
            self.seen, self.completed = {}, []
        if (
            local.get("stop", "none") != "none"
            or local.get("tp", "none") != "none"
            or local.get("stop_pct", 0)
            or local.get("tp_pct", 0)
            or local.get("strategy_data") is not None
        ):
            raise ValueError("online sizing supports fixed-hold no-stop policies")

        positions = local["positions"]
        arrays = local["a"]
        fee = local["fee"]
        tax = local.get("sell_tax", 0.0)
        slip = np.asarray(local.get("slippage", 0.0), dtype=float)
        for symbol, prior in self.seen.items():
            current = positions.get(symbol)
            if current is not None and current["entry"] == prior["entry"]:
                continue
            if prior["exit"] > s or not np.isfinite(arrays["Close"][s, symbol]):
                raise AssertionError("online scale observed an unfinished trade")
            symbol_slip = float(slip[symbol]) if slip.ndim else float(slip)
            proceeds = (
                prior["qty"]
                * arrays["Close"][s, symbol]
                * (1 - symbol_slip)
                * (1 - fee)
                * (1 - tax)
            )
            self.completed.append(proceeds / prior["cost"] - 1)
        self.seen = {key: dict(position) for key, position in positions.items()}
        self.last_i = i
        return posterior_trade_scale(self.completed, self.mode, self.window)
