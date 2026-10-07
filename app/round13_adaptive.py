"""Online completed-trade scale through the unchanged engine's mapping API.

The fixed research engine asks entry_scale.get at every opening. Its current
positions contain only executions already made. Fixed-hold, no-stop policies
allow completed exits to be recovered from the immediately prior completed
close. The adapter reads no price beyond i-1 and resets with every simulation.
"""

import sys
import numpy as np


def posterior_scale(returns, mode, window):
    recent = np.asarray(returns[-window:])
    positive, negative = recent[recent > 0], -recent[recent <= 0]
    probability = (len(positive) + 10) / (len(recent) + 20)
    if mode == "win":
        return float(np.clip((probability - 0.35) / 0.25, 0.25, 1.0))
    win = (positive.sum() + 0.2) / (len(positive) + 10)
    loss = (negative.sum() + 0.2) / (len(negative) + 10)
    edge = probability - (1 - probability) / (win / loss)
    return float(0.25 + 0.75 * np.clip(edge / 0.25, 0, 1))


class CompletedTradeScale:
    def __init__(self, mode, window):
        if mode not in ("win", "payoff") or window < 1:
            raise ValueError("invalid shrink policy")
        self.mode, self.window = mode, window
        self.seen = {}
        self.completed = []
        self.history = []
        self.last_i = None

    def get(self, date, default=0.0):
        local = sys._getframe(1).f_locals
        required = {"i", "s", "dates", "positions", "a", "fee", "hold_days"}
        if not required <= local.keys():
            raise RuntimeError(
                "online scale requires the fixed research engine mapping call"
            )
        i, s, dates = local["i"], local["s"], local["dates"]
        if s != i - 1 or date != dates[s]:
            raise ValueError("online scale supports next-open execution only")
        if (
            local.get("stop", "none") != "none"
            or local.get("tp", "none") != "none"
            or local.get("stop_pct")
            or local.get("tp_pct")
            or local.get("strategy_data") is not None
        ):
            raise ValueError(
                "online scale supports fixed-hold no-stop/no-switch policies"
            )
        if i == 1 or self.last_i is None or i <= self.last_i:
            self.seen, self.completed, self.history = {}, [], []
        positions, a = local["positions"], local["a"]
        fee, slip = local["fee"], local.get("slippage", 0.0)
        closed = []
        for symbol, p in self.seen.items():
            current = positions.get(symbol)
            if current is not None and current["entry"] == p["entry"]:
                continue
            # Missing-close exits are delayed by the engine, so use actual
            # disappearance rather than predicted expiry as the exit trigger.
            if p["exit"] > s or not np.isfinite(a["Close"][s, symbol]):
                raise AssertionError("unobserved or unsupported sale")
            entry = a["Open"][p["entry"], symbol] * (1 + slip)
            exit_price = a["Close"][s, symbol] * (1 - slip)
            value = exit_price / entry * (1 - fee) ** 2 - 1
            closed.append((symbol, value))
        # Common engine sells in insertion order, retained by seen snapshots.
        self.completed.extend(value for _, value in closed)
        self.seen = {k: dict(p) for k, p in positions.items()}
        scale = posterior_scale(self.completed, self.mode, self.window)
        self.history.append(
            dict(date=str(date), completed=len(self.completed), scale=scale)
        )
        self.last_i = i
        return scale
