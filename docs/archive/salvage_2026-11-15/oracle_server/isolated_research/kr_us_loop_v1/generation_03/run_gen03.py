"""Generation 03 fixed OHLC trend hypotheses; local-only, immutable run artifacts."""
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
SPEC = importlib.util.spec_from_file_location("gen01_runner", ROOT / "generation_01" / "run_gen01.py")
g1 = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(g1)
NAMES = ["FRAMA16_SLOPE5", "VORTEX14_SMA100", "ICHIMOKU_CURRENT_CLOUD", "DCTC_GAP_INTRADAY63", "VOL_COMPRESSION_RELEASE55"]


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
    e, x = entry.fillna(False).to_numpy(bool), exit_.fillna(False).to_numpy(bool)
    out = np.zeros(e.shape, dtype=bool)
    active = np.zeros(e.shape[1], dtype=bool)
    for t in month_days:
        active = (active & ~x[t]) | (e[t] & ~x[t])
        out[t] = active
    return pd.DataFrame(out, index=entry.index, columns=entry.columns)


def audit_kr_raw_prices(folder: Path) -> dict:
    """Fail closed on traded rows that cannot be safely split-adjusted."""
    scanned, bad_rows, examples = 0, 0, []
    for path in sorted(folder.glob("*.parquet")):
        d = pd.read_parquet(path, columns=["open", "high", "low", "close", "volume"])
        px = d[["open", "high", "low", "close"]].to_numpy(float)
        vol = d["volume"].to_numpy(float)
        traded = np.isfinite(vol) & (vol > 0)
        invalid = traded & (~np.isfinite(px).all(axis=1) | (px <= 0).any(axis=1) |
                            (px[:, 1] < np.maximum(px[:, 0], px[:, 3])) |
                            (px[:, 2] > np.minimum(px[:, 0], px[:, 3])) |
                            (px[:, 1] < px[:, 2]))
        n = int(invalid.sum())
        scanned += 1
        bad_rows += n
        if n and len(examples) < 10:
            examples.extend({"symbol": path.stem, "row": str(idx), "ohlcv": d.loc[idx, ["open", "high", "low", "close", "volume"]].to_dict()}
                            for idx in d.index[invalid][:10 - len(examples)])
    result = {"parquet_files_scanned": scanned, "invalid_traded_ohlc_rows": bad_rows, "examples": examples}
    if bad_rows:
        raise ValueError("KR raw-price integrity gate failed: " + json.dumps(result, ensure_ascii=False, default=str))
    return result


