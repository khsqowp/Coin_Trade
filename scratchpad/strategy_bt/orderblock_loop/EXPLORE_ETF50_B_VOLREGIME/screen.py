#!/usr/bin/env python3
# EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.
"""ETF volatility-regime exploratory screen. Reads parquet inputs and writes only adjacent outputs."""
from __future__ import annotations

import csv
import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
LABEL = "# EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run."
CUTOFF = pd.Timestamp("2026-06-01")
COST = 0.0006
RISK = ("SPY", "QQQ")
IDEAS = [f"VOLREG-{x}" for x in ("L1", "L2", "L3", "S1", "S2", "S3", "T1", "T2", "T3", "R1", "R2", "V1", "V2", "M1", "M2")]
COLS = ["idea_id", "family", "params", "start_date", "end_date", "n_switches", "n_orders", "strategy_cum_return_pct", "spy_cum_return_pct", "excess_return_pp", "strategy_mdd_pct", "spy_mdd_pct", "mdd_improvement_pp", "ret_2018_pct", "spy_ret_2018_pct", "ret_2022_pct", "spy_ret_2022_pct", "switches_per_year", "both_bear_years_nonneg", "annual_returns_pct", "notes"]


def load_data():
    root = Path(os.environ.get("TRADING_DATA_DIR", "/Users/user/CODE/Coin_Trade/trading_data"))
    etf = pd.read_parquet(root / "external/equities/us/yahoo_daily_us_etf.parquet")
    etf["date"] = pd.to_datetime(etf["date"]).dt.normalize()
    etf = etf[etf.date.le(CUTOFF) & etf.ticker.isin(["SPY", "QQQ", "TLT", "IEF", "SHY", "GLD", "HYG", "LQD"])].copy()
    # Source has harmless duplicate daily records for some other tickers; keep the last source row per key.
    etf = etf.drop_duplicates(["ticker", "date"], keep="last")
    vix = pd.read_parquet(root / "external/equities/vix/cboe_index_history.parquet")
    vix["date"] = pd.to_datetime(vix["date"]).dt.normalize()
    vix = vix[vix.date <= CUTOFF].pivot(index="date", columns="index", values="close")
    vx = pd.read_parquet(root / "external/equities/vix/cboe_vx_futures_by_expiry.parquet")
    vx["trade_date"] = pd.to_datetime(vx["trade_date"]).dt.normalize()
    vx = vx[vx.trade_date <= CUTOFF].sort_values(["trade_date", "expiry_file"]).drop_duplicates("trade_date", keep="first").set_index("trade_date")["settle"]
    return etf, vix, vx


def build_indicators(etf, vix, vx):
    dates = pd.DatetimeIndex(sorted(etf.loc[etf.ticker == "SPY", "date"].unique()))
    close, opn, adjopen, first = {}, {}, {}, {}
    for ticker, g in etf.groupby("ticker"):
        g = g.sort_values("date").set_index("date")
        close[ticker] = g["adj_close"].reindex(dates)
        opn[ticker] = g["open"].reindex(dates)
        # Scale raw open by the close adjustment factor as a dividend-adjusted open proxy.
        adjopen[ticker] = (g["open"] * g["adj_close"] / g["close"]).reindex(dates)
        first[ticker] = g.index.min()
    C = pd.DataFrame(close, index=dates)
    AO = pd.DataFrame(adjopen, index=dates)
    V = vix.reindex(dates)
    vx = vx.reindex(dates)
    v = V.get("VIX", pd.Series(index=dates, dtype=float))
    ret = np.log(C["SPY"] / C["SPY"].shift(1))
    rv20 = ret.rolling(20, min_periods=20).std() * np.sqrt(252) * 100
    spread = v - rv20
    pct504 = lambda s: s.rolling(504, min_periods=504).rank(pct=True) * 100
    # Annualized close-based realized volatility uses the preceding 20 daily returns.
    ind = {
        "VIX": v, "VIX9D": V.get("VIX9D", pd.Series(index=dates, dtype=float)),
        "VIX3M": V.get("VIX3M", pd.Series(index=dates, dtype=float)), "VX": vx,
        "vix_pct504": pct504(v), "chg5": v.pct_change(5, fill_method=None) * 100,
        "chg10": v.pct_change(10, fill_method=None) * 100, "sma20": v.rolling(20, min_periods=20).mean(),
        "rv20": rv20, "spread": spread, "spread_pct504": pct504(spread),
        "rv60": ret.rolling(60, min_periods=60).std() * np.sqrt(252),
        "vix_sma252": v.rolling(252, min_periods=252).mean(),
        "vix_sd252": v.rolling(252, min_periods=252).std(),
    }
    return dates, C, AO, first, ind


