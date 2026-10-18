"""Portfolio-level transfer of the 16 crypto volume-spike research-loop rounds.

This supplements (does not replace) the 98-family signal grid. It preserves the
source signal/round parameters while applying stock costs and next-open fills.
Circuit decisions use information available at the open; a circuit crossed at
today's close can only block new orders from the next session.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.rs_equity_transfer import EquityPanel, load_equity_panel
from app.volume_spike_signal_core import find_signals


OUTPUT = Path(__file__).resolve().parents[1] / "docs/research/equity_transfer_2026-10/full_runs"
START_DATE = "2019-01-01"
ANN = 252


@dataclass(frozen=True)
class Round:
    name: str
    lookback: int = 20
    volume_multiple: float = 3.0
    price_cap_pct: float = 5.0
    hold_days: int = 20
    top_k: int = 8
    circuit_dd: float = 0.0
    circuit_resume_dd: float = 0.0
    rs_top_frac: float = 0.0
    require_positive_rs: bool = False
    sizing: str = "equal"
    max_weight: float = 0.35
    capital_fraction: float = 1.0


ROUNDS = (
    Round("R01_base_best_sweep"),
    Round("R02_circuit_20_10", circuit_dd=.20, circuit_resume_dd=.10),
    Round("R03_circuit_15_7", circuit_dd=.15, circuit_resume_dd=.07),
    Round("R04_circuit_25_12", circuit_dd=.25, circuit_resume_dd=.12),
    Round("R05_rs_top_half", rs_top_frac=.50),
    Round("R06_positive_rs_only", require_positive_rs=True),
    Round("R07_rs_half_circuit", circuit_dd=.20, circuit_resume_dd=.10, rs_top_frac=.50),
    Round("R08_inv_vol_sizing", sizing="inv_vol", max_weight=.25),
    Round("R09_top5_concentrated", top_k=5),
    Round("R10_top12_diversified", top_k=12),
    Round("R11_top12_cash35", top_k=12, capital_fraction=.65),
    Round("R12_top12_cash30", top_k=12, capital_fraction=.70),
    Round("R13_top12_cash40", top_k=12, capital_fraction=.60),
    Round("R14_top12_cash42", top_k=12, capital_fraction=.58),
    Round("R15_cap3_hold20", price_cap_pct=3.0),
    Round("R16_vol4_cap5_hold20", volume_multiple=4.0),
)


def _prepared(panel: EquityPanel, cfg: Round, d0: int) -> dict[str, np.ndarray]:
    nday, nsym = panel.c.shape
    signal = np.zeros((nday, nsym), dtype=bool)
    ratio = np.full((nday, nsym), np.nan)
    ret90 = np.full((nday, nsym), np.nan)
    vol20 = np.full((nday, nsym), np.nan)
    for j in range(nsym):
        valid = np.isfinite(panel.c[:, j])
        if valid.sum() < cfg.lookback + cfg.hold_days + 100:
            continue
        frame = pd.DataFrame({
            "Open": panel.o[:, j], "High": panel.h[:, j], "Low": panel.l[:, j],
            "Close": panel.c[:, j], "Volume": panel.v[:, j],
        }, index=panel.dates).dropna(subset=["Close"])
        out = find_signals(frame, cfg.lookback, cfg.volume_multiple, cfg.price_cap_pct)
        r = frame["Close"].pct_change(fill_method=None)
        out["RET90"] = frame["Close"].pct_change(90, fill_method=None)
        out["VOL20"] = r.shift(1).rolling(20).std() * np.sqrt(ANN)
        loc = panel.dates.get_indexer(out.index)
        valid_loc = loc >= 0
        loc = loc[valid_loc]
        src = out.iloc[np.flatnonzero(valid_loc)]
        signal[loc, j] = src["SIGNAL"].to_numpy(bool)
        ratio[loc, j] = src["VOL_RATIO"].to_numpy(float)
        ret90[loc, j] = src["RET90"].to_numpy(float)
        vol20[loc, j] = src["VOL20"].to_numpy(float)
    signal[:d0] = False
    return {"signal": signal, "ratio": ratio, "ret90": ret90, "vol20": vol20}


def _rank_candidates(indices: list[int], ratio: np.ndarray, ret90: np.ndarray,
                     t: int, cfg: Round) -> list[int]:
    cands = indices
    if cfg.rs_top_frac > 0:
        vals = np.asarray([ret90[t, j] for j in cands], dtype=float)
        good = np.isfinite(vals)
        if good.any():
            cutoff = float(np.quantile(vals[good], 1.0 - cfg.rs_top_frac))
            cands = [j for j in cands if np.isfinite(ret90[t, j]) and ret90[t, j] >= cutoff]
        else:
            cands = []
    if cfg.require_positive_rs:
        cands = [j for j in cands if np.isfinite(ret90[t, j]) and ret90[t, j] > 0]
    # Python's sort is stable: tied scores retain panel.symbols order.
    return sorted(cands, key=lambda j: ratio[t, j], reverse=True)


def _allocations(picked: list[int], vol20: np.ndarray, t: int, cfg: Round) -> dict[int, float]:
    if not picked:
        return {}
    if cfg.sizing == "equal":
        return {j: 1.0 / cfg.top_k for j in picked}
    raw = {j: (1.0 / vol20[t, j] if np.isfinite(vol20[t, j]) and vol20[t, j] > 0 else 0.0)
           for j in picked}
    total = sum(raw.values())
    if total <= 0:
        return {j: 1.0 / cfg.top_k for j in picked}
    clipped = {j: min(w / total, cfg.max_weight) for j, w in raw.items()}
    scale = min(1.0, sum(clipped.values()))
    if scale <= 0:
        return {}
    return {j: w / scale / cfg.top_k * len(picked) for j, w in clipped.items()}


def _simulate(panel: EquityPanel, signals: dict[str, np.ndarray], cfg: Round,
              d0: int, buy_cost: np.ndarray, sell_cost: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    nday, nsym = panel.c.shape
    signal, ratio = signals["signal"], signals["ratio"]
    ret90, vol20 = signals["ret90"], signals["vol20"]
    cash = 1.0
    qty = np.zeros(nsym, dtype=float)
    exits = np.full(nsym, -1, dtype=np.int64)
    equity = np.ones(nday, dtype=float)
    peak = 1.0
    entries_allowed = True
    halted_days = 0
    trades = 0
    exposure_days = 0
    prev_close = panel.c[d0 - 1].copy()

    for t in range(d0, nday):
        # Positions are closed at the planned expiry day's close. The slot is
        # therefore unavailable for today's open fill and becomes free tomorrow.
        for j in range(nsym):
            if exits[j] >= 0 and t > exits[j] and qty[j] != 0.0:
                # A missing session mark uses the last observed close, matching
                # the mark-to-market fallback below rather than inventing a fill.
                px = prev_close[j]
                if np.isfinite(px):
                    cash += qty[j] * px * (1.0 - sell_cost[j])
                    qty[j] = 0.0
                    exits[j] = -1
                    trades += 1

        # Circuit state uses only the currently observable opening mark; close
        # drawdown is acted on at the next session's open.
        open_equity = cash
        for j in range(nsym):
            mark = panel.o[t, j] if np.isfinite(panel.o[t, j]) else prev_close[j]
            if qty[j] != 0 and np.isfinite(mark):
                open_equity += qty[j] * mark
        peak = max(peak, open_equity)
        dd = (peak - open_equity) / peak if peak > 0 else 0.0
        if cfg.circuit_dd > 0 and dd >= cfg.circuit_dd:
            entries_allowed = False
        elif cfg.circuit_dd > 0 and not entries_allowed and dd <= cfg.circuit_resume_dd:
            entries_allowed = True
        if not entries_allowed:
            halted_days += 1

        occupied = int(np.count_nonzero(qty))
        free = max(0, cfg.top_k - occupied)
        if free and t > d0 and entries_allowed:
            sig_t = t - 1
            cands = [j for j in range(nsym)
                     if qty[j] == 0 and signal[sig_t, j] and panel.tradable[t, j]
                     and np.isfinite(ratio[sig_t, j])]
            cands = _rank_candidates(cands, ratio, ret90, sig_t, cfg)
            allocs = _allocations(cands[:cfg.top_k], vol20, sig_t, cfg)
            # Allocate from opening equity after overnight gaps and before new
            # orders, never from today's future close.
            equity_at_open = open_equity
            for j in list(allocs)[:free]:
                price = panel.o[t, j]
                allocation = min(equity_at_open * cfg.capital_fraction * allocs[j], cash)
                if not np.isfinite(price) or price <= 0 or allocation <= 0:
                    continue
                qty[j] = allocation * (1.0 - buy_cost[j]) / price
                cash -= allocation
                exits[j] = min(t + cfg.hold_days, nday - 1)

        close_equity = cash
        for j in range(nsym):
            close = panel.c[t, j]
            if not np.isfinite(close):
                close = prev_close[j]
            if qty[j] != 0 and np.isfinite(close):
                close_equity += qty[j] * close
            if np.isfinite(close):
                prev_close[j] = close
        # Exit on the planned holding-period close, applying the sell-side cost.
        # This close cannot free a slot for an order already filled at today's open.
        for j in range(nsym):
            if exits[j] == t and qty[j] != 0.0:
                close = panel.c[t, j]
                if not np.isfinite(close):
                    close = prev_close[j]
                if np.isfinite(close):
                    cash += qty[j] * close * (1.0 - sell_cost[j])
                    qty[j] = 0.0
                    exits[j] = -1
                    trades += 1
        # Mark the closing portfolio after any scheduled liquidation.
        close_equity = cash + sum(
            qty[j] * (panel.c[t, j] if np.isfinite(panel.c[t, j]) else prev_close[j])
            for j in range(nsym) if qty[j] != 0.0
            and np.isfinite(panel.c[t, j] if np.isfinite(panel.c[t, j]) else prev_close[j])
        )
        equity[t] = close_equity
        if np.any(qty != 0):
            exposure_days += 1
        peak = max(peak, close_equity)

    daily = np.zeros(nday, dtype=float)
    for t in range(d0 + 1, nday):
        daily[t] = equity[t] / equity[t - 1] - 1.0 if equity[t - 1] > 0 else -1.0
    stats = {"final_equity": float(equity[-1]), "trades": float(trades),
             "halted_days": float(halted_days), "exposure_fraction": exposure_days / max(1, nday - d0)}
    return daily, stats


def _metrics(returns: np.ndarray, dates: pd.DatetimeIndex, a: int, b: int) -> dict[str, float]:
    r = np.asarray(returns[a:b], dtype=float)
    if len(r) < 30:
        return {"cagr": np.nan, "mdd": np.nan, "sharpe": np.nan, "calmar": np.nan}
    growth = np.cumprod(1.0 + r)
    years = max((dates[b - 1] - dates[a]).days / 365.25, 1 / 365.25)
    cagr = float(growth[-1] ** (1.0 / years) - 1.0) if growth[-1] > 0 else -1.0
    high = np.maximum.accumulate(np.r_[1.0, growth])[1:]
    mdd = float(np.max(1.0 - growth / high))
    std = float(r.std())
    sharpe = float(r.mean() / std * np.sqrt(ANN)) if std > 0 else 0.0
    return {"cagr": cagr, "mdd": mdd, "sharpe": sharpe,
            "calmar": float(cagr / mdd) if mdd > 1e-12 else 0.0}


def _costs(panel: EquityPanel) -> list[tuple[str, np.ndarray, np.ndarray]]:
    if panel.market == "US":
        return [("KIS_0.36pct", np.full(len(panel.symbols), .0036), np.full(len(panel.symbols), .0036)),
                ("low_0.08pct", np.full(len(panel.symbols), .0008), np.full(len(panel.symbols), .0008))]
    return [("KR_base", .00015 + panel.slip, .00015 + .0018 + panel.slip),
            ("KR_2x_slippage", .00015 + 2 * panel.slip, .00015 + .0018 + 2 * panel.slip)]


def evaluate_market(market: str) -> dict[str, Any]:
    panel = load_equity_panel(market)
    d0 = int(panel.dates.searchsorted(pd.Timestamp(START_DATE)))
    configs = []
    rows = []
    signals_by_key: dict[tuple[Any, ...], dict[str, np.ndarray]] = {}
    for cfg in ROUNDS:
        key = (cfg.lookback, cfg.volume_multiple, cfg.price_cap_pct)
        if key not in signals_by_key:
            signals_by_key[key] = _prepared(panel, cfg, d0)
        sig = signals_by_key[key]
        signal_count = int(sig["signal"][d0:].sum())
        event_returns = []
        for t in range(d0, len(panel.dates) - cfg.hold_days - 1):
            for j in np.flatnonzero(sig["signal"][t]):
                entry = t + 1
                exit_ = entry + cfg.hold_days
                if panel.tradable[entry, j] and np.isfinite(panel.o[entry, j]) and np.isfinite(panel.c[exit_, j]):
                    event_returns.append(panel.c[exit_, j] / panel.o[entry, j] - 1.0)
        base_event_avg = float(np.mean(event_returns)) if event_returns else np.nan
        for cost_name, buy_cost, sell_cost in _costs(panel):
            daily, stats = _simulate(panel, sig, cfg, d0, buy_cost, sell_cost)
            row = {"market": market, **asdict(cfg), "cost_case": cost_name,
                   "signal_count": signal_count, "event_count": len(event_returns),
                   "event_average_return": base_event_avg, **stats}
            for window, (a, b) in {
                "full": (d0, len(panel.dates)),
                "is": (d0, d0 + int((len(panel.dates)-d0)*.60)),
                "oos": (d0 + int((len(panel.dates)-d0)*.60), len(panel.dates)),
                "w22": (max(d0, int(panel.dates.searchsorted(pd.Timestamp("2022-01-03")))), len(panel.dates)),
            }.items():
                row.update({f"{window}_{k}": v for k, v in _metrics(daily, panel.dates, a, b).items()})
            rows.append(row)
        configs.append(asdict(cfg))
    return {"market": market, "dates": [str(panel.dates[d0].date()), str(panel.dates[-1].date())],
            "symbols": len(panel.symbols), "source": "volume_spike_signal_core.find_signals + portfolio RoundConfig R01-R16",
            "fills": "signal at prior close, fill next open; exit at close after hold_days sessions; slot free next session",
            "circuit_timing": "opening mark only; close threshold state affects next session, never uses same-day close for open order",
            "cost_cases": [x[0] for x in _costs(panel)], "configs": configs,
            "rows": rows, "row_count": len(rows)}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
              "round_count": len(ROUNDS), "markets": {m: evaluate_market(m) for m in ("US", "KR")}}
    out = OUTPUT / "volume_portfolio_transfer.json"
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({m: v["row_count"] for m, v in result["markets"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
