"""Generation 02 exploratory hypotheses; local-only, immutable per-run artifacts."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
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
SPEC = importlib.util.spec_from_file_location("gen01_runner", ROOT / "generation_01" / "run_gen01.py")
g1 = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(g1)
NAMES = ["TS63_KENDALL", "OLS_MULTI_3OF4", "SIGN_FLIP63", "KALMAN_DRIFT63", "EHLERS_SSF40_SLOPE5", "BREADTH_60_40_BASKET"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def log_event(path: Path, event: dict) -> None:
    row = {"ts_utc": pd.Timestamp.now(tz="UTC").isoformat(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def monthly_stateful(entry: pd.DataFrame, exit_: pd.DataFrame, month_days: np.ndarray) -> pd.DataFrame:
    """State can change only at a registered month-end close."""
    e, x = entry.fillna(False).to_numpy(bool), exit_.fillna(False).to_numpy(bool)
    out = np.zeros(e.shape, dtype=bool)
    active = np.zeros(e.shape[1], dtype=bool)
    for t in month_days:
        active = (active & ~x[t]) | (e[t] & ~x[t])
        out[t] = active
    return pd.DataFrame(out, index=entry.index, columns=entry.columns)


def candidate_targets(data: dict, name: str, month_days: np.ndarray) -> np.ndarray:
    C = data["C"].astype(float)
    elig, k = data["eligible"], data["k"]
    close = C.to_numpy(float)
    logc = np.log(C.where(C > 0))
    daily_logret = np.log(C / C.shift(1))
    cond = pd.DataFrame(False, index=C.index, columns=C.columns)
    score = pd.DataFrame(np.nan, index=C.index, columns=C.columns)

    if name == "TS63_KENDALL":
        lo, hi = np.triu_indices(63, k=1)
        lag = (hi - lo).astype(float)
        for t in month_days:
            if t < 62:
                continue
            window = logc.iloc[t - 62:t + 1].to_numpy(float)
            valid = np.isfinite(window).all(axis=0)
            if not valid.any():
                continue
            pairs = window[hi][:, valid] - window[lo][:, valid]
            slopes = pairs / lag[:, None]
            median_slope = np.median(slopes, axis=0)
            tau_a = np.sign(pairs).mean(axis=0)
            columns = C.columns[valid]
            score.loc[C.index[t], columns] = tau_a
            cond.loc[C.index[t], columns] = (median_slope > 0) & (tau_a >= 0.30)
    elif name == "OLS_MULTI_3OF4":
        slope_frames = [g1.ols_trend(logc, n)[0] for n in (21, 63, 126, 252)]
        positive = [s > 0 for s in slope_frames]
        count = sum(p.astype(int) for p in positive)
        rank_sum = sum(s.rank(axis=1, pct=True).where(p, 0.0) for s, p in zip(slope_frames, positive))
        avg_rank = rank_sum.div(count.replace(0, np.nan))
        cond = count >= 3
        score = count + avg_rank.fillna(0.0)
    elif name == "SIGN_FLIP63":
        signs = np.sign(daily_logret)
        valid_pair = signs.ne(0) & signs.shift(1).ne(0) & signs.notna() & signs.shift(1).notna()
        flips = signs.ne(signs.shift(1)) & valid_pair
        flip_sum = flips.astype(float).rolling(62, min_periods=1).sum()
        pair_count = valid_pair.astype(float).rolling(62, min_periods=1).sum().replace(0, np.nan)
        rate = flip_sum / pair_count
        ret63 = np.exp(daily_logret.rolling(63, min_periods=63).sum()) - 1
        cond = monthly_stateful((ret63 > 0) & (rate <= 0.32), (ret63 <= 0) | (rate >= 0.50), month_days)
        score = ret63 * (1 - rate)
    elif name == "KALMAN_DRIFT63":
        r = daily_logret.to_numpy(float)
        R = daily_logret.rolling(63, min_periods=63).var(ddof=1).to_numpy(float)
        mean63 = daily_logret.rolling(63, min_periods=63).mean().to_numpy(float)
        T, M = r.shape
        mu = np.full((T, M), np.nan)
        P = np.full((T, M), np.nan)
        for t in range(T):
            valid_R = np.isfinite(R[t]) & (R[t] > 0)
            uninitialized = valid_R & ~np.isfinite(mu[t - 1]) if t > 0 else valid_R
            mu[t, uninitialized] = mean63[t, uninitialized]
            P[t, uninitialized] = R[t, uninitialized] / 63.0
            if t == 0:
                continue
            no_variance = np.isfinite(mu[t - 1]) & np.isfinite(P[t - 1]) & ~valid_R
            mu[t, no_variance], P[t, no_variance] = mu[t - 1, no_variance], P[t - 1, no_variance]
            initialized = np.isfinite(mu[t - 1]) & np.isfinite(P[t - 1]) & valid_R
            if not initialized.any():
                continue
            q = R[t, initialized] / (63.0 ** 2)
            pminus = P[t - 1, initialized] + q
            observed = np.isfinite(r[t, initialized])
            mu_t = mu[t - 1, initialized].copy()
            p_t = pminus.copy()
            if observed.any():
                gain = pminus[observed] / (pminus[observed] + R[t, initialized][observed])
                mu_t[observed] += gain * (r[t, initialized][observed] - mu_t[observed])
                p_t[observed] = (1.0 - gain) * pminus[observed]
            mu[t, initialized], P[t, initialized] = mu_t, p_t
        z = pd.DataFrame(mu / np.sqrt(P), index=C.index, columns=C.columns)
        observations = C.notna().cumsum()
        z = z.where(observations >= 126)
        cond = monthly_stateful(z >= 1.0, z <= 0.0, month_days)
        score = z
    elif name == "EHLERS_SSF40_SLOPE5":
        x = logc.to_numpy(float)
        T, M = x.shape
        a = math.exp(-math.sqrt(2.0) * math.pi / 40.0)
        b = 2.0 * a * math.cos(math.sqrt(2.0) * math.pi / 40.0)
        c1, c2, c3 = 1.0 - b + a * a, b, -(a * a)
        filt = np.full_like(x, np.nan)
        run = np.zeros_like(x, dtype=np.int32)
        for t in range(T):
            observed = np.isfinite(x[t])
            run[t] = np.where(observed, (run[t - 1] + 1) if t > 0 else 1, 0)
            initialize = observed & (run[t] <= 2)
            filt[t, initialize] = x[t, initialize]
            if t >= 2:
                ready = observed & (run[t] > 2) & np.isfinite(x[t - 1]) & np.isfinite(filt[t - 1]) & np.isfinite(filt[t - 2])
                filt[t, ready] = c1 * (x[t, ready] + x[t - 1, ready]) / 2 + c2 * filt[t - 1, ready] + c3 * filt[t - 2, ready]
        fm = pd.DataFrame(filt, index=C.index, columns=C.columns)
        slope5 = fm - fm.shift(5)
        vol63 = daily_logret.rolling(63, min_periods=63).std(ddof=1)
        score = slope5 / vol63
        ready = pd.DataFrame(run >= 200, index=C.index, columns=C.columns)
        cond = monthly_stateful((slope5 > 0) & (logc > fm) & ready, ((slope5 <= 0) | (logc < fm)) & ready, month_days)
        score = score.where(ready)
    elif name == "BREADTH_60_40_BASKET":
        sma200 = C.rolling(200, min_periods=200).mean()
        valid = elig & sma200.notna()
        breadth = ((C > sma200) & valid).sum(axis=1).div(valid.sum(axis=1).replace(0, np.nan))
        state = pd.Series(False, index=C.index)
        on = False
        for t in month_days:
            if pd.notna(breadth.iloc[t]):
                if breadth.iloc[t] >= 0.60:
                    on = True
                elif breadth.iloc[t] <= 0.40:
                    on = False
            state.iloc[t] = on
        # make_target forward-fills monthly targets. State only changes at month-end.
        q = pd.DataFrame(np.repeat(state.to_numpy()[:, None], C.shape[1], axis=1), index=C.index, columns=C.columns)
        cond = q & elig
        score = pd.DataFrame(1.0, index=C.index, columns=C.columns).where(cond)
        return g1.make_target(elig, cond, score, C.shape[1], month_days)
    else:
        raise KeyError(name)

    cond = cond & elig
    return g1.make_target(elig, cond, score, k, month_days)


def metric_for(r: pd.Series, turnover: pd.Series, exposure: pd.Series, market: str, month_days: np.ndarray, include_decisions: bool = True) -> dict:
    out = g1.metric_for(r, turnover, exposure, market)
    idx = r.index
    for key, start, end in (("IS", "2012-06-01" if market == "KR" else "2001-01-03", "2019-12-31" if market == "KR" else "2016-12-30"),
                            ("LATER_CONTAMINATED", "2020-01-01" if market == "KR" else "2017-01-03", None)):
        mask = (idx[month_days] >= pd.Timestamp(start))
        if end:
            mask &= idx[month_days] <= pd.Timestamp(end)
        out[key]["monthly_rebalance_decisions"] = int(mask.sum()) if include_decisions else 0
    return out


def main() -> int:
    started = pd.Timestamp.now(tz="UTC")
    run_id = f"GEN02-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ledger = HERE / f"attempts_{run_id}.jsonl"
    curves_path = HERE / f"equity_curves_{run_id}.csv.gz"
    manifest_path = HERE / f"manifest_{run_id}.json"
    manifest = {"run_id": run_id, "prereg_sha256": sha256(PREREG), "runner_sha256": sha256(Path(__file__)),
                "gen01_runner_sha256": sha256(ROOT / "generation_01" / "run_gen01.py"), "python": sys.version,
                "numpy": np.__version__, "pandas": pd.__version__, "started_utc": started.isoformat(),
                "data_root": str(g1.DATA), "attempts_file": str(ledger), "status": "RUNNING"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    curve_rows: list[dict] = []
    attempt_n = 0
    for market in ("US", "KR"):
        try:
            data = g1.load_market(market)
            month_days = g1.month_ends(data["cal"])
            br, btv, bex = g1.benchmark_returns(data)
            bm = metric_for(br, btv, bex, market, month_days, include_decisions=False)
            if bm["IS"].get("status") != "OK":
                raise ValueError(f"invalid benchmark IS metrics: {bm['IS']}")
        except Exception as e:
            for j, name in enumerate(NAMES, 1):
                aid = f"{run_id}-{market}-{j:02d}-{name}"
                log_event(ledger, {"event": "attempt_fail", "attempt_id": aid, "market": market, "candidate": name,
                                   "status": "FAILED", "stage": "market_setup_or_benchmark", "error_type": type(e).__name__,
                                   "error": str(e), "traceback": traceback.format_exc(limit=8),
                                   "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
            continue
        manifest.setdefault("markets", {})[market] = {"sessions": len(data["cal"]), "symbols": len(data["C"].columns),
                                                        "benchmark": bm, "data_note": data["data_note"]}
        for name in NAMES:
            attempt_n += 1
            aid = f"{run_id}-{market}-{attempt_n:02d}-{name}"
            log_event(ledger, {"event": "attempt_start", "attempt_id": aid, "market": market, "candidate": name,
                               "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"],
                               "planned_new_tests_in_generation": 12})
            t0 = time.time()
            try:
                w = candidate_targets(data, name, month_days)
                r, tv, ex = g1.simulate(data, w)
                result = {"event": "attempt_finish", "attempt_id": aid, "market": market, "candidate": name,
                          "status": "COMPLETED_EXPLORATORY", "data_note": data["data_note"], "benchmark": bm,
                          "strategy": metric_for(r, tv, ex, market, month_days), "runtime_seconds": round(time.time() - t0, 3),
                          "nonconfirmatory_reason": "previously inspected windows; historical test ledger and PIT/universe reconciliation unresolved"}
                for d, val in r.items():
                    curve_rows.append({"attempt_id": aid, "market": market, "candidate": name, "date": str(d.date()),
                                       "daily_return_net": float(val), "turnover": float(tv.loc[d]), "exposure": float(ex.loc[d])})
                log_event(ledger, result)
                print(f"{aid}: {json.dumps(result['strategy'], ensure_ascii=False)}", flush=True)
            except Exception as e:
                log_event(ledger, {"event": "attempt_fail", "attempt_id": aid, "market": market, "candidate": name,
                                   "status": "FAILED", "error_type": type(e).__name__, "error": str(e),
                                   "runtime_seconds": round(time.time() - t0, 3), "traceback": traceback.format_exc(limit=8)})
                print(f"{aid}: FAILED {type(e).__name__}: {e}", flush=True)
        del data
    if curve_rows:
        pd.DataFrame(curve_rows).to_csv(curves_path, index=False, compression="gzip")
    manifest["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    manifest["status"] = "COMPLETED_WITH_ATTEMPTS"
    manifest["attempt_events_sha256"] = sha256(ledger) if ledger.exists() else None
    manifest["curve_file"] = str(curves_path) if curve_rows else None
    if curve_rows:
        manifest["curve_file_sha256"] = sha256(curves_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
