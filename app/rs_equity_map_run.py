"""Run the 1d crypto-family registry on US/KR equities with stock execution rules.

This deliberately does not fabricate 4h equity bars. The registry's 1d grid is
the complete tested universe for the local daily datasets. Output is chunked by
family group to gzip CSV plus an audit/summary JSON.
"""
from __future__ import annotations

import gzip
import itertools
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numba import njit

from app.rs_equity_transfer import EquityPanel, evaluate_family_signal, load_equity_panel


REBALANCES = (1, 2, 3, 7)
K_VALUES = (4, 6, 8, 10, 12)
VOL_TARGET = 0.20
LEV_CAP = 1.5
COMM_KR = 0.00015
TAX_KR = 0.0018
BORROW_YR = {"US": 0.01, "KR": 0.03}
START_DATE = "2019-01-01"
OUTPUT = Path(__file__).resolve().parents[1] / "docs/research/equity_transfer_2026-10/full_runs"
CHUNK_UNITS = 25


@njit(cache=False)
def _sim_one_phase(
    close: np.ndarray, open_: np.ndarray, target: np.ndarray, flat: np.ndarray,
    tradable: np.ndarray, slip: np.ndarray, market_code: int, cadence: int,
    phase: int, fee: float, slip_mult: float, borrow: float, vt: float,
    d0: int,
) -> np.ndarray:
    """Daily close equity returns; signal at close t is filled at t+1 close/open."""
    nday, nsym = close.shape
    values = np.zeros(nsym, dtype=np.float64)
    cash = 1.0
    eq = np.ones(nday, dtype=np.float64)
    daily = np.zeros(nday, dtype=np.float64)
    last_signal = d0 + phase - cadence
    prev_flat = False

    for t in range(d0 + 1, nday):
        # Existing holdings earn overnight and intraday returns before the new
        # next-open target in Korea, and close-to-close returns before next-close
        # target in the US.
        if market_code == 0:
            for j in range(nsym):
                if values[j] != 0.0 and np.isfinite(close[t, j]) and np.isfinite(close[t - 1, j]) and close[t - 1, j] != 0:
                    values[j] *= close[t, j] / close[t - 1, j]
        else:
            for j in range(nsym):
                if values[j] != 0.0 and np.isfinite(open_[t, j]) and np.isfinite(close[t - 1, j]) and close[t - 1, j] != 0:
                    values[j] *= open_[t, j] / close[t - 1, j]

        sig = t - 1
        if sig >= d0:
            now_flat = flat[sig]
            force = now_flat != prev_flat
            due = sig >= d0 + phase and sig - last_signal >= cadence
            if due or force:
                equity = cash
                for j in range(nsym):
                    equity += values[j]
                lev = 1.0
                if vt > 0.0 and sig - d0 + 1 >= 30:
                    lo = max(d0, sig - 59)
                    mean = 0.0
                    for q in range(lo, sig + 1):
                        mean += daily[q]
                    count = sig - lo + 1
                    mean /= count
                    var = 0.0
                    for q in range(lo, sig + 1):
                        diff = daily[q] - mean
                        var += diff * diff
                    vol = np.sqrt(var / count) * np.sqrt(252.0)
                    if vol > 1e-12:
                        lev = min(LEV_CAP, vt / vol)
                    else:
                        lev = LEV_CAP

                cost = 0.0
                sum_delta = 0.0
                for j in range(nsym):
                    delta = 0.0
                    if tradable[t, j]:
                        wanted = target[sig, j] * lev * equity
                        delta = wanted - values[j]
                    if market_code == 0:
                        cost += abs(delta) * fee
                    elif delta > 0.0:
                        cost += delta * (COMM_KR + slip[j] * slip_mult)
                    elif delta < 0.0:
                        cost += -delta * (COMM_KR + TAX_KR + slip[j] * slip_mult)
                    values[j] += delta
                    sum_delta += delta
                cash -= sum_delta + cost
                if due:
                    last_signal = sig
                prev_flat = now_flat

        if market_code == 1:
            for j in range(nsym):
                if values[j] != 0.0 and np.isfinite(close[t, j]) and np.isfinite(open_[t, j]) and open_[t, j] != 0:
                    values[j] *= close[t, j] / open_[t, j]

        if borrow > 0.0:
            short_value = 0.0
            for j in range(nsym):
                if values[j] < 0.0:
                    short_value -= values[j]
            cash -= short_value * borrow / 252.0

        equity_close = cash
        for j in range(nsym):
            equity_close += values[j]
        eq[t] = equity_close
        daily[t] = equity_close / eq[t - 1] - 1.0 if eq[t - 1] > 0.0 else -1.0
    return daily


