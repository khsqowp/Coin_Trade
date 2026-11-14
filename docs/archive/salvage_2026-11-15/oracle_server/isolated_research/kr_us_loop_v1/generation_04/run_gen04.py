"""Generation 04 TEMA/CLV exploratory screen; local data only."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PREREG = HERE / "PREREG.md"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


g1 = _load("gen01_runner", ROOT / "generation_01" / "run_gen01.py")
g3 = _load("gen03_runner", ROOT / "generation_03" / "run_gen03.py")
NAMES = ["TEMA9_21_MONTHLY_SLOPE", "CLV_HIGH_CLOSE_5D"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def log_event(path: Path, event: dict) -> None:
    row = {"ts_utc": pd.Timestamp.now(tz="UTC").isoformat(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, allow_nan=False, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


def tema_series(close: pd.Series, length: int) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Recursive EMA/TEMA, alpha=2/(n+1), first observation seeds each valid segment."""
    values = close.to_numpy(float)
    e1 = np.full(len(values), np.nan)
    e2 = np.full(len(values), np.nan)
    e3 = np.full(len(values), np.nan)
    alpha = 2.0 / (length + 1.0)
    for i, value in enumerate(values):
        if not np.isfinite(value) or value <= 0:
            continue
        if i == 0 or not np.isfinite(values[i - 1]) or values[i - 1] <= 0:
            e1[i] = e2[i] = e3[i] = value
        else:
            e1[i] = alpha * value + (1.0 - alpha) * e1[i - 1]
            e2[i] = alpha * e1[i] + (1.0 - alpha) * e2[i - 1]
            e3[i] = alpha * e2[i] + (1.0 - alpha) * e3[i - 1]
    tema = 3.0 * e1 - 3.0 * e2 + e3
    index = close.index
    return tuple(pd.Series(x, index=index) for x in (e1, e2, e3, tema))


def _consecutive_atr(data: dict, period: int = 14) -> tuple[pd.DataFrame, pd.DataFrame]:
    O, H, L, C = (data[k].astype(float) for k in ("O", "H", "L", "C"))
    atr = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    run = pd.DataFrame(0, index=C.index, columns=C.columns, dtype=np.int32)
    for col in C.columns:
        o, h, l, c = (frame[col].to_numpy(float) for frame in (O, H, L, C))
        valid = (np.isfinite(o) & np.isfinite(h) & np.isfinite(l) & np.isfinite(c) &
                 (o > 0) & (h > 0) & (l > 0) & (c > 0) &
                 (h >= np.maximum(o, c)) & (l <= np.minimum(o, c)) & (h >= l))
        starts = np.flatnonzero(valid & ~np.r_[False, valid[:-1]])
        ends = np.flatnonzero(valid & ~np.r_[valid[1:], False]) + 1
        for start, end in zip(starts, ends):
            run.iloc[start:end, run.columns.get_loc(col)] = np.arange(1, end - start + 1, dtype=np.int32)
            prev = np.r_[np.nan, c[start:end - 1]]
            tr = np.maximum.reduce((h[start:end] - l[start:end],
                                    np.abs(h[start:end] - prev),
                                    np.abs(l[start:end] - prev)))
            atr.iloc[start:end, atr.columns.get_loc(col)] = pd.Series(tr).rolling(period, min_periods=period).mean().to_numpy()
    return atr, run


