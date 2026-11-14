"""Exploratory KR/US daily-bar screens; reads only the local data_mirror."""
from __future__ import annotations

import csv
import hashlib
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
DATA = ROOT / "data_mirror"
ANN = 252


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def log_event(event: dict, attempts_path: Path) -> None:
    event = {"ts_utc": pd.Timestamp.now(tz="UTC").isoformat(), **event}
    with attempts_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def repair_kr(frame: pd.DataFrame, is_delisted: bool) -> pd.DataFrame:
    """Use the frozen KR-v2 large-gap repair as a data normalization rule."""
    d = frame.copy()
    px = d[["open", "high", "low", "close"]].to_numpy(float).copy()
    vol = d["volume"].to_numpy(float).copy()
    lim = np.where(d.index < pd.Timestamp("2015-06-15"), 0.155, 0.305)
    traded = np.where(np.isfinite(vol) & (vol > 0))[0]
    for k in range(1, len(traded)):
        t, p = traded[k], traded[k - 1]
        if is_delisted and t >= len(d) - 15:
            continue
        if px[p, 3] <= 0:
            continue
        factor = px[t, 3] / px[p, 3]
        if abs(factor - 1) > lim[t]:
            px[:t] *= factor
            vol[:t] /= factor
    d[["open", "high", "low", "close"]] = px
    d["volume"] = vol
    return d