@njit(cache=False)
def _simulate(target: np.ndarray, flat: np.ndarray, close: np.ndarray,
              open_: np.ndarray, tradable: np.ndarray, slip: np.ndarray,
              market_code: int, cadence: int, fee: float, slip_mult: float,
              borrow: float, vt: float, d0: int) -> np.ndarray:
    """Average daily return stream over every rebalance phase."""
    nday = close.shape[0]
    total = np.zeros(nday, dtype=np.float64)
    count = np.zeros(nday, dtype=np.int64)
    for phase in range(cadence):
        daily = _sim_one_phase(close, open_, target, flat, tradable, slip,
                               market_code, cadence, phase, fee, slip_mult,
                               borrow, vt, d0)
        for t in range(d0, nday):
            total[t] += daily[t]
            count[t] += 1
    out = np.zeros(nday, dtype=np.float64)
    for t in range(d0, nday):
        out[t] = total[t] / max(count[t], 1)
    return out


def _rank_z(matrix: np.ndarray) -> np.ndarray:
    valid = np.isfinite(matrix)
    ranks = pd.DataFrame(matrix).rank(axis=1).to_numpy()
    counts = valid.sum(axis=1, keepdims=True)
    result = (ranks - (counts + 1.0) / 2.0) / np.sqrt(np.maximum((counts * counts - 1.0) / 12.0, 1.0))
    result[~valid] = np.nan
    return result


def _vol20(close: np.ndarray) -> np.ndarray:
    returns = np.full_like(close, np.nan, dtype=float)
    returns[1:] = close[1:] / close[:-1] - 1.0
    return pd.DataFrame(returns).rolling(20, min_periods=15).std().to_numpy()


def _active_weights(panel: EquityPanel, pos: np.ndarray, strength: np.ndarray,
                    vol: np.ndarray, kind: str, k: int = 0,
                    ivol: bool = False, mode: str = "") -> tuple[np.ndarray, np.ndarray]:
    nday, nsym = panel.c.shape
    active = np.isfinite(pos) & np.isfinite(panel.c) & panel.eligible
    on = active & (pos > 0.0)
    flat = np.zeros(nday, dtype=bool)
    if kind == "LO_EW":
        denom = np.maximum(active.sum(axis=1, keepdims=True), 1)
        if ivol:
            inv = np.full(vol.shape, np.nan, dtype=float)
            np.divide(1.0, vol, out=inv, where=active & np.isfinite(vol) & (vol > 0.0))
            count = np.isfinite(inv).sum(axis=1, keepdims=True)
            mean_inv = np.divide(np.nansum(inv, axis=1, keepdims=True), count,
                                 out=np.ones((nday, 1), dtype=float), where=count > 0)
            weights = np.where(on, np.nan_to_num(inv / mean_inv, nan=1.0), 0.0) / denom
            gross = weights.sum(axis=1, keepdims=True)
            weights /= np.maximum(gross, 1.0)
        else:
            weights = on / denom
        return weights.astype(float), flat

    if kind == "LO_TOPN":
        valid = active & np.isfinite(strength)
        candidates = valid & on
        weights = np.zeros((nday, nsym), dtype=float)
        order = np.argsort(-np.where(candidates, strength, -np.inf), axis=1, kind="stable")
        for t in range(nday):
            selected = [j for j in order[t] if candidates[t, j]][:k]
            if ivol and selected:
                iv = np.array([1.0 / vol[t, j] if np.isfinite(vol[t, j]) and vol[t, j] > 0 else 0.0 for j in selected])
                total = iv.sum()
                if total > 0:
                    for j, value in zip(selected, iv):
                        weights[t, j] = value / total * len(selected) / k
            else:
                for j in selected:
                    weights[t, j] = 1.0 / k
        sma = pd.Series(panel.proxy_close).rolling(200, min_periods=200).mean().to_numpy()
        gate = np.isfinite(sma) & (panel.proxy_close > sma)
        weights *= gate[:, None]
        return weights, flat

    if kind == "LS":
        valid = active & np.isfinite(strength)
        weights = np.zeros((nday, nsym), dtype=float)
        order = np.argsort(-np.where(valid, strength, -np.inf), axis=1, kind="stable")
        for t in range(nday):
            eligible = int(valid[t].sum())
            if eligible < 2 * k:
                continue
            for j in order[t, :k]:
                weights[t, j] = 1.0 / (2 * k)
            for j in order[t, -k:]:
                weights[t, j] = -1.0 / (2 * k)
        return weights, flat

    if kind == "OVL":
        ret14 = np.full_like(panel.c, np.nan, dtype=float)
        ret14[14:] = panel.c[14:] / panel.c[:-14] - 1.0
        base = _rank_z(ret14)
        if mode.startswith("tilt"):
            score = base + float(mode[4:]) * np.nan_to_num(_rank_z(strength), nan=0.0)
        elif mode == "agree":
            score = base + 10.0 * np.sign(np.nan_to_num(pos, nan=0.0))
        elif mode == "gate":
            score = base.copy()
        else:
            raise ValueError(mode)
        score[~np.isfinite(base)] = np.nan
        crashret = np.full(nday, np.nan)
        crashret[14:] = panel.proxy_close[14:] / panel.proxy_close[:-14] - 1.0
        flat = np.isfinite(crashret) & (crashret < -0.10)
        valid = np.isfinite(score) & panel.eligible
        weights = np.zeros((nday, nsym), dtype=float)
        order = np.argsort(-np.where(valid, score, -np.inf), axis=1, kind="stable")
        for t in range(nday):
            selected = [j for j in order[t] if valid[t, j]][:8]
            for j in selected:
                weights[t, j] = 1.0 / 8.0
        weights[flat] = 0.0
        return weights, flat
    raise ValueError(f"unknown construction {kind}")


