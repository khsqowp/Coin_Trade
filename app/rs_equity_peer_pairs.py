"""Causal, explicitly non-literal equity adaptation of the crypto pair signal.

At each daily close, choose each symbol's highest-correlation peer using only
the trailing window ending at that close, then trade the log-ratio z-score.
All active pairs contribute equal gross exposure and opposite signed legs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.rs_equity_map_run import _metrics, _simulate
from app.rs_equity_transfer import EquityPanel, load_equity_panel

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/equity_peer_pairs.json"
VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/equity_peer_pairs_validation.json"
LOOKBACK_CORR = 180
LOOKBACK_Z = 60
ENTRY_Z = (1.5, 2.0, 2.5)
EXIT_Z = (0.25, 0.5, 1.0)
STOP_Z = (3.0, 3.5)
CADENCES = (1, 2, 3, 7)


def _point_in_time_peer_and_z(close: np.ndarray, min_obs: int = LOOKBACK_CORR,
                              z_window: int = LOOKBACK_Z) -> tuple[np.ndarray, np.ndarray]:
    """Return peer indices and ratio z-scores; each row uses data no later than its date."""
    nday, nsym = close.shape
    ret = np.full_like(close, np.nan, dtype=float)
    ret[1:] = close[1:] / close[:-1] - 1.0
    peers = np.full((nday, nsym), -1, dtype=np.int32)
    zscores = np.full((nday, nsym), np.nan, dtype=float)
    for t in range(nday):
        lo = max(1, t - min_obs + 1)
        sample = ret[lo:t + 1]
        valid = np.isfinite(sample).astype(float)
        values = np.nan_to_num(sample, nan=0.0)
        count = valid.T @ valid
        sums = values.T @ valid
        sums2 = (values * values).T @ valid
        cross = values.T @ values
        safe_count = np.maximum(count, 1.0)
        covariance = cross - sums * sums.T / safe_count
        var_i = np.maximum(sums2 - sums * sums / safe_count, 0.0)
        denom = np.sqrt(var_i * var_i.T)
        corr_matrix = np.divide(covariance, denom, out=np.full_like(covariance, -np.inf),
                                where=(count >= min_obs) & (denom > 0))
        np.fill_diagonal(corr_matrix, -np.inf)
        best = np.argmax(corr_matrix, axis=1)
        best_corr = corr_matrix[np.arange(nsym), best]
        for i in range(nsym):
            best_j = int(best[i]) if np.isfinite(best_corr[i]) else -1
            if best_j < 0 or not (close[t, i] > 0 and close[t, best_j] > 0):
                continue
            peers[t, i] = best_j
            start = max(0, t - z_window + 1)
            ratio = np.log(close[start:t + 1, i]) - np.log(close[start:t + 1, best_j])
            ratio = ratio[np.isfinite(ratio)]
            if len(ratio) < z_window:
                continue
            sd = ratio.std(ddof=0)
            if sd > 0 and len(ratio) == z_window:
                zscores[t, i] = (ratio[-1] - ratio.mean()) / sd
    return peers, zscores


def make_pair_targets(panel: EquityPanel, entry_z: float, exit_z: float,
                      stop_z: float, *,
                      peer_data: tuple[np.ndarray, np.ndarray] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Create daily dollar-neutral targets; close/reopen a pair when peer changes."""
    if not 0 < exit_z < entry_z < stop_z:
        raise ValueError("require 0 < exit_z < entry_z < stop_z")
    peers, zscores = peer_data if peer_data is not None else _point_in_time_peer_and_z(panel.c)
    nday, nsym = panel.c.shape
    pair_state = np.zeros(nsym, dtype=np.int8)
    pair_peer = np.full(nsym, -1, dtype=np.int32)
    targets = np.zeros((nday, nsym), dtype=float)
    active_counts = np.zeros(nday, dtype=np.int32)
    for t in range(nday):
        for i in range(nsym):
            j, z = int(peers[t, i]), zscores[t, i]
            if j < 0 or not np.isfinite(z) or not panel.eligible[t, i] or not panel.eligible[t, j]:
                pair_state[i], pair_peer[i] = 0, -1
                continue
            if pair_peer[i] != j:
                pair_state[i], pair_peer[i] = 0, j
            state = pair_state[i]
            if state == 0:
                if z <= -entry_z:
                    state = 1  # long i / short peer
                elif z >= entry_z:
                    state = -1  # short i / long peer
            elif abs(z) <= exit_z or abs(z) >= stop_z or np.sign(z) == state:
                state = 0
            pair_state[i] = state
        contributions = np.zeros(nsym, dtype=float)
        count = 0
        for i, state in enumerate(pair_state):
            j = pair_peer[i]
            if state and j >= 0 and panel.eligible[t, i] and panel.eligible[t, j]:
                contributions[i] += state
                contributions[j] -= state
                count += 1
        gross = np.abs(contributions).sum()
        if gross > 0:
            targets[t] = contributions / gross
        active_counts[t] = count
    return targets, active_counts


def _costs(panel: EquityPanel) -> list[tuple[str, float, float, float]]:
    if panel.market == "US":
        return [("KIS_0.36pct", .0036, 1.0, 0.01), ("low_0.08pct", .0008, 1.0, 0.01)]
    return [("KR_base", 0.0, 1.0, 0.03), ("KR_2x_slippage", 0.0, 2.0, 0.03)]


def run_market(market: str) -> dict[str, Any]:
    panel = load_equity_panel(market)
    d0 = int(panel.dates.searchsorted(pd.Timestamp("2019-01-01")))
    market_code = 0 if market == "US" else 1
    rows = []
    for entry in ENTRY_Z:
        for exit_ in EXIT_Z:
            for stop in STOP_Z:
                targets, counts = make_pair_targets(panel, entry, exit_, stop)
                for cadence in CADENCES:
                    for cost_case, fee, slip_mult, borrow in _costs(panel):
                        returns = _simulate(
                            targets, np.zeros(len(panel.dates), dtype=bool), panel.c,
                            panel.o, panel.tradable, panel.slip, market_code, cadence,
                            fee, slip_mult, borrow, 0.0, d0,
                        )
                        metrics = _metrics(returns, panel.dates, d0, len(panel.dates))
                        eq = np.cumprod(1 + returns[d0:])
                        rows.append({
                            "entry_z": entry, "exit_z": exit_, "stop_z": stop,
                            "cadence": cadence, "cost_case": cost_case,
                            "metrics": metrics, "active_pair_days": int(np.count_nonzero(counts[d0:])),
                            "avg_active_pairs": float(counts[d0:].mean()),
                            "daily_dates": [str(x.date()) for x in panel.dates[d0:]],
                            "daily_equity": eq.tolist(),
                        })
    return {
        "market": market, "symbols": panel.symbols, "dates": [str(x.date()) for x in panel.dates[d0:]],
        "grid": {"entry_z": ENTRY_Z, "exit_z": EXIT_Z, "stop_z": STOP_Z, "cadence": CADENCES,
                 "cost_cases": [x[0] for x in _costs(panel)]},
        "rows": rows,
        "definition": "Causal equity-peer adaptation; not literal reproduction of the crypto BTC/ETH/SOL/BNB pair strategy.",
    }


def main() -> None:
    payload = {"markets": {m: run_market(m) for m in ("US", "KR")}}
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({m: len(v["rows"]) for m, v in payload["markets"].items()}))


if __name__ == "__main__":
    main()