def candidate_targets(data: dict, name: str, month_days: np.ndarray) -> np.ndarray:
    C, H, L, O = (data[k].astype(float) for k in ("C", "H", "L", "O"))
    elig, k = data["eligible"], data["k"]
    close = C.to_numpy(float)
    logc = np.log(C.where(C > 0))
    daily_logret = np.log(C / C.shift(1))
    cond = pd.DataFrame(False, index=C.index, columns=C.columns)
    score = pd.DataFrame(np.nan, index=C.index, columns=C.columns)

    if name == "FRAMA16_SLOPE5":
        hh8 = H.rolling(8, min_periods=8).max()
        ll8 = L.rolling(8, min_periods=8).min()
        hh8_prior, ll8_prior = hh8.shift(8), ll8.shift(8)
        hh16 = H.rolling(16, min_periods=16).max()
        ll16 = L.rolling(16, min_periods=16).min()
        n1, n2, n3 = (hh8 - ll8) / 8.0, (hh8_prior - ll8_prior) / 8.0, (hh16 - ll16) / 16.0
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            dim = (np.log(n1 + n2) - np.log(n3)) / np.log(2.0)
            alpha = np.exp(-4.6 * (dim - 1.0)).clip(0.01, 1.0)
        alpha = alpha.where((n1 > 0) & (n2 > 0) & (n3 > 0) & np.isfinite(alpha))
        x = C.to_numpy(float)
        a = alpha.to_numpy(float)
        filt = np.full_like(x, np.nan)
        run = np.zeros_like(x, dtype=np.int32)
        for t in range(len(C.index)):
            observed = np.isfinite(x[t]) & (x[t] > 0)
            run[t] = np.where(observed, (run[t - 1] + 1) if t else 1, 0)
            restart = observed & (run[t] == 1)
            filt[t, restart] = x[t, restart]
            hold = observed & (run[t] > 1) & np.isfinite(filt[t - 1] if t else np.nan)
            filt[t, hold] = filt[t - 1, hold] if t else np.nan
            update = observed & (run[t] > 1) & np.isfinite(a[t]) & np.isfinite(filt[t - 1] if t else np.nan)
            filt[t, update] = a[t, update] * x[t, update] + (1.0 - a[t, update]) * filt[t - 1, update]
        F = pd.DataFrame(filt, index=C.index, columns=C.columns)
        slope5 = F - F.shift(5)
        vol63 = daily_logret.rolling(63, min_periods=63).std(ddof=1)
        ready = pd.DataFrame(run >= 200, index=C.index, columns=C.columns)
        feature_available = alpha.notna() & ready & slope5.notna() & vol63.notna()
        entry = (C > F) & (slope5 > 0) & feature_available
        exit_ = ((C <= F) | (slope5 <= 0) | ~feature_available)
        cond = monthly_stateful(entry, exit_, month_days)
        score = (slope5 / vol63).where(feature_available)
    elif name == "VORTEX14_SMA100":
        prev_c, prev_h, prev_l = C.shift(1), H.shift(1), L.shift(1)
        vm_plus = (H - prev_l).abs()
        vm_minus = (L - prev_h).abs()
        tr = pd.DataFrame(np.maximum.reduce([(H - L).to_numpy(), (H - prev_c).abs().to_numpy(),
                                              (L - prev_c).abs().to_numpy()]), index=C.index, columns=C.columns)
        sum_tr = tr.rolling(14, min_periods=14).sum().where(lambda x: x > 0)
        vi_plus = vm_plus.rolling(14, min_periods=14).sum() / sum_tr
        vi_minus = vm_minus.rolling(14, min_periods=14).sum() / sum_tr
        sma100 = C.rolling(100, min_periods=100).mean()
        score = vi_plus - vi_minus
        ready = score.notna() & sma100.notna()
        cond = monthly_stateful((score > 0) & (C > sma100) & ready, ((score <= 0) | (C <= sma100)) & ready, month_days)
    elif name == "ICHIMOKU_CURRENT_CLOUD":
        hh9, ll9 = H.rolling(9, min_periods=9).max(), L.rolling(9, min_periods=9).min()
        hh26, ll26 = H.rolling(26, min_periods=26).max(), L.rolling(26, min_periods=26).min()
        hh52, ll52 = H.rolling(52, min_periods=52).max(), L.rolling(52, min_periods=52).min()
        tenkan, kijun = (hh9 + ll9) / 2.0, (hh26 + ll26) / 2.0
        span_a, span_b = (tenkan + kijun) / 2.0, (hh52 + ll52) / 2.0
        cloud_hi = pd.DataFrame(np.maximum(span_a.to_numpy(), span_b.to_numpy()), index=C.index, columns=C.columns)
        cloud_lo = pd.DataFrame(np.minimum(span_a.to_numpy(), span_b.to_numpy()), index=C.index, columns=C.columns)
        ready = cloud_hi.notna() & tenkan.notna() & kijun.notna()
        entry = (C > cloud_hi) & (tenkan > kijun) & ready
        exit_ = ((C <= cloud_hi) | (tenkan <= kijun)) & ready
        cond = monthly_stateful(entry, exit_, month_days)
        score = (C - cloud_hi) / C
    elif name == "DCTC_GAP_INTRADAY63":
        prev_c = C.shift(1)
        valid = (O > 0) & (C > 0) & (prev_c > 0)
        gap = np.log(O / prev_c).where(valid)
        intraday = np.log(C / O).where(valid)
        tg = gap.rolling(63, min_periods=63).mean() / (gap.rolling(63, min_periods=63).std(ddof=1) / np.sqrt(63.0))
        tb = intraday.rolling(63, min_periods=63).mean() / (intraday.rolling(63, min_periods=63).std(ddof=1) / np.sqrt(63.0))
        ready = tg.notna() & tb.notna() & np.isfinite(tg) & np.isfinite(tb)
        entry = (tg >= 0.5) & (tb >= 0.5) & ready
        exit_ = ((tg <= 0) | (tb <= 0)) & ready
        cond = monthly_stateful(entry, exit_, month_days)
        score = pd.DataFrame(np.minimum(tg.to_numpy(), tb.to_numpy()), index=C.index, columns=C.columns).where(ready)
    elif name == "VOL_COMPRESSION_RELEASE55":
        prev_c = C.shift(1)
        tr = pd.DataFrame(np.maximum.reduce([(H - L).to_numpy(), (H - prev_c).abs().to_numpy(),
                                              (L - prev_c).abs().to_numpy()]), index=C.index, columns=C.columns)
        atr20 = tr.rolling(20, min_periods=20).mean()
        atr_pct = atr20 / C
        base_min = atr_pct.shift(21).rolling(42, min_periods=42).min()
        old_q20 = atr_pct.shift(21).rolling(252, min_periods=252).quantile(0.20, interpolation="linear")
        prior55 = H.shift(1).rolling(55, min_periods=55).max()
        prior_l20 = L.shift(1).rolling(20, min_periods=20).min()
        valid = (base_min > 0) & (atr_pct > 0) & old_q20.notna() & prior55.notna() & prior_l20.notna()
        entry = (base_min <= old_q20) & (C > prior55) & (atr_pct >= 1.3 * base_min) & valid
        exit_ = (C < prior_l20) & valid
        cond = monthly_stateful(entry, exit_, month_days)
        score = ((C / prior55 - 1.0) / atr_pct).where(valid)
    else:
        raise KeyError(name)

    cond = cond & elig
    return g1.make_target(elig, cond, score, k, month_days)