def clv_event_targets(data: dict, event: pd.DataFrame, rank_score: pd.DataFrame) -> np.ndarray:
    """Fixed five-session lots; rejected overflow events are not queued for late entry."""
    ev, score = event.fillna(False).to_numpy(bool), rank_score.to_numpy(float)
    t, n = ev.shape
    out = np.zeros((t, n), dtype=np.float32)
    active: dict[int, tuple[int, float]] = {}
    for i in range(t):
        for j in [j for j, (end, _) in active.items() if end < i]:
            del active[j]
        free = max(int(data["k"]) - len(active), 0)
        candidates = np.array([int(j) for j in np.flatnonzero(ev[i])
                               if int(j) not in active and np.isfinite(score[i, j])], dtype=int)
        if free and len(candidates):
            order = np.lexsort((candidates, -score[i, candidates]))
            for j in candidates[order[:free]]:
                active[int(j)] = (i + 4, float(score[i, j]))
        choices = np.array(sorted(active), dtype=int)
        if len(choices) > int(data["k"]):
            values = np.array([active[int(j)][1] for j in choices])
            choices = choices[np.lexsort((choices, -values))[:int(data["k"])]]
        if len(choices):
            out[i, choices] = 1.0 / len(choices)
    return out


def simulate_gen04_strict(data: dict, desired_at_close: np.ndarray) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Gen03 execution math plus full OHLC validation on every held/new position."""
    O, H, L, C = (data[k].to_numpy(float) for k in ("O", "H", "L", "C"))
    T, N = C.shape
    desired = np.vstack([np.zeros((1, N)), desired_at_close[:-1]])
    returns = np.zeros(T, dtype=float)
    turnover = np.zeros(T, dtype=float)
    exposure = np.zeros(T, dtype=float)
    prev_w = np.zeros(N, dtype=float)
    symbols = list(data["C"].columns)
    for i in range(1, T):
        prev_close, open_i, high_i, low_i, close_i = C[i - 1], O[i], H[i], L[i], C[i]
        valid_bar = (np.isfinite(open_i) & np.isfinite(high_i) & np.isfinite(low_i) & np.isfinite(close_i) &
                     (open_i > 0) & (high_i > 0) & (low_i > 0) & (close_i > 0) &
                     (high_i >= np.maximum(open_i, close_i)) &
                     (low_i <= np.minimum(open_i, close_i)) & (high_i >= low_i))
        bad_held = (prev_w > 1e-8) & (~valid_bar | ~np.isfinite(prev_close) | (prev_close <= 0))
        target = desired[i].astype(float, copy=True)
        bad_entry = (target > 1e-8) & ~valid_bar
        bad = bad_held | bad_entry
        if bad.any():
            j = int(np.flatnonzero(bad)[0])
            reason = "held position has an invalid or missing OHLC bar" if bad_held[j] else "entry target has an invalid or missing OHLC bar"
            raise ValueError(f"strict OHLC integrity failure on {data['cal'][i].date()} {symbols[j]}: {reason}")
        valid_gap = np.isfinite(open_i) & (open_i > 0) & np.isfinite(prev_close) & (prev_close > 0)
        gap = np.zeros(N, dtype=float)
        gap[valid_gap] = open_i[valid_gap] / prev_close[valid_gap] - 1.0
        overnight = float(np.dot(prev_w, gap))
        post_gap = prev_w * (1.0 + gap) / max(1.0 + overnight, 1e-12)
        total = target.sum()
        if total > 1.0:
            target /= total
        sells = np.maximum(post_gap - target, 0).sum()
        buys = np.maximum(target - post_gap, 0).sum()
        turnover[i] = sells + buys
        fees = buys * data["fee_buy"] + sells * data["fee_sell"]
        intraday = np.zeros(N, dtype=float)
        intraday[valid_bar] = close_i[valid_bar] / open_i[valid_bar] - 1.0
        portfolio_intraday = float(np.dot(target, intraday))
        returns[i] = (1.0 + overnight) * (1.0 - fees) * (1.0 + portfolio_intraday) - 1.0
        exposure[i] = target.sum()
        prev_w = target * (1.0 + intraday) / max(1.0 + portfolio_intraday, 1e-12)
        prev_w = np.maximum(prev_w, 0.0)
        if prev_w.sum() > 1.0:
            prev_w /= prev_w.sum()
    return (pd.Series(returns, index=data["cal"]), pd.Series(turnover, index=data["cal"]),
            pd.Series(exposure, index=data["cal"]))


def market_snapshot_hash(market: str, data: dict) -> dict:
    folder = g1.DATA / "kr_daily_v2" / "data" if market == "KR" else g1.DATA / "us_daily"
    if market == "KR":
        paths = [folder / "005930.parquet", g1.DATA / "kr_daily_v2" / "universe" / "universe_raw.csv"]
        paths += [folder / f"{symbol}.parquet" for symbol in data["C"].columns]
    else:
        paths = [folder / "SPY.parquet", folder / "pit" / "sp500_ticker_start_end.csv"]
        for symbol in data["C"].columns:
            paths.append(folder / f"{symbol}.parquet")
            meta = folder / f"{symbol}.meta.json"
            if meta.exists():
                paths.append(meta)
    h = hashlib.sha256()
    files = []
    for path in sorted(set(paths)):
        if not path.is_file():
            raise FileNotFoundError(f"snapshot input disappeared: {path}")
        digest = sha256(path)
        rel = str(path.relative_to(g1.DATA))
        h.update(f"{rel}\0{digest}\n".encode())
        files.append(rel)
    return {"sha256": h.hexdigest(), "files": len(files), "scope": "files actually used plus universe/calendar inputs"}


def candidate_targets(data: dict, name: str, month_days: np.ndarray) -> np.ndarray:
    C, H, L = (data[k].astype(float) for k in ("C", "H", "L"))
    if name == "TEMA9_21_MONTHLY_SLOPE":
        atr14, valid_run = _consecutive_atr(data, 14)
        t9 = pd.DataFrame(index=C.index, columns=C.columns, dtype=float)
        t21 = t9.copy()
        for col in C.columns:
            segmented_close = C[col].where(valid_run[col] > 0)
            t9[col] = tema_series(segmented_close, 9)[3]
            t21[col] = tema_series(segmented_close, 21)[3]
        slope = t21 / t21.shift(21) - 1.0
        feature_ready = (valid_run >= 200) & atr14.notna() & slope.notna()
        entry = (t9 > t21) & (C > t21) & (slope > 0) & feature_ready
        exit_ = (~((t9 > t21) & (C > t21) & (slope > 0))) | ~feature_ready
        state = g3.monthly_stateful(entry, exit_, month_days)
        score = (slope / (atr14 / C)).where(feature_ready)
        return g1.make_target(data["eligible"], state & data["eligible"], score, int(data["k"]), month_days)
    if name == "CLV_HIGH_CLOSE_5D":
        O = data["O"].astype(float)
        valid = ((O > 0) & (C > 0) & (H > 0) & (L > 0) & (H > L) &
                 (H >= np.maximum(O, C)) & (L <= np.minimum(O, C)))
        clv = ((C - L) - (H - C)) / (H - L).where(H > L)
        event = (clv > 0.8) & valid & data["eligible"]
        return clv_event_targets(data, event, clv)
    raise KeyError(name)


def main() -> int:
    started = pd.Timestamp.now(tz="UTC")
    run_id = f"GEN04-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ledger = HERE / f"attempts_{run_id}.jsonl"
    curves_path = HERE / f"equity_curves_{run_id}.csv.gz"
    manifest_path = HERE / f"manifest_{run_id}.json"
    addenda = {p.name: sha256(p) for p in sorted(HERE.glob("ADDENDUM_A*.md"))}
    manifest = {"run_id": run_id, "prereg_sha256": sha256(PREREG), "addenda_sha256": addenda,
                "runner_sha256": sha256(Path(__file__)),
                "gen01_runner_sha256": sha256(ROOT / "generation_01" / "run_gen01.py"),
                "gen03_runner_sha256": sha256(ROOT / "generation_03" / "run_gen03.py"),
                "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
                "started_utc": started.isoformat(), "data_root": str(g1.DATA), "attempts_file": str(ledger),
                "planned_attempts": len(NAMES) * 2, "status": "RUNNING",
                "evidence_status": "EXPLORATORY_ONLY_HISTORIC_WINDOWS_AND_TRIALS_UNRESOLVED"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    curves: list[dict] = []
    counter = 0
    for market in ("US", "KR"):
        try:
            data = g1.load_market(market)
            snapshot_hash = market_snapshot_hash(market, data)
            months = g1.month_ends(data["cal"])
            br, btv, bex = g1.benchmark_returns(data)
            bm = g3.metric_for(br, btv, bex, market, months)
            if bm["IS"].get("status") != "OK":
                raise ValueError(f"invalid benchmark IS metrics: {bm['IS']}")
        except Exception as exc:
            for j, name in enumerate(NAMES, 1):
                aid = f"{run_id}-{market}-{j:02d}-{name}"
                log_event(ledger, {"event": "attempt_fail", "attempt_id": aid, "market": market,
                                   "candidate": name, "status": "FAILED", "stage": "market_setup_or_benchmark",
                                   "error_type": type(exc).__name__, "error": str(exc),
                                   "traceback": traceback.format_exc(limit=8),
                                   "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
            continue
        manifest.setdefault("markets", {})[market] = {"sessions": len(data["cal"]), "symbols": len(data["C"].columns),
                                                        "benchmark": bm, "data_note": data["data_note"],
                                                        "input_snapshot": snapshot_hash}
        for name in NAMES:
            counter += 1
            aid = f"{run_id}-{market}-{counter:02d}-{name}"
            log_event(ledger, {"event": "attempt_start", "attempt_id": aid, "market": market, "candidate": name,
                               "status": "STARTED", "prereg_sha256": manifest["prereg_sha256"],
                               "runner_sha256": manifest["runner_sha256"], "planned_new_tests_in_generation": 4})
            start = time.monotonic()
            try:
                weights = candidate_targets(data, name, months)
                returns, turnover, exposure = simulate_gen04_strict(data, weights)
                result = {"event": "attempt_finish", "attempt_id": aid, "market": market, "candidate": name,
                          "status": "COMPLETED_EXPLORATORY", "data_note": data["data_note"], "benchmark": bm,
                          "strategy": g3.metric_for(returns, turnover, exposure, market, months),
                          "runtime_seconds": round(time.monotonic() - start, 3),
                          "nonconfirmatory_reason": "source family previously screened; historical windows inspected; PIT and cumulative trial reconciliation unresolved"}
                for date, value in returns.items():
                    curves.append({"attempt_id": aid, "market": market, "candidate": name, "date": date.date().isoformat(),
                                   "daily_return_net": float(value), "turnover": float(turnover.loc[date]),
                                   "exposure": float(exposure.loc[date])})
                log_event(ledger, result)
                print(f"{aid}: {json.dumps(result['strategy'], ensure_ascii=False, allow_nan=False)}", flush=True)
            except Exception as exc:
                log_event(ledger, {"event": "attempt_fail", "attempt_id": aid, "market": market,
                                   "candidate": name, "status": "FAILED", "stage": "candidate_execution",
                                   "error_type": type(exc).__name__, "error": str(exc),
                                   "traceback": traceback.format_exc(limit=8),
                                   "runtime_seconds": round(time.monotonic() - start, 3),
                                   "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
        del data
    if curves:
        pd.DataFrame(curves).to_csv(curves_path, index=False, compression="gzip")
    manifest["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    manifest["attempt_events_sha256"] = sha256(ledger) if ledger.exists() else None
    manifest["attempt_events"] = sum(1 for _ in ledger.open(encoding="utf-8")) if ledger.exists() else 0
    manifest["curve_file"] = str(curves_path) if curves else None
    if curves:
        manifest["curve_file_sha256"] = sha256(curves_path)
    manifest["status"] = "FINISHED"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