def load_market(market: str) -> dict:
    if market == "KR":
        folder = DATA / "kr_daily_v2" / "data"
        # KODEX 200 is not present in this mirror. 005930 is used only to supply
        # the exchange-session calendar; the explicit equal-weight proxy below
        # supplies the regime series and the simulated KR comparison portfolio.
        bench = pd.read_parquet(folder / "005930.parquet")
        cal = pd.DatetimeIndex(pd.to_datetime(bench.index).tz_localize(None).normalize()).unique().sort_values()
        names = sorted(p.stem for p in folder.glob("*.parquet") if p.stem != "069500")
        threshold, k = 1_000_000_000.0, 20
        base_cost_buy, base_cost_sell = 0.00115, 0.00315
        # The available universe manifest and the v2 A2 registration disagree; this list is not asserted as an exact A2 replay.
        raw_universe = pd.read_csv(DATA / "kr_daily_v2" / "universe" / "universe_raw.csv", dtype={"code": str})
        raw_codes = set(raw_universe["code"].dropna().astype(str))
        names = [s for s in names if s in raw_codes]
        opens, highs, lows, closes, volumes = {}, {}, {}, {}, {}
        for j, sym in enumerate(names, 1):
            d = pd.read_parquet(folder / f"{sym}.parquet")
            d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
            d = d[~d.index.duplicated(keep="last")].sort_index()
            d = repair_kr(d, bool(d.index.max() < cal[-1])).reindex(cal)
            opens[sym], highs[sym], lows[sym], closes[sym], volumes[sym] = (d[c].astype("float32") for c in ("open", "high", "low", "close", "volume"))
            if j % 500 == 0:
                print(f"{market} loaded {j}/{len(names)}", flush=True)
        frame = {k0: pd.DataFrame(v, index=cal).sort_index(axis=1) for k0, v in (("O", opens), ("H", highs), ("L", lows), ("C", closes), ("V", volumes))}
        liquid = (frame["C"] * frame["V"]).where(frame["V"] > 0).rolling(60, min_periods=55).median()
        count = frame["C"].notna().cumsum()
        active = frame["C"].notna() & (count >= 252) & (frame["V"].fillna(0).rolling(60, min_periods=55).sum() >= 55) & (liquid >= threshold)
        daily = frame["C"].pct_change(fill_method=None)
        proxy_ret = daily.where(active).mean(axis=1).fillna(0.0)
        benchmark = (1.0 + proxy_ret).cumprod()
        return {"market": market, "cal": cal, **frame, "eligible": active, "benchmark": benchmark, "k": k, "fee_buy": base_cost_buy, "fee_sell": base_cost_sell, "data_note": "KR KODEX file absent; 005930 supplies calendar only; daily equal-weight eligible-name returns supply regime series; a separate monthly rebalanced equal-weight eligible-name portfolio is the comparison benchmark; exact A2 universe unresolved; exploratory only"}

    folder = DATA / "us_daily"
    membership = pd.read_csv(folder / "pit" / "sp500_ticker_start_end.csv", dtype={"ticker": str})
    membership["ticker"] = membership["ticker"].str.replace(".", "-", regex=False)
    membership["end_date"] = membership["end_date"].fillna("2099-12-31")
    bench = pd.read_parquet(folder / "SPY.parquet")
    cal = pd.DatetimeIndex(pd.to_datetime(bench.index).tz_localize(None).normalize()).unique().sort_values()
    names = sorted(set(membership["ticker"]))
    opens, highs, lows, closes, volumes, masks = {}, {}, {}, {}, {}, {}
    for j, sym in enumerate(names, 1):
        p = folder / f"{sym}.parquet"
        if not p.exists():
            continue
        meta_p = folder / f"{sym}.meta.json"
        if meta_p.exists():
            try:
                info = json.loads(meta_p.read_text()).get("vendor", {})
                if info.get("instrumentType") not in (None, "EQUITY"):
                    continue
            except (ValueError, OSError):
                pass
        d = pd.read_parquet(p)
        d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
        d = d[~d.index.duplicated(keep="last")].sort_index()
        factor = (d["adjclose"] / d["close"]).replace([np.inf, -np.inf], np.nan) if "adjclose" in d else pd.Series(1.0, index=d.index)
        d["open"], d["high"], d["low"] = d["open"] * factor, d["high"] * factor, d["low"] * factor
        d["close"] = d["adjclose"] if "adjclose" in d else d["close"]
        d = d.reindex(cal)
        opens[sym], highs[sym], lows[sym], closes[sym], volumes[sym] = (d[c].astype("float32") for c in ("open", "high", "low", "close", "volume"))
        m = pd.Series(False, index=cal)
        for r in membership[membership["ticker"] == sym].itertuples(index=False):
            m.loc[pd.Timestamp(r.start_date):pd.Timestamp(r.end_date)] = True
        masks[sym] = m
        if j % 100 == 0:
            print(f"{market} loaded {j}/{len(names)} PIT tickers", flush=True)
    symbols = sorted(closes)
    frame = {k0: pd.DataFrame(v, index=cal).reindex(columns=symbols) for k0, v in (("O", opens), ("H", highs), ("L", lows), ("C", closes), ("V", volumes))}
    member = pd.DataFrame(masks, index=cal).reindex(columns=symbols).fillna(False)
    count = frame["C"].notna().cumsum()
    active = member & frame["C"].notna() & (count >= 260)
    benchmark = bench["adjclose"].reindex(cal).astype(float) if "adjclose" in bench else bench["close"].reindex(cal).astype(float)
    return {"market": market, "cal": cal, **frame, "eligible": active, "benchmark": benchmark, "k": 50, "fee_buy": 0.001, "fee_sell": 0.001, "data_note": f"PIT members with local prices only; missing price history remains an optimistic coverage bias; {len(symbols)} tickers"}


def roll_weighted(x: np.ndarray, n: int) -> np.ndarray:
    """Trailing weighted sum with weights 1..n, requiring a complete finite window."""
    t, m = x.shape
    a = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float64, copy=False)
    finite = np.isfinite(x).astype(np.int32)
    counts = pd.DataFrame(finite).rolling(n, min_periods=n).sum().to_numpy()
    sums = pd.DataFrame(a).rolling(n, min_periods=1).sum().to_numpy()
    out = np.full((t, m), np.nan)
    if t < n:
        return out
    weights = np.arange(1, n + 1, dtype=float)[:, None]
    out[n - 1] = (a[:n] * weights).sum(axis=0)
    for i in range(n, t):
        out[i] = out[i - 1] - sums[i - 1] + n * a[i]
    out[counts < n] = np.nan
    return out


def wma(x: np.ndarray, n: int) -> np.ndarray:
    return roll_weighted(x, n) / (n * (n + 1) / 2)