def simulate_strict(data: dict, desired_at_close: np.ndarray) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Shared execution math, but fail instead of assigning flat return to missing held bars."""
    O, C = data["O"].to_numpy(float), data["C"].to_numpy(float)
    T, N = C.shape
    desired = np.vstack([np.zeros((1, N)), desired_at_close[:-1]])
    returns = np.zeros(T, dtype=float)
    turnover = np.zeros(T, dtype=float)
    exposure = np.zeros(T, dtype=float)
    prev_w = np.zeros(N, dtype=float)
    symbols = list(data["C"].columns)
    for i in range(1, T):
        prev_close, open_i, close_i = C[i - 1], O[i], C[i]
        target = desired[i].astype(float, copy=True)
        missing_open = ~np.isfinite(open_i) | (open_i <= 0)
        missing_close = ~np.isfinite(close_i) | (close_i <= 0)
        unresolved = (prev_w > 1e-8) & (missing_open | missing_close | ~np.isfinite(prev_close) | (prev_close <= 0))
        unfilled_buy = (target > 1e-8) & (missing_open | missing_close)
        bad = unresolved | unfilled_buy
        if bad.any():
            j = int(np.flatnonzero(bad)[0])
            reason = "held position lacks a valid OHLC mark" if unresolved[j] else "target entry lacks a complete executable OHLC bar"
            raise ValueError(f"strict execution data gap on {data['cal'][i].date()} {symbols[j]}: {reason}; candidate attempt rejected")
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
        valid_intra = np.isfinite(close_i) & (close_i > 0) & np.isfinite(open_i) & (open_i > 0)
        intra = np.zeros(N, dtype=float)
        intra[valid_intra] = close_i[valid_intra] / open_i[valid_intra] - 1.0
        intraday = float(np.dot(target, intra))
        returns[i] = (1.0 + overnight) * (1.0 - fees) * (1.0 + intraday) - 1.0
        exposure[i] = target.sum()
        prev_w = target * (1.0 + intra) / max(1.0 + intraday, 1e-12)
        prev_w = np.maximum(prev_w, 0)
        if prev_w.sum() > 1.0:
            prev_w /= prev_w.sum()
    idx = data["cal"]
    return pd.Series(returns, index=idx), pd.Series(turnover, index=idx), pd.Series(exposure, index=idx)


def metric_for(r: pd.Series, turnover: pd.Series, exposure: pd.Series, market: str, month_days: np.ndarray) -> dict:
    out = g1.metric_for(r, turnover, exposure, market)
    idx = r.index
    for key, start, end in (("IS", "2012-06-01" if market == "KR" else "2001-01-03", "2019-12-31" if market == "KR" else "2016-12-30"),
                            ("LATER_CONTAMINATED", "2020-01-01" if market == "KR" else "2017-01-03", None)):
        mask = idx[month_days] >= pd.Timestamp(start)
        if end:
            mask &= idx[month_days] <= pd.Timestamp(end)
        out[key]["monthly_rebalance_decisions"] = int(mask.sum())
    return out


def main() -> int:
    started = pd.Timestamp.now(tz="UTC")
    run_id = f"GEN03-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ledger, curves_path, manifest_path = (HERE / f"attempts_{run_id}.jsonl", HERE / f"equity_curves_{run_id}.csv.gz", HERE / f"manifest_{run_id}.json")
    manifest = {"run_id": run_id, "prereg_sha256": sha256(PREREG), "runner_sha256": sha256(Path(__file__)),
                "gen01_runner_sha256": sha256(ROOT / "generation_01" / "run_gen01.py"), "python": sys.version,
                "numpy": np.__version__, "pandas": pd.__version__, "started_utc": started.isoformat(),
                "data_root": str(g1.DATA), "planned_attempts": 10, "attempts_file": str(ledger), "status": "RUNNING"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    curve_rows: list[dict] = []
    attempt_n = 0
    for market in ("US", "KR"):
        try:
            kr_audit = None
            if market == "KR":
                kr_audit = audit_kr_raw_prices(g1.DATA / "kr_daily_v2" / "data")
                raise RuntimeError("KR execution blocked: shared inferred split-repair path has a reproduced corruption defect; corrected transformed panels, PIT membership and benchmark have not been audited")
            data = g1.load_market(market)
            month_days = g1.month_ends(data["cal"])
            br, btv, bex = g1.benchmark_returns(data)
            bm = g1.metric_for(br, btv, bex, market)
            if bm["IS"].get("status") != "OK":
                raise ValueError(f"invalid benchmark IS metrics: {bm['IS']}")
        except Exception as e:
            for j, name in enumerate(NAMES, 1):
                aid = f"{run_id}-{market}-{j:02d}-{name}"
                log_event(ledger, {"event": "attempt_start", "attempt_id": aid, "market": market, "candidate": name,
                                   "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"],
                                   "planned_new_tests_in_generation": 10})
                log_event(ledger, {"event": "attempt_fail", "attempt_id": aid, "market": market, "candidate": name,
                                   "status": "FAILED", "stage": "market_setup_or_benchmark", "error_type": type(e).__name__,
                                   "error": str(e), "traceback": traceback.format_exc(limit=8),
                                   "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
            continue
        manifest.setdefault("markets", {})[market] = {"sessions": len(data["cal"]), "symbols": len(data["C"].columns),
                                                        "benchmark": bm, "data_note": data["data_note"], "raw_price_audit": kr_audit}
        for name in NAMES:
            attempt_n += 1
            aid = f"{run_id}-{market}-{attempt_n:02d}-{name}"
            log_event(ledger, {"event": "attempt_start", "attempt_id": aid, "market": market, "candidate": name,
                               "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"],
                               "planned_new_tests_in_generation": 10})
            t0 = time.time()
            try:
                w = candidate_targets(data, name, month_days)
                r, tv, ex = simulate_strict(data, w)
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
    if ledger.exists():
        events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        terminal = [x for x in events if x.get("event") in ("attempt_finish", "attempt_fail")]
        started_ids = [x.get("attempt_id") for x in events if x.get("event") == "attempt_start"]
        terminal_ids = [x.get("attempt_id") for x in terminal]
        manifest["event_counts"] = {"attempt_start": len(started_ids), "attempt_finish": sum(x.get("event") == "attempt_finish" for x in events),
                                    "attempt_fail": sum(x.get("event") == "attempt_fail" for x in events)}
        manifest["attempt_ledger_integrity"] = len(started_ids) == manifest["planned_attempts"] and sorted(started_ids) == sorted(terminal_ids) and len(set(terminal_ids)) == manifest["planned_attempts"]
    manifest["status"] = "FINISHED_WITH_FAILED_ATTEMPTS" if manifest.get("event_counts", {}).get("attempt_fail", 0) else "COMPLETED_ALL_ATTEMPTS"
    manifest["attempt_events_sha256"] = sha256(ledger) if ledger.exists() else None
    manifest["curve_file"] = str(curves_path) if curve_rows else None
    if curve_rows:
        manifest["curve_file_sha256"] = sha256(curves_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