def signals(ind):
    d = {k: x for k, x in ind.items()}
    return {
        "VOLREG-L1": (d["VIX"] >= 18, d["VIX"] < 15, "VIX absolute", "VIX>=18 / <15"),
        "VOLREG-L2": (d["VIX"] >= 22, d["VIX"] < 22, "VIX absolute", "VIX>=22 / <22"),
        "VOLREG-L3": (d["vix_pct504"] >= 85, d["vix_pct504"] <= 60, "VIX percentile", "504d percentile >=85 / <=60"),
        "VOLREG-S1": (d["chg5"] >= 40, pd.Series(False, index=d["VIX"].index), "VIX change", "5d change >=40%, fixed 10 sessions"),
        "VOLREG-S2": (d["chg5"] >= 25, d["chg5"] <= 0, "VIX change", "5d change >=25 / <=0%"),
        "VOLREG-S3": (d["chg10"] >= 50, d["VIX"] < d["sma20"], "VIX change", "10d change >=50%; VIX<SMA20"),
        "VOLREG-T1": (d["VIX"] / d["VIX3M"] >= 1, d["VIX"] / d["VIX3M"] < .95, "term structure", "VIX/VIX3M >=1 / <.95"),
        "VOLREG-T2": (d["VIX9D"] / d["VIX"] >= 1.05, d["VIX9D"] / d["VIX"] < 1, "term structure", "VIX9D/VIX >=1.05 / <1"),
        "VOLREG-T3": (d["VX"] < d["VIX"], d["VX"] >= d["VIX"], "term structure", "front VX settle<VIX / >=VIX"),
        "VOLREG-R1": (d["spread"] <= -2, d["spread"] >= 0, "realized-implied", "VIX-RV20 <=-2 / >=0"),
        "VOLREG-R2": (d["spread_pct504"] <= 10, d["spread_pct504"] >= 30, "realized-implied", "spread percentile <=10 / >=30"),
        "VOLREG-V1": (None, None, "volatility targeting", "15% target / RV20; risky clip 0-150%; 5pp band"),
        "VOLREG-V2": (None, None, "volatility targeting", "10% target / RV60; risky clip 0-150%; 5pp band"),
        "VOLREG-M1": (d["VIX"] >= d["vix_sma252"] + 2*d["vix_sd252"], d["VIX"] < d["vix_sma252"] + d["vix_sd252"], "VIX contrarian", "z>=2 risky 100%; z<1 neutral 50%"),
        "VOLREG-M2": (d["VIX"] > 1.5*d["vix_sma252"], d["VIX"] < 1.1*d["vix_sma252"], "VIX contrarian", "VIX>1.5x SMA252 risky 100%; <1.1x SHY"),
    }


def target_path(idea, dates, ind, enter, exit_, start_idx):
    out = np.zeros(len(dates))
    state, hold = False, 0
    for i in range(start_idx, len(dates)):
        e = bool(enter.iloc[i]) if enter is not None and pd.notna(enter.iloc[i]) else False
        x = bool(exit_.iloc[i]) if exit_ is not None and pd.notna(exit_.iloc[i]) else False
        if idea in ("VOLREG-V1", "VOLREG-V2"):
            rv = ind["rv20" if idea.endswith("V1") else "rv60"].iloc[i]
            target = float(np.clip((.15 if idea.endswith("V1") else .10) / rv, 0, 1.5)) if pd.notna(rv) and rv > 0 else 0.0
            out[i] = target
            continue
        if idea == "VOLREG-S1":
            if e:
                state, hold = True, 10
            elif state and hold > 0:
                hold -= 1
            else:
                state = False
        elif e:
            state = True
        elif x:
            state = False
        if idea in ("VOLREG-M1", "VOLREG-M2"):
            if idea == "VOLREG-M1":
                out[i] = 1.0 if state else .5
            else:
                out[i] = 1.0 if state else 0.0
        else:
            out[i] = 0.0 if state else 1.0
    return out