def ols_trend(logc: pd.DataFrame, n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    y = logc.to_numpy(float)
    sy = logc.rolling(n, min_periods=n).sum().to_numpy()
    syy = logc.pow(2).rolling(n, min_periods=n).sum().to_numpy()
    sxy = roll_weighted(y, n)
    sx, sxx = n * (n + 1) / 2, n * (n + 1) * (2 * n + 1) / 6
    num = n * sxy - sx * sy
    denx = n * sxx - sx * sx
    deny = n * syy - sy * sy
    slope = num / denx
    r2 = np.divide(num * num, denx * deny, out=np.full_like(num, np.nan), where=deny > 1e-16)
    return pd.DataFrame(slope, index=logc.index, columns=logc.columns), pd.DataFrame(np.clip(r2, 0, 1), index=logc.index, columns=logc.columns)


def stateful(entry: pd.DataFrame, exit_: pd.DataFrame) -> pd.DataFrame:
    e, x = entry.fillna(False).to_numpy(bool), exit_.fillna(False).to_numpy(bool)
    out = np.zeros(e.shape, bool)
    for t in range(1, len(e)):
        out[t] = (out[t - 1] & ~x[t]) | (e[t] & ~x[t])
    return pd.DataFrame(out, index=entry.index, columns=entry.columns)


def stateful_monthly(entry: pd.DataFrame, exit_: pd.DataFrame, rebalance_days: np.ndarray) -> pd.DataFrame:
    """Change position state only at registered month-end decisions."""
    e, x = entry.fillna(False).to_numpy(bool), exit_.fillna(False).to_numpy(bool)
    out = np.zeros(e.shape, bool)
    active = np.zeros(e.shape[1], bool)
    for t in rebalance_days:
        active = (active & ~x[t]) | (e[t] & ~x[t])
        out[t] = active
    return pd.DataFrame(out, index=entry.index, columns=entry.columns)


def month_ends(index: pd.DatetimeIndex) -> np.ndarray:
    return pd.Series(np.arange(len(index)), index=index).groupby([index.year, index.month]).max().to_numpy(int)


def make_target(eligible: pd.DataFrame, condition: pd.DataFrame, score: pd.DataFrame, k: int, rebalance_days: np.ndarray) -> np.ndarray:
    ev = eligible.fillna(False).to_numpy(bool)
    q = condition.fillna(False).to_numpy(bool)
    s = score.to_numpy(float)
    t, n = ev.shape
    w = np.zeros((t, n), dtype=np.float32)
    for i in rebalance_days:
        sel = np.flatnonzero(ev[i] & q[i] & np.isfinite(s[i]))
        if len(sel) > k:
            sel = sel[np.lexsort((sel, -s[i, sel]))[:k]]
        if len(sel):
            w[i, sel] = 1.0 / len(sel)
    frame = pd.DataFrame(w)
    non_rebalance = np.ones(t, dtype=bool)
    non_rebalance[rebalance_days] = False
    frame.loc[non_rebalance, :] = np.nan
    return frame.ffill().fillna(0).to_numpy(np.float32)


def make_event_target(data: dict, event: pd.DataFrame, rank_score: pd.DataFrame) -> np.ndarray:
    ev, sc = event.fillna(False).to_numpy(bool), rank_score.to_numpy(float)
    t, n = ev.shape
    out = np.zeros((t, n), dtype=np.float32)
    k = data["k"]
    active: dict[int, tuple[int, float]] = {}
    for i in range(t):
        for j in [j for j, (end, _) in active.items() if end < i]:
            del active[j]
        for j in np.flatnonzero(ev[i]):
            active[int(j)] = (i + 4, float(sc[i, j]))
        # A signal at close i is eligible to fill at open i+1; the day-i row is shifted below.
        choices = np.array(sorted(active), dtype=int)
        if len(choices) > k:
            vals = np.array([active[int(j)][1] for j in choices])
            choices = choices[np.lexsort((choices, -vals))[:k]]
        if len(choices):
            out[i, choices] = 1.0 / len(choices)
    return out


def simulate(data: dict, desired_at_close: np.ndarray, cost_multiplier: float = 1.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Daily-bar execution: decisions at close t become target weights at open t+1."""
    O, C = data["O"].to_numpy(float), data["C"].to_numpy(float)
    T, N = C.shape
    desired = np.vstack([np.zeros((1, N)), desired_at_close[:-1]])
    desired[~np.isfinite(O)] = 0.0
    desired[~np.isfinite(C)] = 0.0
    returns = np.zeros(T, dtype=float)
    turnover = np.zeros(T, dtype=float)
    exposure = np.zeros(T, dtype=float)
    prev_w = np.zeros(N, dtype=float)
    for i in range(1, T):
        prev_close = C[i - 1]
        open_i, close_i = O[i], C[i]
        valid_gap = np.isfinite(open_i) & np.isfinite(prev_close) & (prev_close > 0)
        gap = np.zeros(N)
        gap[valid_gap] = open_i[valid_gap] / prev_close[valid_gap] - 1.0
        held_gap = prev_w.copy()
        # A held symbol with no bar is kept at its last close; its missing exit cannot be filled.
        held_gap[~valid_gap] = prev_w[~valid_gap]
        overnight = float(np.dot(prev_w, gap))
        post_gap = prev_w * (1 + gap) / max(1 + overnight, 1e-12)
        target = desired[i].astype(float, copy=True)
        # Do not invent an open fill for a missing/suspended security.
        no_open = ~np.isfinite(open_i) | (open_i <= 0)
        target[no_open] = post_gap[no_open]
        total = target.sum()
        if total > 1:
            target /= total
        sells = np.maximum(post_gap - target, 0).sum()
        buys = np.maximum(target - post_gap, 0).sum()
        turnover[i] = sells + buys
        fees = cost_multiplier * (buys * data["fee_buy"] + sells * data["fee_sell"])
        valid_day = np.isfinite(open_i) & np.isfinite(close_i) & (open_i > 0)
        intra = np.zeros(N)
        intra[valid_day] = close_i[valid_day] / open_i[valid_day] - 1.0
        intraday = float(np.dot(target, intra))
        returns[i] = (1 + overnight) * (1 - fees) * (1 + intraday) - 1
        exposure[i] = target.sum()
        prev_w = target * (1 + intra) / max(1 + intraday, 1e-12)
        # Portfolio weights cannot be negative and any rounding/leverage drift is normalized.
        prev_w = np.maximum(prev_w, 0)
        if prev_w.sum() > 1:
            prev_w /= prev_w.sum()
    idx = data["cal"]
    return (pd.Series(returns, index=idx), pd.Series(turnover, index=idx), pd.Series(exposure, index=idx))


def metrics(r: pd.Series, turnover: pd.Series, exposure: pd.Series, start: str, end: str | None = None) -> dict:
    x = r.loc[start:end].dropna()
    x = x.iloc[1:] if len(x) else x
    if len(x) < 100:
        return {"status": "INSUFFICIENT", "bars": int(len(x))}
    eq = (1 + x).cumprod()
    years = len(x) / ANN
    cagr = float(eq.iloc[-1] ** (1 / years) - 1) if years > 0 and eq.iloc[-1] > 0 else -1.0
    sd = float(x.std(ddof=1))
    sharpe = float(x.mean() / sd * math.sqrt(ANN)) if sd > 0 else 0.0
    high_water = pd.concat([pd.Series([1.0], index=[x.index[0] - pd.Timedelta(days=1)]), eq])
    dd = high_water / high_water.cummax() - 1
    return {"status": "OK", "start": str(x.index[0].date()), "end": str(x.index[-1].date()), "bars": int(len(x)), "cagr": cagr, "sharpe": sharpe, "mdd": float(dd.min()), "total_return": float(eq.iloc[-1] - 1), "annual_turnover": float(turnover.loc[x.index].sum() / years), "mean_exposure": float(exposure.loc[x.index].mean())}


def compute_residual_score(data: dict) -> pd.DataFrame:
    c = data["C"].astype(float)
    r = np.log(c / c.shift(1))
    m = np.log(data["benchmark"].astype(float) / data["benchmark"].astype(float).shift(1))
    mvar = m.rolling(126, min_periods=126).var(ddof=0)
    cov = r.mul(m, axis=0).rolling(126, min_periods=126).mean().sub(r.rolling(126, min_periods=126).mean().mul(m.rolling(126, min_periods=126).mean(), axis=0), axis=0)
    beta = cov.div(mvar, axis=0)
    rsum = r.rolling(126, min_periods=126).sum()
    msum = m.rolling(126, min_periods=126).sum()
    return rsum - beta.mul(msum, axis=0)


def candidate_targets(data: dict, name: str, month_days: np.ndarray) -> np.ndarray:
    C, H, L = (data[k].astype(float) for k in ("C", "H", "L"))
    O, V = data["O"].astype(float), data["V"].astype(float)
    elig, k = data["eligible"], data["k"]
    prev_h20 = H.shift(1).rolling(20, min_periods=20).max()
    prev_h55 = H.shift(1).rolling(55, min_periods=55).max()
    prev_l10 = L.shift(1).rolling(10, min_periods=10).min()
    prev_l20 = L.shift(1).rolling(20, min_periods=20).min()
    pc = C.shift(1)
    tr = pd.DataFrame(
        np.maximum.reduce([(H - L).to_numpy(), (H - pc).abs().to_numpy(), (L - pc).abs().to_numpy()]),
        index=C.index,
        columns=C.columns,
    )
    atr14 = tr.rolling(14, min_periods=14).mean()
    atr20 = tr.rolling(20, min_periods=20).mean()
    rets = C.pct_change(fill_method=None)
    cond = pd.DataFrame(False, index=C.index, columns=C.columns)
    score = pd.DataFrame(np.nan, index=C.index, columns=C.columns)

    if name == "KAMA_ER20":
        er = (C / C.shift(20) - 1).abs() / (C.pct_change(fill_method=None).abs().rolling(20, min_periods=20).sum())
        fast, slow = 2 / 3, 2 / 31
        sc = (er * (fast - slow) + slow) ** 2
        ca = C.to_numpy(float); sva = sc.to_numpy(float)
        kama = np.full_like(ca, np.nan)
        for t in range(len(ca)):
            if t == 0:
                kama[t] = ca[t]
            else:
                init = np.isfinite(ca[t]) & ~np.isfinite(kama[t - 1])
                kama[t, init] = ca[t, init]
                keep = np.isfinite(ca[t]) & ~np.isfinite(sva[t]) & np.isfinite(kama[t - 1])
                kama[t, keep] = kama[t - 1, keep]
                good = np.isfinite(ca[t]) & np.isfinite(ca[t - 1]) & np.isfinite(sva[t]) & np.isfinite(kama[t - 1])
                kama[t, good] = kama[t - 1, good] + sva[t, good] * (ca[t, good] - kama[t - 1, good])
        km = pd.DataFrame(kama, index=C.index, columns=C.columns)
        cond = (er >= 0.30) & (C > km) & (km > km.shift(1))
        score = er
    elif name == "HMA55_BREAKOUT":
        arr = C.to_numpy(float)
        hma = wma(2 * wma(arr, 27) - wma(arr, 55), 7)
        hm = pd.DataFrame(hma, index=C.index, columns=C.columns)
        entry = (C > prev_h55) & (hm > hm.shift(1))
        exit_ = (C < prev_l20) | (hm <= hm.shift(1))
        cond = stateful_monthly(entry, exit_, month_days)
        score = hm / hm.shift(5) - 1
    elif name == "REG60_R2_BREAKOUT":
        slope, r2 = ols_trend(np.log(C.where(C > 0)), 60)
        entry = (C > prev_h20) & (slope > 0) & (r2 >= 0.35)
        exit_ = (C < prev_l20) | (slope <= 0)
        cond = stateful_monthly(entry, exit_, month_days)
        score = r2
    elif name == "ATR_NORM_SMA100":
        sma100 = C.rolling(100, min_periods=100).mean()
        norm = (sma100 / sma100.shift(20) - 1) / (atr20 / C)
        entry = (C > prev_h20) & (norm >= 0.75)
        exit_ = (C < prev_l20) | (norm <= 0)
        cond = stateful_monthly(entry, exit_, month_days)
        score = norm
    elif name == "VHF63_DONCHIAN20":
        net = C.rolling(63, min_periods=63).max() - C.rolling(63, min_periods=63).min()
        vhf = net / C.diff().abs().rolling(63, min_periods=63).sum()
        entry = (C > prev_h20) & (vhf >= 0.35)
        exit_ = (C < prev_l10) | (vhf < 0.20)
        cond = stateful_monthly(entry, exit_, month_days)
        score = vhf
    elif name == "PERSIST63":
        ret63 = C / C.shift(63) - 1
        pos_share = rets.gt(0).rolling(63, min_periods=63).mean()
        cond = stateful_monthly((ret63 > 0) & (pos_share >= 0.60), (ret63 <= 0) | (pos_share < 0.50), month_days)
        score = ret63 * pos_share
    elif name == "ATR_BUFFER55":
        distance = (C - prev_h55) / atr14
        entry = C > prev_h55 + 0.5 * atr14
        exit_ = C < prev_l20
        cond = stateful_monthly(entry, exit_, month_days)
        score = distance
    elif name == "RESIDUAL_MOM126":
        score = compute_residual_score(data)
        cond = score.notna()
    elif name == "MOM_TO_LOWVOL_200SMA":
        mom = C.shift(21) / C.shift(252) - 1
        vol = rets.rolling(252, min_periods=200).std()
        market = data["benchmark"].astype(float)
        trend_on = market > market.rolling(200, min_periods=200).mean()
        for i in month_days:
            valid = elig.iloc[i] & mom.iloc[i].notna() & vol.iloc[i].notna()
            if bool(trend_on.iloc[i]):
                score.iloc[i] = mom.iloc[i].where(valid)
            else:
                score.iloc[i] = (-vol.iloc[i]).where(valid)
                cond.iloc[i] = valid
        # For the on-state, use the top momentum cross-section; off-state uses top negative volatility.
        for i in month_days:
            if bool(trend_on.iloc[i]):
                cond.iloc[i] = elig.iloc[i] & mom.iloc[i].notna()
        return make_target(elig, cond, score, k, month_days)
    elif name == "MOM12_1_VOL10_OVERLAY":
        # Return unscaled base 12-1 basket; run_gen applies its fixed volatility overlay.
        mom = C.shift(21) / C.shift(252) - 1
        cond = mom.notna()
        score = mom
    elif name == "GAP_REVERSAL_5D":
        gap = O / C.shift(1) - 1
        prior_atr_pct = atr14.shift(1) / C.shift(1)
        event = (gap <= -1.5 * prior_atr_pct) & (C > O) & elig
        gap_score = (-gap / prior_atr_pct).where(event)
        return make_event_target(data, event, gap_score)
    else:
        raise KeyError(name)

    cond = cond & elig
    if name == "RESIDUAL_MOM126":
        cond = score.notna() & elig
    return make_target(elig, cond, score, k, month_days)


def benchmark_returns(data: dict) -> tuple[pd.Series, pd.Series, pd.Series]:
    if data["market"] == "KR":
        # KODEX is absent. Use the preregistered equal-weight eligible universe
        # analogue, but label it as a snapshot-biased proxy in the attempt record.
        eligible = data["eligible"]
        score = pd.DataFrame(1.0, index=eligible.index, columns=eligible.columns)
        w = make_target(eligible, eligible, score, eligible.shape[1], month_ends(data["cal"]))
        return simulate(data, w)
    # US benchmark comes from its explicit total-return SPY file.
    b = data["benchmark"].astype(float)
    r = b.pct_change(fill_method=None)
    if len(r):
        if r.iloc[1:].isna().any() or not np.isfinite(r.iloc[1:].to_numpy(float)).all():
            raise ValueError("US SPY benchmark has missing/non-finite daily returns after its first observation")
        r.iloc[0] = 0.0
        r.iloc[0] -= data["fee_buy"]
        r.iloc[-1] -= data["fee_sell"]
    return r, pd.Series(0.0, index=b.index), pd.Series(1.0, index=b.index)


def metric_for(r: pd.Series, tv: pd.Series, ex: pd.Series, market: str) -> dict:
    if market == "KR":
        return {"IS": metrics(r, tv, ex, "2012-06-01", "2019-12-31"), "LATER_CONTAMINATED": metrics(r, tv, ex, "2020-01-01")}
    return {"IS": metrics(r, tv, ex, "2001-01-03", "2016-12-30"), "LATER_CONTAMINATED": metrics(r, tv, ex, "2017-01-03")}


def main() -> int:
    prereg = HERE / "PREREG.md"
    started = pd.Timestamp.now(tz="UTC")
    run_id = f"GEN01-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    manifest_path = HERE / f"manifest_{run_id}.json"
    attempts_path = HERE / f"attempts_{run_id}.jsonl"
    curves_path = HERE / f"equity_curves_{run_id}.csv.gz"
    manifest = {"run_id": run_id, "prereg_sha256": sha256(prereg), "runner_sha256": sha256(Path(__file__)), "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__, "started_utc": started.isoformat(), "data_root": str(DATA), "data_note": "See PREREG.md; source snapshot is non-atomic and universe reconciliation is unresolved", "attempts_file": str(attempts_path)}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    names = ["KAMA_ER20", "HMA55_BREAKOUT", "REG60_R2_BREAKOUT", "ATR_NORM_SMA100", "VHF63_DONCHIAN20", "PERSIST63", "ATR_BUFFER55", "RESIDUAL_MOM126", "GAP_REVERSAL_5D", "MOM12_1_VOL10_OVERLAY", "MOM_TO_LOWVOL_200SMA"]
    attempt_n = 0
    curves = []
    for market in ("US", "KR"):
        print(f"Loading {market}", flush=True)
        try:
            data = load_market(market)
            print(f"Loaded {market}: {len(data['cal'])} sessions x {len(data['C'].columns)} symbols; {data['data_note']}", flush=True)
            mends = month_ends(data["cal"])
            br, btv, bex = benchmark_returns(data)
            brm = metric_for(br, btv, bex, market)
            if not brm["IS"].get("status") == "OK":
                raise ValueError(f"Benchmark IS invalid: {brm['IS']}")
            print(f"{market} benchmark: {json.dumps(brm, ensure_ascii=False)}", flush=True)
        except Exception as e:
            for n, name in enumerate(names, 1):
                aid = f"{run_id}-{market}-{n:02d}-{name}"
                log_event({"event": "attempt_fail", "attempt_id": aid, "market": market, "candidate": name, "status": "FAILED", "stage": "market_setup_or_benchmark", "error_type": type(e).__name__, "error": str(e), "traceback": traceback.format_exc(limit=8), "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]}, attempts_path)
            print(f"{market}: market setup failed; logged all {len(names)} affected attempts: {type(e).__name__}: {e}", flush=True)
            continue
        for name in names:
            attempt_n += 1
            aid = f"{run_id}-{market}-{attempt_n:02d}-{name}"
            start_event = {"event": "attempt_start", "attempt_id": aid, "market": market, "candidate": name, "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"], "planned_new_tests_in_generation": 22}
            log_event(start_event, attempts_path)
            start_t = time.time()
            try:
                w = candidate_targets(data, name, mends)
                if name == "MOM12_1_VOL10_OVERLAY":
                    base_r, _, _ = simulate(data, w)
                    vol = base_r.rolling(20, min_periods=20).std() * math.sqrt(ANN)
                    scale = (0.10 / vol).clip(upper=1.0).shift(1).fillna(1.0).to_numpy(float)
                    w = w * scale[:, None]
                r, tv, ex = simulate(data, w)
                result = {"attempt_id": aid, "market": market, "candidate": name, "status": "COMPLETED_EXPLORATORY", "data_note": data["data_note"], "benchmark": brm, "strategy": metric_for(r, tv, ex, market), "runtime_seconds": round(time.time() - start_t, 3), "nonconfirmatory_reason": "previously inspected historical windows; unresolved global historical trial count and snapshot/universe provenance"}
                for d, val in r.items():
                    curves.append({"attempt_id": aid, "market": market, "candidate": name, "date": str(d.date()), "daily_return_net": float(val), "turnover": float(tv.loc[d]), "exposure": float(ex.loc[d])})
                log_event({"event": "attempt_finish", **result}, attempts_path)
                print(f"{aid}: {json.dumps(result['strategy'], ensure_ascii=False)}", flush=True)
            except Exception as e:
                failure = {"event": "attempt_fail", "attempt_id": aid, "market": market, "candidate": name, "status": "FAILED", "error_type": type(e).__name__, "error": str(e), "runtime_seconds": round(time.time() - start_t, 3), "traceback": traceback.format_exc(limit=8)}
                log_event(failure, attempts_path)
                print(f"{aid}: FAILED {type(e).__name__}: {e}", flush=True)
        del data
    if curves:
        pd.DataFrame(curves).to_csv(curves_path, index=False, compression="gzip")
    manifest["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    manifest["attempt_events_sha256"] = sha256(attempts_path) if attempts_path.exists() else None
    manifest["curve_file"] = str(curves_path) if curves else None
    if curves:
        manifest["curve_file_sha256"] = sha256(curves_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