def _metrics(returns: np.ndarray, dates: pd.DatetimeIndex,
             start: int, end: int) -> dict[str, float]:
    r = np.asarray(returns[start:end], dtype=float)
    if len(r) < 30:
        return {"cagr": np.nan, "mdd": np.nan, "calmar": np.nan, "sharpe": np.nan}
    growth = np.cumprod(1.0 + r)
    years = max((dates[end - 1] - dates[start]).days / 365.25, 1.0 / 365.25)
    cagr = growth[-1] ** (1.0 / years) - 1.0 if growth[-1] > 0 else -1.0
    high = np.maximum.accumulate(np.r_[1.0, growth])[1:]
    mdd = float(np.max(1.0 - growth / high))
    std = float(r.std())
    sharpe = float(r.mean() / std * np.sqrt(252.0)) if std > 0 else 0.0
    return {"cagr": float(cagr), "mdd": mdd,
            "calmar": float(cagr / mdd) if mdd > 1e-12 else 0.0,
            "sharpe": sharpe}


def _windows(panel: EquityPanel, d0: int) -> dict[str, tuple[int, int]]:
    n = len(panel.dates) - d0
    cut = d0 + int(n * 0.60)
    third = (n // 3)
    w22 = int(panel.dates.searchsorted(pd.Timestamp("2022-01-03")))
    return {
        "FULL": (d0, len(panel.dates)),
        "IS": (d0, cut),
        "OOS": (cut, len(panel.dates)),
        "W22": (max(d0, w22), len(panel.dates)),
        "F1": (d0, d0 + third),
        "F2": (d0 + third, d0 + 2 * third),
        "F3": (d0 + 2 * third, len(panel.dates)),
    }


def _configurations() -> list[dict[str, Any]]:
    configs = []
    for k, cadence in itertools.product(K_VALUES, REBALANCES):
        configs.append({"construction": "LS", "K": k, "cadence": cadence, "weight": "ew", "mode": ""})
    for ivol, cadence in itertools.product((False, True), REBALANCES):
        configs.append({"construction": "LO_EW", "K": 0, "cadence": cadence,
                        "weight": "ivol" if ivol else "ew", "mode": ""})
    for k, ivol, cadence in itertools.product(K_VALUES, (False, True), REBALANCES):
        configs.append({"construction": "LO_TOPN", "K": k, "cadence": cadence,
                        "weight": "ivol" if ivol else "ew", "mode": ""})
    for mode in ("tilt0.5", "tilt1.0", "agree", "gate"):
        configs.append({"construction": "OVL", "K": 8, "cadence": 3, "weight": "-", "mode": mode})
    if len(configs) != 72:
        raise AssertionError(f"strategy construction grid changed: {len(configs)}")
    return configs


def _cost_cases(market: str) -> list[tuple[str, float, float]]:
    if market == "US":
        return [("KIS_0.36pct", 0.0036, 1.0), ("low_0.08pct", 0.0008, 1.0)]
    return [("KR_base", 0.0, 1.0), ("KR_2x_slippage", 0.0, 2.0)]


def _family_params(registry: dict[str, Any]):
    from app.rs_map_off_run import grid_points

    for family_name, family in registry.items():
        for params in grid_points(family):
            yield family_name, family, params


def _evaluate_market(market: str, registry: dict[str, Any], limit_units: int | None = None) -> dict[str, Any]:
    panel = load_equity_panel(market)
    d0 = int(panel.dates.searchsorted(pd.Timestamp(START_DATE)))
    if d0 >= len(panel.dates) - 100:
        raise RuntimeError(f"insufficient data after {START_DATE} for {market}")
    windows = _windows(panel, d0)
    configurations = _configurations()
    cost_cases = _cost_cases(market)
    vol = _vol20(panel.c)
    market_code = 0 if market == "US" else 1
    out_dir = OUTPUT
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / f"{market}_meta.json").exists():
        raise FileExistsError(f"completed market artifact already exists: {out_dir / f'{market}_meta.json'}")
    summaries: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    n_units = 0
    t0 = time.monotonic()
    prior_chunks = sorted(out_dir.glob(f"{market}_[abc]_daily_cases_*.csv.gz"))
    done_units: set[tuple[str, str]] = set()
    for old in prior_chunks:
        old_df = pd.read_csv(old, usecols=["family", "params"])
        done_units.update((str(f), str(p)) for f, p in old_df.drop_duplicates().itertuples(index=False, name=None))
    n_rows = len(done_units) * len(configurations) * len(cost_cases) * 2
    chunk_no = {
        group: 1 + max((int(p.name.rsplit("_", 1)[1].split(".")[0])
                        for p in prior_chunks if f"_{group.lower()}_" in p.name), default=-1)
        for group in "ABC"
    }
    chunk_units = {group: 0 for group in "ABC"}
    chunk_rows: dict[str, list[pd.DataFrame]] = {group: [] for group in "ABC"}
    chunk_manifest: list[str] = []

    def flush(group: str) -> None:
        if not chunk_rows[group]:
            return
        path = out_dir / f"{market}_{group.lower()}_daily_cases_{chunk_no[group]:04d}.csv.gz"
        if path.exists():
            raise FileExistsError(f"refusing to overwrite prior artifact: {path}")
        tmp = path.with_suffix(path.suffix + ".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8", newline="") as stream:
            pd.concat(chunk_rows[group], ignore_index=True).to_csv(stream, index=False)
        tmp.replace(path)
        done_units.update(
            (str(f), str(p))
            for frame in chunk_rows[group]
            for f, p in frame[["family", "params"]].drop_duplicates().itertuples(index=False, name=None)
        )
        chunk_manifest.append(str(path))
        chunk_no[group] += 1
        chunk_units[group] = 0
        chunk_rows[group].clear()

    if prior_chunks:
        print(f"{market} resume: {len(done_units)} committed family/parameter units in {len(prior_chunks)} chunks", flush=True)
    try:
        for family_name, family, params in _family_params(registry):
            if family["tfs"].count("1d") == 0:
                continue
            unit_key = (family_name, json.dumps(params, sort_keys=True, separators=(",", ":")))
            if unit_key in done_units:
                continue
            try:
                pos, strength, proxy_pos = evaluate_family_signal(panel, family, "1d", params)
            except Exception as exc:
                failures.append({"family": family_name, "params": params,
                                 "error": f"{type(exc).__name__}: {exc}"[:300]})
                continue
            n_units += 1
            active_weights: dict[tuple[str, int, str, str], tuple[np.ndarray, np.ndarray]] = {}
            for cfg in configurations:
                key = (cfg["construction"], cfg["K"], cfg["weight"], cfg["mode"])
                if key not in active_weights:
                    if cfg["construction"] == "OVL" and cfg["mode"] == "gate":
                        weights, flat = _active_weights(panel, pos, strength, vol,
                                                        cfg["construction"], cfg["K"],
                                                        cfg["weight"] == "ivol", cfg["mode"])
                        flat |= ~np.isfinite(proxy_pos) | (proxy_pos <= 0.0)
                        weights[flat] = 0.0
                    else:
                        weights, flat = _active_weights(panel, pos, strength, vol,
                                                        cfg["construction"], cfg["K"],
                                                        cfg["weight"] == "ivol", cfg["mode"])
                    active_weights[key] = (weights, flat)
            rows = []
            for cfg in configurations:
                key = (cfg["construction"], cfg["K"], cfg["weight"], cfg["mode"])
                weights, flat = active_weights[key]
                for cost_name, fee, slip_mult in cost_cases:
                    for size_name, vt in (("x1", 0.0), ("vt20_cap1.5", VOL_TARGET)):
                        daily = _simulate(weights, flat, panel.c, panel.o, panel.tradable,
                                          panel.slip, market_code, cfg["cadence"], fee,
                                          slip_mult, BORROW_YR[market], vt, d0)
                        row: dict[str, Any] = {
                            "family": family_name,
                            "params": json.dumps(params, sort_keys=True, separators=(",", ":")),
                            **cfg, "cost_case": cost_name, "size_case": size_name,
                            "proxy": "equal_weight_universe",
                        }
                        for name, (a, b) in windows.items():
                            m = _metrics(daily, panel.dates, a, b)
                            row.update({f"{name.lower()}_{metric}": value for metric, value in m.items()})
                        rows.append(row)
                        n_rows += 1
            group = family_name[0].upper()
            if len(rows) != len(configurations) * len(cost_cases) * 2:
                raise AssertionError(f"unexpected row count for {family_name}: {len(rows)}")
            frame = pd.DataFrame(rows)
            chunk_rows[group].append(frame)
            chunk_units[group] += 1
            summaries.append({"family": family_name, "params": params,
                              "signal_nonzero": int(np.count_nonzero(pos > 0)),
                              "case_rows": len(rows)})
            if n_units % 100 == 0:
                print(f"{market} units={n_units} rows={n_rows} failures={len(failures)} elapsed={time.monotonic()-t0:.0f}s", flush=True)
            if chunk_units[group] >= CHUNK_UNITS:
                flush(group)
            if limit_units is not None and n_units >= limit_units:
                break
    finally:
        for group in "ABC":
            flush(group)

    meta = {
        "market": market,
        "dates": [str(panel.dates[d0].date()), str(panel.dates[-1].date())],
        "symbols": len(panel.symbols),
        "family_count": len(registry),
        "grid_units_evaluated_this_run": n_units,
        "grid_units_committed_total": len(done_units),
        "grid_units_expected_1d": sum(1 for _ in _family_params(registry)),
        "constructions_per_unit": len(configurations),
        "cost_cases": [x[0] for x in cost_cases],
        "sizing_cases": ["x1", "vt20_cap1.5"],
        "case_rows": n_rows,
        "failures": failures,
        "windows": {k: [str(panel.dates[a].date()), str(panel.dates[b - 1].date())]
                    for k, (a, b) in windows.items()},
        "source": "1d family registry; no synthesized intraday bars",
        "elapsed_seconds": time.monotonic() - t0,
        "result_chunks": [str(p) for p in sorted(out_dir.glob(f"{market}_[abc]_daily_cases_*.csv.gz"))],
    }
    expected_units = meta["grid_units_expected_1d"]
    meta_path = out_dir / (f"{market}_meta.json" if len(done_units) >= expected_units else f"{market}_progress.json")
    tmp_meta = meta_path.with_suffix(meta_path.suffix + ".tmp")
    tmp_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_meta.replace(meta_path)
    return meta


def main() -> None:
    # Existing family/crypto modules have Numba cache=True decorators. Disable
    # only disk caching before import; compiled kernels remain enabled in-memory.
    import numba
    original_njit = numba.njit
    def no_disk_cache(*args: Any, **kwargs: Any):
        kwargs.pop("cache", None)
        return original_njit(*args, cache=False, **kwargs)
    numba.njit = no_disk_cache
    from app.rs_map_off_run import registry
    reg = registry()
    if len(reg) != 98:
        raise RuntimeError(f"expected 98 registered families, found {len(reg)}")
    args = sys.argv[1:]
    if args and args[0].isdigit():
        max_units = int(args[0])
        markets = args[1:] or ["US", "KR"]
    else:
        max_units = None
        markets = args or ["US", "KR"]
    print(f"families={len(reg)} 1d_units={sum(1 for _ in _family_params(reg))} cases_per_unit={72*2*2}", flush=True)
    for market in markets:
        print(json.dumps(_evaluate_market(market, reg, max_units), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
