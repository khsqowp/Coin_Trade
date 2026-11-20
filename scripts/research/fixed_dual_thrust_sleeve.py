"""Fixed-rule Dual Thrust sleeve simulator for the preregistered blend study.

This module is historical-research-only. Inputs are completed daily UTC bars and
verified funding settlements. Funding at either the entry or exit instant is
excluded because event ordering within that timestamp is not identifiable.
"""
from __future__ import annotations

from collections.abc import Mapping
import math

import pandas as pd


def simulate_dual_thrust(
    frames: Mapping[str, pd.DataFrame],
    funding: Mapping[str, pd.DataFrame],
    *,
    start: pd.Timestamp,
    end_exclusive: pd.Timestamp,
    top_k: int = 8,
    hold_days: int = 20,
    cost: float = 0.001,
) -> dict:
    """Simulate next-open entries, close exits, one-way costs and exact funding.

    Each frame requires Open/High/Low/Close/DIRECTION/SCORE columns indexed by
    UTC daily-open timestamps. Funding frames require rate/markPrice columns on
    UTC settlement timestamps. Positions cannot be re-entered on the same day
    they exit: an exit scheduled for that day's close still occupies its slot
    at that day's open.
    """
    if top_k <= 0 or top_k % 2 or hold_days <= 0 or not 0 <= cost < 1:
        raise ValueError("top_k must be positive/even, hold_days positive, cost in [0,1)")
    start = pd.Timestamp(start)
    end_exclusive = pd.Timestamp(end_exclusive)
    if start.tz is None or end_exclusive.tz is None or start >= end_exclusive:
        raise ValueError("start/end_exclusive must be ordered timezone-aware timestamps")
    dates = sorted({d for frame in frames.values() for d in frame.index if start <= d < end_exclusive})
    if len(dates) < 2:
        raise ValueError("insufficient common evaluation dates")
    for sym, frame in frames.items():
        if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
            raise ValueError(f"{sym}: daily index must be timezone-aware")
        if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
            raise ValueError(f"{sym}: daily index must be unique and increasing")
        if not {"Open", "High", "Low", "Close", "DIRECTION", "SCORE"}.issubset(frame.columns):
            raise ValueError(f"{sym}: required daily columns missing")
    per_side = top_k // 2
    positions: dict[str, dict] = {}
    cash = 1.0
    nav_rows: list[tuple[pd.Timestamp, float]] = []
    fee_paid = 0.0
    funding_pnl = 0.0
    turnover = 0.0
    trade_count = 0

    def price(sym: str, day: pd.Timestamp, column: str) -> float | None:
        frame = frames[sym]
        if day not in frame.index:
            return None
        value = float(frame.at[day, column])
        return value if math.isfinite(value) and value > 0 else None

    def mark(day: pd.Timestamp, column: str) -> float:
        value = cash
        for sym, pos in positions.items():
            px = price(sym, day, column)
            if px is None:
                px = pos["last_mark"]
            value += pos["notional"] + pos["direction"] * pos["qty"] * (px - pos["entry_price"])
        return value

    for idx, day in enumerate(dates):
        # New positions are decided using the prior completed daily signal and
        # entered at today's open. Positions expiring at today's close still
        # consume their slots at the open.
        if idx > 0:
            signal_day = dates[idx - 1]
            nlong = sum(p["direction"] > 0 for p in positions.values())
            nshort = sum(p["direction"] < 0 for p in positions.values())
            long_free, short_free = per_side - nlong, per_side - nshort
            long_candidates, short_candidates = [], []
            for sym, frame in frames.items():
                if sym in positions or signal_day not in frame.index or day not in frame.index:
                    continue
                direction = int(frame.at[signal_day, "DIRECTION"])
                score = float(frame.at[signal_day, "SCORE"])
                if direction not in (-1, 0, 1) or not math.isfinite(score):
                    raise ValueError(f"{sym}: invalid direction or score")
                if direction > 0:
                    long_candidates.append((sym, score))
                elif direction < 0:
                    short_candidates.append((sym, score))
            long_candidates.sort(key=lambda x: (-x[1], x[0]))
            short_candidates.sort(key=lambda x: (-x[1], x[0]))
            selected = [(s, 1) for s, _ in long_candidates[:max(0, long_free)]]
            selected += [(s, -1) for s, _ in short_candidates[:max(0, short_free)]]
            if selected:
                equity_open = mark(day, "Open")
                slot_notional = equity_open / top_k
                for sym, direction in selected:
                    entry = price(sym, day, "Open")
                    if entry is None or slot_notional <= 0:
                        continue
                    notional = min(slot_notional, max(0.0, cash))
                    if notional <= 0:
                        continue
                    qty = notional / entry
                    paid = notional * cost
                    cash -= notional + paid
                    fee_paid += paid
                    turnover += notional
                    positions[sym] = {
                        "direction": direction, "entry_price": entry, "qty": qty,
                        "notional": notional, "entry_time": day,
                        "exit_day": dates[min(idx + hold_days, len(dates) - 1)],
                        "last_mark": entry,
                    }

        close_time = day + pd.Timedelta(days=1)
        for sym, pos in list(positions.items()):
            # Apply every observed settlement strictly inside (entry, exit).
            settlements = funding.get(sym)
            if settlements is not None and not settlements.empty:
                if not isinstance(settlements.index, pd.DatetimeIndex) or settlements.index.tz is None:
                    raise ValueError(f"{sym}: funding index must be timezone-aware")
                if not settlements.index.is_monotonic_increasing or settlements.index.has_duplicates:
                    raise ValueError(f"{sym}: funding settlements must be unique and increasing")
                last_funding = pos.get("last_funding_time", pos["entry_time"])
                eligible = settlements.loc[(settlements.index > last_funding) & (settlements.index < close_time)]
                for _, event in eligible.iterrows():
                    rate, mark_price = float(event["rate"]), float(event["markPrice"])
                    if not math.isfinite(rate) or not math.isfinite(mark_price) or mark_price <= 0:
                        raise ValueError(f"{sym}: invalid funding event")
                    flow = -pos["direction"] * pos["qty"] * mark_price * rate
                    cash += flow
                    funding_pnl += flow
                if len(eligible):
                    pos["last_funding_time"] = eligible.index[-1]
            close = price(sym, day, "Close")
            if close is not None:
                pos["last_mark"] = close
            if day >= pos["exit_day"] or idx == len(dates) - 1:
                if close is None:
                    raise ValueError(f"{sym}: cannot close position without final close price")
                pnl = pos["direction"] * pos["qty"] * (close - pos["entry_price"])
                paid = pos["qty"] * close * cost
                cash += pos["notional"] + pnl - paid
                fee_paid += paid
                turnover += pos["qty"] * close
                trade_count += 1
                del positions[sym]

        nav = mark(day, "Close")
        if not math.isfinite(nav) or nav <= 0:
            raise ValueError(f"nonpositive/nonfinite NAV at {day}")
        nav_rows.append((day, nav))

    nav = pd.Series([v for _, v in nav_rows], index=pd.DatetimeIndex([d for d, _ in nav_rows]), name="nav")
    returns = nav.pct_change().dropna()
    years = (nav.index[-1] - nav.index[0]).total_seconds() / (365.2425 * 86400)
    peak = nav.cummax()
    sharpe = float(returns.mean() / returns.std(ddof=1) * math.sqrt(365)) if len(returns) > 1 and returns.std(ddof=1) else 0.0
    return {
        "nav": nav, "terminal_nav": float(nav.iloc[-1]),
        "total_return": float(nav.iloc[-1] - 1.0),
        "cagr": float(nav.iloc[-1] ** (1 / years) - 1) if years > 0 else float("nan"),
        "mdd": float((1 - nav / peak).max()), "sharpe_365": sharpe,
        "trades": trade_count, "fees": fee_paid, "funding_pnl": funding_pnl,
        "turnover": turnover,
    }