def simulate(idea, dates, C, AO, first, ind, enter, exit_, meta):
    assets = ["SPY", "QQQ", "SHY"]
    required = ["SPY"]
    if idea in ("VOLREG-L1", "VOLREG-L2", "VOLREG-L3", "VOLREG-S1", "VOLREG-S2", "VOLREG-S3", "VOLREG-T1", "VOLREG-T2", "VOLREG-T3", "VOLREG-R1", "VOLREG-R2", "VOLREG-V1", "VOLREG-V2", "VOLREG-M1", "VOLREG-M2"):
        required += ["QQQ", "SHY"]
    common_start = max(first[a] for a in required)
    signal_valid = pd.Series(True, index=dates)
    source_cols = {"L1": ["VIX"], "L2": ["VIX"], "L3": ["vix_pct504"], "S1": ["chg5"], "S2": ["chg5"], "S3": ["chg10", "sma20"], "T1": ["VIX", "VIX3M"], "T2": ["VIX9D", "VIX"], "T3": ["VX", "VIX"], "R1": ["spread"], "R2": ["spread_pct504"], "V1": ["rv20"], "V2": ["rv60"], "M1": ["VIX", "vix_sma252", "vix_sd252"], "M2": ["VIX", "vix_sma252"]}[idea[-2:]]
    for col in source_cols:
        signal_valid &= ind[col].notna()
    good = np.flatnonzero((dates >= common_start) & signal_valid.to_numpy())
    if len(good) == 0:
        raise ValueError("No common valid dates after required series warmup")
    start = int(good[0])
    raw_target = target_path(idea, dates, ind, enter, exit_, start)
    # Signals and RV values are confirmed at close; execute their targets next session.
    execution_target = np.zeros(len(dates))
    execution_target[1:] = raw_target[:-1]
    # Start neutral until a fully formed close signal can be traded next session.
    raw_target[:start] = 0.0
    n = len(dates)
    strat = np.zeros(n); bench = np.zeros(n); orders = switches = 0
    # Begin in cash; the first target allocation is a real purchase and pays entry cost.
    w = np.zeros(3); last_traded_risk = 0.0
    bvalue, value = 100.0, 100.0
    prevclose = np.array([C[a].iloc[start-1] if start else np.nan for a in assets], dtype=float)
    if not np.isfinite(prevclose).all():
        prevclose = np.array([AO[a].iloc[start] for a in assets], dtype=float)
    last_state = None
    for i in range(start, n):
        target_risk = float(np.clip(execution_target[i], 0, 1.5))
        state = target_risk
        if idea in ("VOLREG-V1", "VOLREG-V2"):
            do_trade = abs(target_risk - last_traded_risk) >= .05
        else:
            state = target_risk
            do_trade = last_state is None or state != last_state
        # Apply old holdings' overnight close-to-open returns; then trade at today's open.
        today_open = np.array([AO[a].iloc[i] for a in assets], dtype=float)
        today_close = np.array([C[a].iloc[i] for a in assets], dtype=float)
        if not np.isfinite(today_open).all() or not np.isfinite(today_close).all():
            raise ValueError(f"Missing ETF data in required evaluation range at {dates[i].date()}")
        overnight = today_open / prevclose - 1 if i > start else np.zeros(3)
        value *= 1 + float(np.dot(w, overnight))
        spy_overnight = AO["SPY"].iloc[i] / prevclose[0] - 1 if i > start else 0.0
        bvalue *= 1 + spy_overnight
        if do_trade:
            desired = np.array([target_risk/2, target_risk/2, 1-target_risk])
            turnover = float(np.abs(desired-w).sum())
            value *= 1 - COST * turnover
            orders += int(np.count_nonzero(np.abs(desired-w) > 1e-12))
            if last_state is not None and (abs(state-last_state) >= .05 if idea in ("VOLREG-V1", "VOLREG-V2") else state != last_state): switches += 1
            w = desired
            last_traded_risk = target_risk
            last_state = state
        intraday = today_close / today_open - 1
        value *= 1 + float(np.dot(w, intraday))
        bvalue *= 1 + (today_close[0]/today_open[0]-1)
        if i == start:
            # Pay entry cost for the 100% SPY benchmark purchase at inception.
            bvalue *= 1-COST
        strat[i], bench[i] = value, bvalue
        prevclose = today_close
    # Terminal liquidation cost; benchmark receives the same terminal transaction cost.
    close_target = np.array([execution_target[-1]/2, execution_target[-1]/2, 1-execution_target[-1]])
    value *= 1-COST*float(np.abs(close_target).sum()); bvalue *= 1-COST
    strat[-1] = value; bench[-1] = bvalue
    sr = pd.Series(strat[start:], index=dates[start:]); br = pd.Series(bench[start:], index=dates[start:])
    # Ensure daily start reference is 100 after initial transaction costs for return reporting.
    sr = sr / 100; br = br / 100
    def mdd(s): return (s / s.cummax() - 1).min() * 100
    strat_ret = (sr.iloc[-1] - 1)*100; spy_ret = (br.iloc[-1] - 1)*100
    ann_years = max((dates[-1]-dates[start]).days/365.25, 1/365.25)
    yearly = {}
    annual = {}
    for year in sorted(set(sr.index.year)):
        z, bz = sr[sr.index.year == year], br[br.index.year == year]
        if len(z) > 1:
            annual[str(year)] = round((z.iloc[-1]/z.iloc[0]-1)*100, 4)
    for year in (2018, 2022):
        z = sr[sr.index.year == year]
        bz = br[br.index.year == year]
        yearly[year] = ((z.iloc[-1]/z.iloc[0]-1)*100 if len(z)>1 else np.nan,
                        (bz.iloc[-1]/bz.iloc[0]-1)*100 if len(bz)>1 else np.nan)
    note = "adj_close 근사, 분배금 완전조정 아님; 오버나이트는 기존 보유, 시가 후 수익은 체결 후 목표비중 적용. 탐색 결과로 승격 근거 아님."
    terminal_orders = int(np.count_nonzero(np.abs(close_target) > 1e-12))
    return {"idea_id": idea, "family": meta[2], "params": meta[3], "start_date": dates[start].date().isoformat(), "end_date": dates[-1].date().isoformat(), "n_switches": switches, "n_orders": orders+terminal_orders, "strategy_cum_return_pct": strat_ret, "spy_cum_return_pct": spy_ret, "excess_return_pp": strat_ret-spy_ret, "strategy_mdd_pct": mdd(sr), "spy_mdd_pct": mdd(br), "mdd_improvement_pp": mdd(sr)-mdd(br), "ret_2018_pct": yearly[2018][0], "spy_ret_2018_pct": yearly[2018][1], "ret_2022_pct": yearly[2022][0], "spy_ret_2022_pct": yearly[2022][1], "switches_per_year": switches/ann_years, "both_bear_years_nonneg": bool(np.isfinite(yearly[2018][0]) and np.isfinite(yearly[2022][0]) and yearly[2018][0]>=0 and yearly[2022][0]>=0), "annual_returns_pct": annual, "notes": note}


