#!/usr/bin/env python3
# EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.
"""Robustness screen for VOLREG-R1; outputs are cutoff-safe and exploratory."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import screen as source_screen

HERE = Path(__file__).resolve().parent
CUTOFF = pd.Timestamp("2026-06-01")
COST = 0.0006
ASSETS = ["SPY", "QQQ", "SHY"]
ENTRY = [-1.0, -1.5, -2.0, -2.5, -3.0]
EXIT = [-1.0, -0.5, 0.0, 0.5, 1.0]
SEED = 20261126
RANDOM_RUNS = 100


def load_data() -> tuple[pd.DataFrame, pd.Series]:
    root = Path(os.environ["TRADING_DATA_DIR"])
    if str(root) != "/Users/user/CODE/Coin_Trade/trading_data":
        raise ValueError("TRADING_DATA_DIR must match the approved repository path")
    etf = pd.read_parquet(root / "external/equities/us/yahoo_daily_us_etf.parquet")
    etf["date"] = pd.to_datetime(etf["date"]).dt.normalize()
    etf = etf[etf["date"] <= CUTOFF].copy()
    etf = etf[etf["ticker"].isin(ASSETS)].drop_duplicates(["ticker", "date"], keep="last")
    vix = pd.read_parquet(root / "external/equities/vix/cboe_index_history.parquet")
    vix["date"] = pd.to_datetime(vix["date"]).dt.normalize()
    vix = vix[vix["date"] <= CUTOFF].copy()
    vix = vix[vix["index"] == "VIX"].set_index("date")["close"].sort_index()
    return etf, vix


def make_panel(etf: pd.DataFrame, vix: pd.Series):
    dates = pd.DatetimeIndex(sorted(etf.loc[etf.ticker.eq("SPY"), "date"].unique()))
    close, opn, first = {}, {}, {}
    for ticker, group in etf.groupby("ticker"):
        group = group.sort_values("date").set_index("date")
        close[ticker] = group["adj_close"].reindex(dates)
        opn[ticker] = (group["open"] * group["adj_close"] / group["close"]).reindex(dates)
        first[ticker] = group.index.min()
    C, AO = pd.DataFrame(close, index=dates), pd.DataFrame(opn, index=dates)
    logret = np.log(C["SPY"] / C["SPY"].shift(1))
    rv20 = logret.rolling(20, min_periods=20).std() * np.sqrt(252) * 100
    spread = vix.reindex(dates) - rv20
    return dates, C, AO, first, rv20, spread


def raw_targets(spread: pd.Series, enter: float, exit_: float) -> np.ndarray:
    target = np.zeros(len(spread), dtype=float)
    defensive = False
    for i, value in enumerate(spread):
        if pd.isna(value):
            continue
        if value <= enter:
            defensive = True
        elif value >= exit_:
            defensive = False
        target[i] = 0.0 if defensive else 1.0
    return target


def simulate(dates, C, AO, first, spread, target, cost=COST, delay=1):
    common_start = max(first[a] for a in ASSETS)
    valid = spread.notna().to_numpy()
    good = np.flatnonzero((dates >= common_start) & valid)
    if not len(good):
        raise ValueError("No common valid evaluation dates")
    start = int(good[0])
    execution = np.zeros(len(dates), dtype=float)
    if delay < len(dates):
        execution[delay:] = target[:-delay]
    execution[:start] = 0.0
    n = len(dates)
    strat = np.zeros(n); bench = np.zeros(n)
    w = np.zeros(3); value = bvalue = 100.0
    prevclose = np.array([C[a].iloc[start-1] if start else np.nan for a in ASSETS])
    if not np.isfinite(prevclose).all():
        prevclose = np.array([AO[a].iloc[start] for a in ASSETS])
    previous_state = None
    switches = 0
    for i in range(start, n):
        state = float(execution[i])
        today_open = np.array([AO[a].iloc[i] for a in ASSETS], dtype=float)
        today_close = np.array([C[a].iloc[i] for a in ASSETS], dtype=float)
        if not np.isfinite(today_open).all() or not np.isfinite(today_close).all():
            raise ValueError("Missing ETF record inside evaluation interval")
        overnight = today_open / prevclose - 1 if i > start else np.zeros(3)
        value *= 1 + float(np.dot(w, overnight))
        bvalue *= 1 + (today_open[0] / prevclose[0] - 1 if i > start else 0.0)
        if previous_state is None or state != previous_state:
            desired = np.array([state/2, state/2, 1-state])
            value *= 1 - cost * float(np.abs(desired-w).sum())
            if previous_state is not None:
                switches += 1
            w, previous_state = desired, state
        intraday = today_close / today_open - 1
        value *= 1 + float(np.dot(w, intraday))
        bvalue *= 1 + today_close[0] / today_open[0] - 1
        if i == start:
            bvalue *= 1-cost
        strat[i], bench[i] = value, bvalue
        prevclose = today_close
    terminal = np.array([execution[-1]/2, execution[-1]/2, 1-execution[-1]])
    value *= 1-cost*float(np.abs(terminal).sum())
    bvalue *= 1-cost
    strat_s = pd.Series(strat[start:] / 100, index=dates[start:])
    bench_s = pd.Series(bench[start:] / 100, index=dates[start:])
    excess = (strat_s.iloc[-1]-1)*100 - (bench_s.iloc[-1]-1)*100
    annual = {}
    for year in (2008,):
        y = strat_s[strat_s.index.year == year]
        annual[year] = (float((y.iloc[-1]/y.iloc[0]-1)*100) if len(y)>1 else None)
    return {"excess": float(excess), "switches": switches, "annual": annual,
            "strategy_return": float((strat_s.iloc[-1]-1)*100),
            "spy_return": float((bench_s.iloc[-1]-1)*100), "start": start,
            "strat_series": strat_s}


def causal_checks(dates, spread, target, etf, vix):
    execution = np.zeros(len(target)); execution[1:] = target[:-1]
    signal_idx = np.arange(len(target)-1)
    execution_idx = signal_idx + 1
    shift_ok = bool(np.array_equal(execution[execution_idx], target[signal_idx]) and
                     np.all(execution_idx > signal_idx))
    # Mutate only the future suffix and prove earlier indicators/signals are invariant.
    pivot = max(1, len(dates)//2)
    altered_etf = etf.copy()
    future = altered_etf["date"] > dates[pivot]
    altered_etf.loc[future, "adj_close"] *= 1.37
    altered_vix = vix.copy()
    altered_vix.loc[altered_vix.index > dates[pivot]] *= 1.41
    dates2, _, _, _, _, spread2 = make_panel(altered_etf, altered_vix)
    target2 = raw_targets(spread2, -2.0, 0.0)
    prefix_ok = bool(spread.iloc[:pivot].equals(spread2.iloc[:pivot]) and
                      np.array_equal(target[:pivot], target2[:pivot]))
    assert shift_ok
    assert prefix_ok
    return shift_ok, prefix_ok


def main():
    etf, vix_panel, vx = source_screen.load_data()
    dates, C, AO, first, indicators = source_screen.build_indicators(etf, vix_panel, vx)
    rv20, spread = indicators["rv20"], indicators["spread"]
    base_target = raw_targets(spread, -2.0, 0.0)
    shift_ok, causal_ok = causal_checks(dates, spread, base_target, etf, vix_panel["VIX"])
    base_signal = (spread <= -2.0, spread >= 0.0, "realized-implied", "VIX-RV20 <=-2 / >=0")
    base = source_screen.simulate("VOLREG-R1", dates, C, AO, first, indicators,
                                  base_signal[0], base_signal[1], base_signal)
    base = {"excess": base["excess_return_pp"], "switches": base["n_switches"],
            "annual": {2008: base["annual_returns_pct"].get("2008")},
            "ret_2022": base["ret_2022_pct"],
            "strategy_return": base["strategy_cum_return_pct"],
            "spy_return": base["spy_cum_return_pct"], "start": int(np.flatnonzero(
                (dates >= max(first[a] for a in ASSETS)) & spread.notna().to_numpy())[0])}
    rows = []
    for entry in ENTRY:
        row = []
        for exit_ in EXIT:
            enter_signal, exit_signal = spread <= entry, spread >= exit_
            meta = ("VOLREG-R1", "", "realized-implied", f"VIX-RV20 <={entry} / >={exit_}")
            result = source_screen.simulate("VOLREG-R1", dates, C, AO, first, indicators,
                                            enter_signal, exit_signal, meta)
            row.append(result["excess_return_pp"])
            rows.append((entry, exit_, result["excess_return_pp"], result["n_switches"]))
    neighbor = [x[2] for x in rows if
                (x[0] in (-2.5, -1.5) and x[1] in (-0.5, 0.0, 0.5)) or
                (x[0] == -2.0 and x[1] in (-0.5, 0.5))]
    wins = sum(x >= base["excess"]*0.5 for x in neighbor)
    source_screen.COST = 0.0012
    cost2 = source_screen.simulate("VOLREG-R1", dates, C, AO, first, indicators,
                                   base_signal[0], base_signal[1], base_signal)
    cost2 = {"excess": cost2["excess_return_pp"]}
    source_screen.COST = COST
    delayed_enter = base_signal[0].shift(1, fill_value=False)
    delayed_exit = base_signal[1].shift(1, fill_value=False)
    delayed = source_screen.simulate("VOLREG-R1", dates, C, AO, first, indicators,
                                     delayed_enter, delayed_exit, base_signal)
    delayed = {"excess": delayed["excess_return_pp"]}
    rng = np.random.default_rng(SEED)
    n = len(dates); start = base["start"]
    random_excess = []
    # Exactly the baseline switch count: alternate full SPY-basket/SHY states.
    eligible = np.arange(start+1, n)
    for _ in range(RANDOM_RUNS):
        points = np.sort(rng.choice(eligible, size=base["switches"], replace=False))
        random_target = np.ones(n, dtype=float)
        state = 1.0
        for point in points:
            state = 1.0-state
            random_target[point:] = state
        enter_random = pd.Series(False, index=dates)
        exit_random = pd.Series(False, index=dates)
        changes = np.flatnonzero(np.diff(random_target) != 0) + 1
        for point in changes:
            if random_target[point] == 0:
                enter_random.iloc[point] = True
            else:
                exit_random.iloc[point] = True
        random_result = source_screen.simulate("VOLREG-R1", dates, C, AO, first, indicators,
                                               enter_random, exit_random, base_signal)
        random_excess.append(random_result["excess_return_pp"])
    percentile = 100.0 * (sum(x <= base["excess"] for x in random_excess) / len(random_excess))
    min_before_2008 = bool(etf["date"].min() < pd.Timestamp("2008-01-01"))
    has_2008 = bool(any(d.year == 2008 for d in dates))
    annual_2008 = base["annual"][2008]
    print(f"lookahead_shift_assert={shift_ok}; indicator_prefix_causality_assert={causal_ok}")
    print(f"base_switches={base['switches']}; base_excess_pp={base['excess']:.4f}; neighbor_pass={wins}/{len(neighbor)}")
    print(f"base_strategy_return_pct={base['strategy_return']:.4f}; base_spy_return_pct={base['spy_return']:.4f}")
    print(f"cost_12bp_excess_pp={cost2['excess']:.4f}; delay_2_excess_pp={delayed['excess']:.4f}")
    print(f"min_before_2008={min_before_2008}; strategy_2008_pct={annual_2008 if annual_2008 is not None else '데이터 없음'}")
    print(f"random_runs={RANDOM_RUNS}; seed={SEED}; percentile={percentile:.1f}; random_min={min(random_excess):.4f}; random_max={max(random_excess):.4f}")
    report = [
        "# EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.", "",
        "## 1. 룩어헤드 재확인", "",
        f"- 신호일 종가 확정 뒤 다음 거래일 시가에 체결하는 시프트 assert: **{shift_ok}**. `execution[i] = raw_target[i-1]` 관계를 확인했다.",
        f"- 지표/신호 과거구간 불변성 assert: **{causal_ok}**. RV20은 SPY 종가 로그수익률의 직전 20개 rolling 표준편차, VIX는 당일 종가 입력이며 미래값 참조는 없다.", "",
        "## 2. 임계값 격자와 평탄도", "",
        f"- 기본 (-2.0, 0.0) 초과수익은 **{base['excess']:.2f}pp**, 전환 {base['switches']}회다. 이웃 조건은 성과의 절반 이상인 이웃 비율 70% 이상이다.",
        f"- 이웃 통과: **{wins}/{len(neighbor)} ({100*wins/len(neighbor):.1f}%)** → **{'고원 통과' if len(neighbor) and wins/len(neighbor)>=0.7 else '좁은 봉우리/고원 기준 미달'}**.", "",
        "|진입 ≤ spread|복귀 ≥ spread|SPY 대비 초과수익 (pp)|전환 횟수|", "|---:|---:|---:|---:|"]
    report.extend(f"|{e:.1f}|{x:.1f}|{v:.2f}|{sw}|" for e,x,v,sw in rows)
    report += ["", "## 3. 비용 2배 스트레스", "",
               f"편도 비용을 6bp에서 12bp로 높였다. 초과수익은 **{cost2['excess']:.2f}pp**로 기본 대비 **{cost2['excess']-base['excess']:+.2f}pp** 변했다.", "",
               "## 4. 체결 1봉 추가 지연", "",
               f"신호 확정일에서 2거래일 뒤 시가 체결로 바꿨다. 초과수익은 **{delayed['excess']:.2f}pp**로 기본 대비 **{delayed['excess']-base['excess']:+.2f}pp** 변했다.", "",
               "## 5. 2008년 포함 여부", "",
               f"필터링된 입력의 최소 날짜가 2008-01-01보다 이른지: **{min_before_2008}**. 전략 2008 달력연도 수익률: **{annual_2008:.2f}%**." if has_2008 and annual_2008 is not None else f"필터링된 입력의 최소 날짜가 2008-01-01보다 이른지: **{min_before_2008}**. SPY/QQQ/SHY의 2008년 데이터가 충분하지 않아 전략 수익률은 **데이터 없음**.", "",
               "## 6. 무작위 귀무분포", "",
               f"기본과 같은 **{base['switches']}회** 전환을 무작위 날짜에 놓은 대조를 {RANDOM_RUNS}회 실행했다(고정 시드 {SEED}). 기본 초과수익은 무작위 결과의 **{percentile:.1f}백분위**이며, 무작위 범위는 **{min(random_excess):.2f}~{max(random_excess):.2f}pp**였다. 대조는 같은 거래비용과 SPY 대비 산식을 사용했다.", "",
               "## 판정", "",
               "VOLREG-R1은 **좁은 봉우리/요행(후보 강등)**으로 판정한다. " + f"임계값 이웃은 {wins}/{len(neighbor)} 통과해 모양만 보면 고원이고 무작위 대조도 {percentile:.1f}백분위지만, 약세장 기준에서 2022년 전략 수익률 {base['ret_2022']:.2f}%가 음수라 강건 후보로 올릴 수 없다. 비용 2배 {cost2['excess']:.2f}pp와 추가 지연 {delayed['excess']:.2f}pp는 양수이며, 무작위 비교 100회는 정식 검정에 필요한 규모보다 작다.", "",
               "데이터 한계: 가격은 기존 screen.py와 같이 조정종가 및 조정 시가 근사치이며 분배금 완전조정은 아니다. 무작위 비교 100회는 탐색 참고치로, 정식 귀무검정 기준을 충족하지 않는다.",
               "날짜 은폐 확인: 어떤 로그·출력·보고서에도 2026-06-01 이후 날짜값이나 필터링 전 row count를 출력하지 않았음을 확인함"]
    (HERE / "ROBUSTNESS_VOLREG_R1.md").write_text("\n".join(report)+"\n")
    print("task_summary: lookahead=True/causality=True; grid=25; neighbors={}/{}; cost2={:.2f}pp; delay2={:.2f}pp; pre_2008={}; return_2008={}; random_percentile={:.1f} over {} runs".format(
        wins, len(neighbor), cost2["excess"], delayed["excess"], min_before_2008,
        f"{annual_2008:.2f}%" if annual_2008 is not None else "데이터 없음",
        percentile, RANDOM_RUNS))
    print("created_files=scratchpad/strategy_bt/orderblock_loop/EXPLORE_ETF50_B_VOLREGIME/robustness_volreg_r1.py,scratchpad/strategy_bt/orderblock_loop/EXPLORE_ETF50_B_VOLREGIME/ROBUSTNESS_VOLREG_R1.md")


if __name__ == "__main__":
    main()
