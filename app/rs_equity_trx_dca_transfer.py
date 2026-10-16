"""Causal multi-stock adaptation of the explicit TRX DCA swing rule."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-cache")

import pandas_ta as ta

from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_transfer import EquityPanel, load_equity_panel


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/trx_dca_swing_transfer.json"
START = pd.Timestamp("2019-01-01")
TRANCHES = 5
DCA_DROP = 0.03
RSI_OVERBOUGHT = 70.0
RETRACE = 0.03
MAX_POSITIONS = 8


def _signals(panel: EquityPanel) -> dict[str, dict[str, np.ndarray]]:
    output = {}
    for j, symbol in enumerate(panel.symbols):
        close = pd.Series(panel.c[:, j], index=panel.dates)
        valid = close.notna()
        close = close.loc[valid]
        ema9 = ta.ema(close, length=9)
        ema21 = ta.ema(close, length=21)
        rsi = ta.rsi(close, length=14)
        cross_up = (ema9.shift(1) <= ema21.shift(1)) & (ema9 > ema21)
        cross_down = (ema9.shift(1) >= ema21.shift(1)) & (ema9 < ema21)
        output[symbol] = {
            "cross_up": cross_up.reindex(panel.dates).to_numpy(dtype=float, na_value=0).astype(bool),
            "cross_down": cross_down.reindex(panel.dates).to_numpy(dtype=float, na_value=0).astype(bool),
            "rsi": rsi.reindex(panel.dates).to_numpy(float),
        }
    return output


def simulate_dca(
    panel: EquityPanel,
    fee_pct_one_way: float,
    slippage: np.ndarray,
    sell_tax_pct: float,
    max_positions: int = MAX_POSITIONS,
) -> dict[str, Any]:
    """Simulate prior-close decisions filled at the following open."""
    if fee_pct_one_way < 0 or sell_tax_pct < 0 or max_positions < 1:
        raise ValueError("invalid fee, tax, or position limit")
    if slippage.shape != (len(panel.symbols),) or (slippage < 0).any():
        raise ValueError("slippage must be a nonnegative per-symbol vector")
    signals = _signals(panel)
    first = int(panel.dates.searchsorted(START))
    if first == 0 or first >= len(panel.dates):
        raise ValueError("daily panel does not cover the required start date")
    dates = panel.dates[first:]
    fee = fee_pct_one_way / 100
    tax = sell_tax_pct / 100
    cash = 1.0
    marks = np.zeros(len(panel.symbols), dtype=float)
    positions: dict[int, dict[str, Any]] = {}
    equity_curve = []
    trade_count = 0
    buy_count = 0
    partial_sell_count = 0
    full_sell_count = 0
    rejected_entry_count = 0
    max_open_positions = 0
    symbol_index = {symbol: j for j, symbol in enumerate(panel.symbols)}

    for i in range(first, len(panel.dates)):
        day_open = panel.o[i]
        day_close = panel.c[i]
        day_tradable = panel.tradable[i]
        prior = i - 1

        def sell_quantity(j: int, quantity: float) -> float:
            nonlocal cash, trade_count
            price = day_open[j] * (1 - slippage[j])
            proceeds = quantity * price * (1 - fee) * (1 - tax)
            cash += proceeds
            trade_count += 1
            return proceeds

        # Process previous-close signals at today's first executable price.
        for j in list(positions):
            position = positions[j]
            symbol = panel.symbols[j]
            info = signals[symbol]
            prior_close = panel.c[prior, j]
            if np.isfinite(info["rsi"][prior]) and info["rsi"][prior] >= RSI_OVERBOUGHT:
                position["overbought_seen"] = True
            if position["overbought_seen"] and np.isfinite(prior_close):
                old_peak = position["peak_after_overbought"]
                position["peak_after_overbought"] = max(
                    prior_close, prior_close if old_peak is None else old_peak
                )
                if prior_close <= position["peak_after_overbought"] * (1 - RETRACE):
                    position["partial_exit_pending"] = True
            if info["cross_down"][prior]:
                position["full_exit_pending"] = True
            if not day_tradable[j] or not np.isfinite(day_open[j]) or day_open[j] <= 0:
                continue
            if position["partial_exit_pending"] and not position["half_sold"]:
                quantity = position["qty"] / 2
                sell_quantity(j, quantity)
                position["qty"] -= quantity
                position["half_sold"] = True
                position["partial_exit_pending"] = False
                partial_sell_count += 1
            if position["full_exit_pending"] and position["qty"] > 0:
                sell_quantity(j, position["qty"])
                del positions[j]
                full_sell_count += 1
                continue
            if (
                prior_close > 0
                and position["tranches_used"] < TRANCHES
                and prior_close <= position["last_buy_price"] * (1 - DCA_DROP)
            ):
                position["dca_pending"] = True
            if position["dca_pending"] and position["tranches_used"] < TRANCHES:
                amount = min(cash, position["tranche_budget"])
                if amount > 1e-12:
                    buy_price = day_open[j] * (1 + slippage[j])
                    quantity = amount * (1 - fee) / buy_price
                    position["qty"] += quantity
                    position["tranches_used"] += 1
                    position["last_buy_price"] = buy_price
                    position["dca_pending"] = False
                    cash -= amount
                    buy_count += 1

        # Allocate new positions equally across the declared maximum slots.
        open_equity = cash + sum(
            position["qty"] * (
                day_open[j] if np.isfinite(day_open[j]) else marks[j]
            )
            for j, position in positions.items()
        )
        candidates = [
            j for j, symbol in enumerate(panel.symbols)
            if j not in positions and signals[symbol]["cross_up"][prior]
            and panel.eligible[i, j] and day_tradable[j]
            and np.isfinite(day_open[j]) and day_open[j] > 0
        ]
        candidates.sort(key=lambda j: panel.symbols[j])
        free_slots = max(0, max_positions - len(positions))
        rejected_entry_count += max(0, len(candidates) - free_slots)
        for j in candidates[:free_slots]:
            allocation = open_equity / max_positions
            tranche = min(cash, allocation / TRANCHES)
            if tranche <= 1e-12:
                break
            buy_price = day_open[j] * (1 + slippage[j])
            quantity = tranche * (1 - fee) / buy_price
            positions[j] = {
                "qty": quantity,
                "tranches_used": 1,
                "last_buy_price": buy_price,
                "tranche_budget": allocation / TRANCHES,
                "overbought_seen": False,
                "peak_after_overbought": None,
                "half_sold": False,
                "partial_exit_pending": False,
                "full_exit_pending": False,
                "dca_pending": False,
            }
            cash -= tranche
            buy_count += 1
        max_open_positions = max(max_open_positions, len(positions))

        valid_close = np.isfinite(day_close) & (day_close > 0)
        marks[valid_close] = day_close[valid_close]
        equity = cash + sum(
            position["qty"] * marks[j] for j, position in positions.items()
        )
        equity_curve.append(equity)

    curve = np.asarray(equity_curve, dtype=float)
    if not np.isfinite(curve).all() or (curve <= 0).any():
        raise ValueError("portfolio equity became non-finite or non-positive")
    years = (dates[-1] - dates[0]).days / 365.25
    daily_returns = curve[1:] / curve[:-1] - 1
    drawdown = curve / np.maximum.accumulate(curve) - 1
    return {
        "metrics": {
            "cagr": float(((curve[-1] / curve[0]) ** (1 / years) - 1) * 100),
            "mdd": float(-drawdown.min() * 100),
            "sharpe": float(daily_returns.mean() / daily_returns.std(ddof=1) * np.sqrt(365))
            if daily_returns.std(ddof=1) else 0.0,
            "final": float(curve[-1]),
            "trades": trade_count,
            "buys_including_dca": buy_count,
            "partial_sells": partial_sell_count,
            "full_sells": full_sell_count,
            "rejected_entries_at_slot_limit": rejected_entry_count,
            "max_open_positions": max_open_positions,
        },
        "daily_equity": curve.tolist(),
        "daily_dates": [str(date.date()) for date in dates],
    }


def run_market(market: str) -> dict[str, Any]:
    panel = load_equity_panel(market)
    rows = []
    for cost_name, fee, slip, tax in _costs(panel):
        # The source coin backtest uses a 0.1% one-way fee. The stock transfer
        # uses established market-specific fee/tax/slippage assumptions instead.
        simulation = simulate_dca(panel, fee, np.asarray(slip, dtype=float), tax)
        rows.append({"cost_case": cost_name, **simulation})
    dates = panel.dates[int(panel.dates.searchsorted(START)):]
    return {
        "market": market,
        "symbols": len(panel.symbols),
        "date_range": [str(dates[0].date()), str(dates[-1].date())],
        "source_rule_parameters": {
            "ema_fast": 9, "ema_slow": 21, "dca_drop_pct": 3.0,
            "max_tranches": 5, "rsi_period": 14, "overbought_rsi": 70,
            "retrace_pct": 3.0,
        },
        "portfolio_transfer_parameters": {
            "max_positions": MAX_POSITIONS,
            "per_position_budget_fraction": 1 / MAX_POSITIONS,
            "tranche_allocation": "initial position budget / 5; capped by available cash",
            "execution": "signal at prior close, order at next tradable open; mark at close",
        },
        "rows": rows,
    }


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    payload = {
        "source": "app/trx_dca_swing_backtest.py explicit user-confirmed rule",
        "source_execution": "single TRX strategy at same-close observed price; source backtest uses 0.1% fee",
        "equity_transfer_execution": "multi-stock capped-slot portfolio; next-open fills; market-specific costs; no intraday path fabricated",
        "markets": {market: run_market(market) for market in ("US", "KR")},
        "limitations": [
            "The source is TRX-only; applying its triggers to many stocks is a cross-sectional transfer, not a literal same-asset replication.",
            "The source same-close fills are shifted to next-open fills to avoid lookahead.",
            "An eight-position cap and equal per-position budget are portfolio-transfer assumptions; the original uses one coin and up to five tranches of account equity.",
            "RSI retrace and EMA-cross conditions use daily closes; no intraday fill path is claimed.",
            "Current cached universe has survivorship and selection bias.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps({m: [r["metrics"] for r in v["rows"]]
                      for m, v in payload["markets"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