def write_results(rows):
    with (HERE / "RESULTS.csv").open("w", newline="") as f:
        f.write(LABEL + "\n")
        writer = csv.DictWriter(f, fieldnames=COLS); writer.writeheader()
        writer.writerows(rows)


def write_ranked(rows):
    scored = []
    for r in rows:
        r["composite_score"] = r["excess_return_pp"] + .5*r["mdd_improvement_pp"]
        scored.append(r)
    top = sorted(scored, key=lambda r: r["composite_score"], reverse=True)[:10]
    out = ["# ETF 변동성 레짐 상위 10개 - 탐색 스크리닝", "", f"> {LABEL}", "", "순위 점수 = 초과수익(pp) + 0.5 × MDD 개선(pp). 거래 비용은 비중 변경 절대값 합에 편도 6bp를 적용했다. 수익은 adj_close 근사, 분배금 완전조정 아님.", "", "## 상위 10개", "", "|순위|아이디어|가족|점수|전환|편도 주문|초과수익 pp|MDD 개선 pp|2018 전략/SPY %|2022 전략/SPY %|약세장 모두 양수|", "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for i,r in enumerate(top,1):
        flag = "✅ True" if r["both_bear_years_nonneg"] else "False"
        out.append(f"|{i}|{r['idea_id']}|{r['family']}|{r['composite_score']:.2f}|{r['n_switches']}|{r['n_orders']}|{r['excess_return_pp']:.2f}|{r['mdd_improvement_pp']:.2f}|{r['ret_2018_pct']:.2f}/{r['spy_ret_2018_pct']:.2f}|{r['ret_2022_pct']:.2f}/{r['spy_ret_2022_pct']:.2f}|{flag}|")
    out += ["", "## 상위 3개 해석", ""]
    for i,r in enumerate(top[:3],1):
        out.append(f"{i}. **{r['idea_id']} ({r['family']})** — {r['params']}. 레짐 전환 {r['n_switches']}회, 편도 주문 {r['n_orders']}건, 동일 구간 SPY 대비 초과수익 {r['excess_return_pp']:.2f}pp, MDD 개선 {r['mdd_improvement_pp']:.2f}pp. 2018 전략 {r['ret_2018_pct']:.2f}% / SPY {r['spy_ret_2018_pct']:.2f}%, 2022 전략 {r['ret_2022_pct']:.2f}% / SPY {r['spy_ret_2022_pct']:.2f}%.")
    flags=[r for r in scored if r["both_bear_years_nonneg"]]
    out += ["", "## 2018·2022 모두 비음수인 항목", "", (", ".join(f"**{r['idea_id']}** (2018 {r['ret_2018_pct']:.2f}%, 2022 {r['ret_2022_pct']:.2f}%)" for r in flags) if flags else "해당 없음."), "", "## 연도별 수익률: 상위 10개", "", "표의 연도 값은 연말 평가자산/전년말 평가자산으로 계산한 달력연도 수익률이며 첫/마지막 부분연도는 부분 구간이다.", "", "|아이디어|"+"|".join(str(y) for y in range(2018,2027))+"|", "|---|"+"|".join(["---:"]*9)+"|"]
    for r in top:
        # Annual returns are reconstructed during report generation from result-path records where available.
        annual = r.get("annual_returns_pct", {})
        out.append(f"|{r['idea_id']}|"+"|".join(f"{annual.get(str(y), float('nan')):.2f}" if str(y) in annual else "—" for y in range(2018,2027))+"|")
    out += ["", "## 해석 한계", "", "- 이 결과는 탐색 전용이며 G-게이트·장부에 포함되지 않는다. 다중검정 보정, 합성 테스트, 워크포워드와 별도 TRAIN 검증을 하지 않았다.", "- 평가 표본은 아이디어별 공통 입력 및 ETF 상장일 이후부터 2026-06-01까지다. 2018·2022 값이 시작일/시계열 결측으로 없으면 NaN으로 표시한다.", "- 편도 주문은 목표 포트폴리오 대비 자산별 비중 차이에 대해 산정한다. 분배금 조정은 adj_close 근사다.", "- 순위는 지정된 조합점수의 기계적 내림차순이며 전략 우위의 통계적 증거가 아니다."]
    (HERE / "RANKED_TOP10.md").write_text("\n".join(out)+"\n")


def main():
    etf, vix, vx = load_data()
    dates,C,AO,first,ind=build_indicators(etf,vix,vx)
    sig=signals(ind); rows=[]
    for idea in IDEAS:
        enter,exit_,family,params=sig[idea]
        try:
            rows.append(simulate(idea,dates,C,AO,first,ind,enter,exit_,sig[idea]))
        except Exception as exc:
            rows.append({"idea_id":idea,"family":family,"params":params,"start_date":"","end_date":"2026-06-01","n_switches":0,"n_orders":0,"strategy_cum_return_pct":np.nan,"spy_cum_return_pct":np.nan,"excess_return_pp":np.nan,"strategy_mdd_pct":np.nan,"spy_mdd_pct":np.nan,"mdd_improvement_pp":np.nan,"ret_2018_pct":np.nan,"spy_ret_2018_pct":np.nan,"ret_2022_pct":np.nan,"spy_ret_2022_pct":np.nan,"switches_per_year":np.nan,"both_bear_years_nonneg":False,"annual_returns_pct":{},"notes":f"FAILED: {type(exc).__name__}: {exc}"})
    write_results(rows); write_ranked(rows)
    print(f"rows={len(rows)} scoreable={sum(not str(r['notes']).startswith('FAILED:') for r in rows)}")
    print(f"date_cutoff={CUTOFF.date()} trading_data={os.environ.get('TRADING_DATA_DIR')}")


if __name__ == "__main__":
    main()
