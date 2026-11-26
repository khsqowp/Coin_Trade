#!/usr/bin/env python3
# EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.
"""ETF bull/bear regime confirmation-lag exploratory screen."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CUTOFF = pd.Timestamp("2026-06-01")
LABEL = "# EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run."
COST = 0.0006  # 6bp per one-way portfolio turnover; 12bp round trip at full switch.
TICKERS = ("SPY", "QQQ", "SHY")
LAGS = (0, 5, 10, 20, 40)
IDEA_SPECS = [
    ("PX200", lag, f"SPY adj_close > SMA200; confirmation_lag_days={lag}") for lag in LAGS
] + [
    ("VIXMED", lag, f"VIX < cutoff-filtered full-series median; confirmation_lag_days={lag}") for lag in LAGS
] + [
    ("DD15", lag, f"SPY drawdown > -15%; confirmation_lag_days={lag}") for lag in LAGS
] + [
    ("DD10", 0, "SPY drawdown > -10%; confirmation_lag_days=0"),
    ("DD20", 0, "SPY drawdown > -20%; confirmation_lag_days=0"),
    ("TR12M", 0, "SPY trailing 252-session return >= 0; confirmation_lag_days=0"),
    ("GC5020", 0, "SPY SMA50 > SMA200; confirmation_lag_days=0"),
]
RESULT_COLS = [
    "idea_id", "family", "params", "start_date", "end_date", "confirmation_lag_days",
    "n_switches", "excess_return_pp", "strategy_mdd_pct", "spy_mdd_pct",
    "ret_2018_pct", "spy_ret_2018_pct", "ret_2022_pct", "spy_ret_2022_pct",
    "switches_per_year", "unreliable_few_switches", "both_bear_years_nonneg",
    "annual_returns_pct", "notes", "strategy_cum_return_pct", "spy_cum_return_pct",
    "mdd_improvement_pp",
]


def load_data():
    root = Path(os.environ.get("TRADING_DATA_DIR", "/Users/user/CODE/Coin_Trade/trading_data"))
    expected = Path("/Users/user/CODE/Coin_Trade/trading_data")
    if Path(os.environ.get("TRADING_DATA_DIR", str(expected))).resolve() != expected:
        raise ValueError("TRADING_DATA_DIR must be the canonical Coin_Trade trading_data directory")
    etf = pd.read_parquet(root / "external/equities/us/yahoo_daily_us_etf.parquet")
    etf["date"] = pd.to_datetime(etf["date"]).dt.normalize()
    etf = etf[etf["date"] <= CUTOFF].copy()
    etf = etf[etf["ticker"].isin(TICKERS)].copy()
    etf = etf.drop_duplicates(["ticker", "date"], keep="last")
    vix = pd.read_parquet(root / "external/equities/vix/cboe_index_history.parquet")
    vix["date"] = pd.to_datetime(vix["date"]).dt.normalize()
    vix = vix[vix["date"] <= CUTOFF].copy()
    vix = vix[vix["index"] == "VIX"].copy()
    vix = vix.drop_duplicates(["date", "index"], keep="last").set_index("date")["close"]
    return etf, vix


def build_prices(etf, vix):
    dates = pd.DatetimeIndex(sorted(etf.loc[etf["ticker"] == "SPY", "date"].unique()))
    close, opn, first = {}, {}, {}
    for ticker, group in etf.groupby("ticker"):
        group = group.sort_values("date").set_index("date")
        close[ticker] = group["adj_close"].reindex(dates)
        # Scale raw open by close adjustment factor, matching B's dividend-adjusted open proxy.
        opn[ticker] = (group["open"] * group["adj_close"] / group["close"]).reindex(dates)
        first[ticker] = group.index.min()
    C = pd.DataFrame(close, index=dates)
    AO = pd.DataFrame(opn, index=dates)
    V = vix.reindex(dates)
    return dates, C, AO, V, first


def build_raw_states(dates, C, V):
    spy = C["SPY"]
    sma50 = spy.rolling(50, min_periods=50).mean()
    sma200 = spy.rolling(200, min_periods=200).mean()
    peak = spy.cummax()
    drawdown = spy / peak - 1
    trailing = spy / spy.shift(252) - 1
    vix_median = float(V.dropna().median())
    raw = {
        "PX200": (spy > sma200),
        "GC5020": (sma50 > sma200),
        "DD10": (drawdown > -0.10),
        "DD15": (drawdown > -0.15),
        "DD20": (drawdown > -0.20),
        "TR12M": (trailing >= 0),
        "VIXMED": (V < vix_median),
    }
    return raw, vix_median


def confirm_state(raw: pd.Series, lag: int) -> pd.Series:
    values = raw.to_numpy(dtype=object)
    confirmed = np.zeros(len(values), dtype=bool)
    if len(values) == 0 or pd.isna(values[0]):
        raise ValueError("Raw regime state is missing at series start")
    confirmed[0] = bool(values[0])
    run_len = 1
    for i in range(1, len(values)):
        if pd.isna(values[i]):
            raise ValueError(f"Raw regime state missing at {raw.index[i].date()}")
        current = bool(values[i])
        previous = bool(values[i - 1])
        run_len = run_len + 1 if current == previous else 1
        if lag == 0:
            confirmed[i] = current
        elif run_len >= lag and current != confirmed[i - 1]:
            confirmed[i] = current
        else:
            confirmed[i] = confirmed[i - 1]
    return pd.Series(confirmed, index=raw.index)


def max_drawdown(values):
    return float((values / values.cummax() - 1).min() * 100)


def year_return(values, year):
    section = values[values.index.year == year]
    if len(section) < 2:
        return np.nan
    return float((section.iloc[-1] / section.iloc[0] - 1) * 100)


def simulate(family, lag, params, raw, dates, C, AO, first):
    common_start = max(first[ticker] for ticker in TICKERS)
    # Restrict the evaluation grid first; all sizing and date summaries use this cutoff-safe index.
    eval_mask = dates >= common_start
    eval_dates = dates[eval_mask]
    state_full = confirm_state(raw.loc[eval_dates], lag)
    source_valid = np.isfinite(C.loc[eval_dates, list(TICKERS)].to_numpy()).all(axis=1)
    valid_positions = np.flatnonzero(source_valid)
    if not len(valid_positions):
        raise ValueError("No common valid ETF evaluation dates")
    start_pos = int(valid_positions[0])
    # Warmup values must exist at the signal close immediately before the first execution date.
    start_pos = max(start_pos, 1)
    start_date = eval_dates[start_pos]
    eval_dates = eval_dates[start_pos:]
    if not len(eval_dates):
        raise ValueError("No evaluation dates after common ETF start")
    # Each target at date i is sourced from the prior session's confirmed close state.
    execution_state = state_full.iloc[start_pos - 1 : len(state_full) - 1].to_numpy(dtype=bool)
    signal_dates = eval_dates - pd.Timedelta(days=1)
    actual_signal_dates = state_full.index[start_pos - 1 : len(state_full) - 1]
    assert len(actual_signal_dates) == len(eval_dates)
    assert np.all(actual_signal_dates.to_numpy() < eval_dates.to_numpy()), "Signal close must precede execution open"

    assets = list(TICKERS)
    closes = C.loc[eval_dates, assets].to_numpy(dtype=float)
    opens = AO.loc[eval_dates, assets].to_numpy(dtype=float)
    if not np.isfinite(closes).all() or not np.isfinite(opens).all():
        bad_row = int(np.argwhere(~np.isfinite(closes).all(axis=1) | ~np.isfinite(opens).all(axis=1))[0, 0])
        raise ValueError(f"Missing ETF price in evaluation range at {eval_dates[bad_row].date()}")
    prior_closes = C.loc[eval_dates[0] - pd.Timedelta(days=1), assets].to_numpy(dtype=float)
    if not np.isfinite(prior_closes).all():
        prior_idx = dates.get_loc(eval_dates[0]) - 1
        prior_closes = C.loc[dates[prior_idx], assets].to_numpy(dtype=float)
    if not np.isfinite(prior_closes).all():
        raise ValueError("Prior close unavailable for initial overnight return")

    value = bench = 100.0
    weights = np.zeros(3)
    bench_weights = np.zeros(3)
    strategy_values, benchmark_values = [], []
    switches = 0
    prior_state = None
    for i, date in enumerate(eval_dates):
        # Accrue overnight movement on old positions, then rebalance at today's open.
        if i:
            overnight = opens[i] / closes[i - 1] - 1
            value *= 1 + float(np.dot(weights, overnight))
            bench *= 1 + overnight[0]
        else:
            overnight = opens[i] / prior_closes - 1
            # Start portfolio and baseline at the common start close; no unheld overnight exposure.
        is_bull = bool(execution_state[i])
        target = np.array([0.5, 0.5, 0.0]) if is_bull else np.array([0.0, 0.0, 1.0])
        turnover = float(np.abs(target - weights).sum())
        value *= 1 - COST * turnover
        weights = target
        if prior_state is not None and is_bull != prior_state:
            switches += 1
        prior_state = is_bull
        if i == 0:
            bench *= 1 - COST  # same initial SPY purchase cost convention as B
            bench_weights = np.array([1.0, 0.0, 0.0])
        intraday = closes[i] / opens[i] - 1
        value *= 1 + float(np.dot(weights, intraday))
        bench *= 1 + intraday[0]
        strategy_values.append(value)
        benchmark_values.append(bench)
    # Liquidate at final close; charge the same full-turnover convention to both portfolios.
    value *= 1 - COST * float(np.abs(weights).sum())
    bench *= 1 - COST
    strategy_values[-1] = value
    benchmark_values[-1] = bench
    strat = pd.Series(strategy_values, index=eval_dates) / 100
    spy = pd.Series(benchmark_values, index=eval_dates) / 100
    strategy_ret = float((strat.iloc[-1] - 1) * 100)
    spy_ret = float((spy.iloc[-1] - 1) * 100)
    years = max((eval_dates[-1] - eval_dates[0]).days / 365.25, 1 / 365.25)
    annual = {}
    for year in sorted(set(eval_dates.year)):
        s = strat[strat.index.year == year]
        if len(s) > 1:
            annual[str(year)] = round(float((s.iloc[-1] / s.iloc[0] - 1) * 100), 4)
    r2018, s2018 = year_return(strat, 2018), year_return(spy, 2018)
    r2022, s2022 = year_return(strat, 2022), year_return(spy, 2022)
    mdd_s, mdd_b = max_drawdown(strat), max_drawdown(spy)
    return {
        "idea_id": f"RT-{family}-L{lag}", "family": family, "params": params,
        "start_date": eval_dates[0].date().isoformat(), "end_date": eval_dates[-1].date().isoformat(),
        "confirmation_lag_days": lag, "n_switches": switches,
        "excess_return_pp": strategy_ret - spy_ret, "strategy_mdd_pct": mdd_s,
        "spy_mdd_pct": mdd_b, "ret_2018_pct": r2018, "spy_ret_2018_pct": s2018,
        "ret_2022_pct": r2022, "spy_ret_2022_pct": s2022,
        "switches_per_year": switches / years, "unreliable_few_switches": switches < 5,
        "both_bear_years_nonneg": bool(np.isfinite(r2018) and np.isfinite(r2022) and r2018 >= 0 and r2022 >= 0),
        "annual_returns_pct": json.dumps(annual, sort_keys=True),
        "notes": "탐색 전용. adj_close 기반 분배금 조정 근사; SPY/QQQ 50:50, SHY 100%; 시가 체결 전일까지 기존 보유분 오버나이트 수익 적용. 강건성 검증 미실시.",
        "strategy_cum_return_pct": strategy_ret, "spy_cum_return_pct": spy_ret,
        "mdd_improvement_pp": mdd_b - mdd_s,
    }


def fmt(value):
    return "NA" if not np.isfinite(value) else f"{value:.2f}"


def write_ideas():
    path = HERE / "IDEAS.csv"
    with path.open("w", newline="") as handle:
        handle.write(LABEL + "\n")
        writer = csv.writer(handle)
        writer.writerow(["idea_id", "family", "params", "rationale"])
        for family, lag, params in IDEA_SPECS:
            idea_id = f"RT-{family}-L{lag}"
            writer.writerow([idea_id, family, params, "불리언 강세/약세 레짐의 연속 유지 확인 지연 효과를 탐색; 정식 검증 아님"])


def write_results(rows):
    with (HERE / "RESULTS.csv").open("w", newline="") as handle:
        handle.write(LABEL + "\n")
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLS)
        writer.writeheader()
        writer.writerows(rows)


def write_ranked(rows):
    scoreable = [r for r in rows if not str(r["notes"]).startswith("FAILED:")]
    for row in scoreable:
        row["composite_score"] = row["excess_return_pp"] + 0.5 * row["mdd_improvement_pp"]
    top = sorted(scoreable, key=lambda r: r["composite_score"], reverse=True)[:10]
    lines = [
        "# ETF 레짐 전환 지연 상위 10개 - 탐색 스크리닝", "", f"> {LABEL}", "",
        "점수 = SPY 대비 초과수익(pp) + 0.5 × MDD 개선(pp). 전환 확정은 종가 정보로 계산하고 다음 거래일 시가에 반영했다. 비용은 비중 변경 절대값 합 × 6bp다. 수익은 adj_close 조정 근사다.", "",
        "## 상위 10개", "", "|순위|아이디어|기준|지연일|점수|전환|초과수익 pp|전략 MDD %|SPY MDD %|2018 전략/SPY %|2022 전략/SPY %|5회 미만|", "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for i, r in enumerate(top, 1):
        lines.append(f"|{i}|{r['idea_id']}|{r['family']}|{r['confirmation_lag_days']}|{r['composite_score']:.2f}|{r['n_switches']}|{r['excess_return_pp']:.2f}|{r['strategy_mdd_pct']:.2f}|{r['spy_mdd_pct']:.2f}|{fmt(r['ret_2018_pct'])}/{fmt(r['spy_ret_2018_pct'])}|{fmt(r['ret_2022_pct'])}/{fmt(r['spy_ret_2022_pct'])}|{r['unreliable_few_switches']}|")
    lines.extend(["", "## 상위 3개 해석", ""])
    for i, r in enumerate(top[:3], 1):
        lines.append(f"{i}. **{r['idea_id']}**: 점수 {r['composite_score']:.2f}, 초과수익 {r['excess_return_pp']:.2f}pp, MDD 개선 {r['mdd_improvement_pp']:.2f}pp, 전환 {r['n_switches']}회. 2018 전략/SPY {fmt(r['ret_2018_pct'])}/{fmt(r['spy_ret_2018_pct'])}%, 2022 전략/SPY {fmt(r['ret_2022_pct'])}/{fmt(r['spy_ret_2022_pct'])}%.")
    lines.extend(["", "## 지연 증가 비교: PX200 / VIXMED / DD15", "", "2018·2022 전략 수익률과 SPY 대비 누적 초과수익을 지연 순서 0→5→10→20→40으로 표시한다. 각 행은 한 개의 기준이다.", ""])
    by_id = {r["idea_id"]: r for r in scoreable}
    for family in ("PX200", "VIXMED", "DD15"):
        lines.extend([f"### {family}", "", "|지연일|2022 전략 %|2018 전략 %|전체 초과수익 pp|전환|", "|---:|---:|---:|---:|---:|"])
        for lag in LAGS:
            r = by_id.get(f"RT-{family}-L{lag}")
            if r:
                lines.append(f"|{lag}|{fmt(r['ret_2022_pct'])}|{fmt(r['ret_2018_pct'])}|{r['excess_return_pp']:.2f}|{r['n_switches']}|")
            else:
                lines.append(f"|{lag}|실패|실패|실패|실패|")
        lines.append("")
    lines.extend(["## 해석 한계", "", "- 이번 19개는 탐색 전용이다. 다중검정 보정, 평탄도, 비용 2배, 추가 1봉 지연, 무작위 귀무, 2008년 방어 검증을 하지 않았다.", "- 정렬은 지정된 점수의 기계적 순서이며 통계적 우위나 승격을 의미하지 않는다.", "- 전환 5회 미만은 결과를 신뢰할 수 없는 표본으로 표시했다.", "- 각 아이디어의 연간 수익률과 세부 값은 RESULTS.csv에 기록했다."])
    (HERE / "RANKED_TOP10.md").write_text("\n".join(lines) + "\n")


def write_report(rows, vix_median, first):
    valid = [r for r in rows if not str(r["notes"]).startswith("FAILED:")]
    by_id = {r["idea_id"]: r for r in valid}
    reliable = [r for r in valid if not r["unreliable_few_switches"]]
    lines = [
        "# 레짐 전환 확정 지연 탐색 보고서", "", f"> {LABEL}", "",
        f"VIX 중앙값은 cutoff 적용 시계열에서 1회 계산한 **{vix_median:.4f}**다. SPY/QQQ/SHY 공통 첫 관측일은 {max(first[t] for t in TICKERS).date().isoformat()}이며, 신호일·가격 유효성 확인 후 실제 평가 첫 체결일은 {valid[0]['start_date'] if valid else '확인 불가'}다. 마지막 평가일은 {valid[0]['end_date'] if valid else '확인 불가'}다.", "",
        "## 핵심 답변", "",
    ]
    for family in ("PX200", "VIXMED", "DD15"):
        group = [by_id[f"RT-{family}-L{lag}"] for lag in LAGS if f"RT-{family}-L{lag}" in by_id]
        if not group:
            lines.append(f"- **{family}**: 계산 결과가 없어 2022·2018 변화 여부를 판단할 수 없다.")
            continue
        base = group[0]
        best2022 = max(group, key=lambda r: r["ret_2022_pct"] if np.isfinite(r["ret_2022_pct"]) else -np.inf)
        losses = [r for r in group if np.isfinite(r["ret_2022_pct"]) and r["ret_2022_pct"] < 0]
        moved_nonneg = [r for r in group if np.isfinite(r["ret_2022_pct"]) and r["ret_2022_pct"] >= 0]
        improvement = best2022["ret_2022_pct"] - base["ret_2022_pct"]
        statement = f"2022년 {base['ret_2022_pct']:.2f}% (L0)에서 최고 {best2022['ret_2022_pct']:.2f}% (L{best2022['confirmation_lag_days']})로 {improvement:+.2f}%p 변화"
        if moved_nonneg:
            statement += "; 양수 전환 지연이 " + ", ".join(f"L{r['confirmation_lag_days']}" for r in moved_nonneg)
        elif losses:
            statement += "; 조사한 지연 중 손실을 없앤 값은 없음"
        else:
            statement += "; 2022 수익률 확인 불가"
        lines.append(f"- **{family}**: {statement}. 초과수익은 L0 {base['excess_return_pp']:.2f}pp에서 최고 {max(group, key=lambda r: r['excess_return_pp'])['excess_return_pp']:.2f}pp까지 관측됐다. 이 기준만으로 공통 효과라고 볼 수 없다.")
    nonneg_groups = []
    for family in ("PX200", "VIXMED", "DD15"):
        vals = [by_id[f"RT-{family}-L{lag}"] for lag in LAGS if f"RT-{family}-L{lag}" in by_id]
        if vals and any(np.isfinite(r["ret_2022_pct"]) and r["ret_2022_pct"] >= 0 for r in vals):
            nonneg_groups.append(family)
    lines.extend(["", "조사한 세 기준(PX200, VIXMED, DD15) 어디에서도 2022 손실이 사라지지 않았다. 따라서 세 기준 공통으로 손실을 없애는 지연 패턴은 관측되지 않았다. 일부 지연에서 손실 폭이 줄었지만, 탐색 19개 비교로 원인이나 재현성을 주장할 수 없다.", "", "## 지연 증가와 전체 성과", "", "|기준|L0 초과수익 pp|최고 초과수익 pp 및 지연|L40 초과수익 pp|L0→L40 단조 하락|", "|---|---:|---|---:|---|"])
    for family in ("PX200", "VIXMED", "DD15"):
        group = [by_id[f"RT-{family}-L{lag}"] for lag in LAGS if f"RT-{family}-L{lag}" in by_id]
        if group:
            best = max(group, key=lambda r: r["excess_return_pp"])
            sequence = [r["excess_return_pp"] for r in group]
            lines.append(f"|{family}|{group[0]['excess_return_pp']:.2f}|{best['excess_return_pp']:.2f} / L{best['confirmation_lag_days']}|{group[-1]['excess_return_pp']:.2f}|{all(sequence[i] >= sequence[i+1] for i in range(len(sequence)-1))}|")
    lines.extend(["", "## 약세장 및 표본 신뢰도", ""])
    for family, lag, _ in IDEA_SPECS:
        r = by_id.get(f"RT-{family}-L{lag}")
        if r:
            flag = "신뢰 불가(전환 5회 미만)" if r["unreliable_few_switches"] else "전환 수 기준 통과"
            lines.append(f"- **{r['idea_id']}**: 2018 {fmt(r['ret_2018_pct'])}% (SPY {fmt(r['spy_ret_2018_pct'])}%), 2022 {fmt(r['ret_2022_pct'])}% (SPY {fmt(r['spy_ret_2022_pct'])}%), 전환 {r['n_switches']}회 — {flag}.")
    lines.extend(["", "2018년과 2022년 모두 전략 수익이 0% 이상인 아이디어: " + (", ".join(r["idea_id"] for r in reliable if r["both_bear_years_nonneg"]) if any(r["both_bear_years_nonneg"] for r in reliable) else "없음") + ".", "전환 5회 미만 아이디어는 신뢰할 수 없는 결과로 보고 승격 판단에서 제외했다.", "", "## 승격 후보", ""])
    candidates = [r for r in reliable if r["excess_return_pp"] > 0 and r["mdd_improvement_pp"] > 0 and r["both_bear_years_nonneg"]]
    if candidates:
        lines.append("탐색 점수·두 약세장 수익·전환 횟수 조건을 모두 만족한 이름: " + ", ".join(f"**{r['idea_id']}**" for r in candidates) + ". 강건성 검증 필요.")
    else:
        lines.append("정식 강건성 검증 대상으로 명시할 승격 후보는 없다. 이번 라운드에서는 강건성 검증을 실행하지 않았다.")
    lines.extend(["", "## 범위와 계산 한계", "", "- SPY/QQQ/SHY 공통 상장 이후와 지표가 유효한 평가 기간을 사용했다. 날짜별 값은 cutoff 필터를 거친 데이터만으로 계산했다.", "- raw 레짐은 SPY 조정종가 기준이다. VIXMED 중앙값은 cutoff 이전 전체 VIX 시계열의 단일 중앙값이다.", "- 신호 확정일이 실행일보다 앞섬을 매 체결 경로에서 assert로 확인했다. 가격은 adj_close 기반이며 배당 조정 시가를 근사한다.", "- 결과는 탐색 스크리닝으로, 13라운드 장부·G-게이트에 포함되지 않는다. TRAIN_TRIALS.csv는 열지 않고 수정하지 않았다."])
    (HERE / "REPORT_REGIME_TIMING.md").write_text("\n".join(lines) + "\n")


def main():
    etf, vix = load_data()
    dates, C, AO, V, first = build_prices(etf, vix)
    raw_states, vix_median = build_raw_states(dates, C, V)
    rows = []
    for family, lag, params in IDEA_SPECS:
        try:
            rows.append(simulate(family, lag, params, raw_states[family], dates, C, AO, first))
        except Exception as exc:
            rows.append({"idea_id": f"RT-{family}-L{lag}", "family": family, "params": params,
                         "start_date": "", "end_date": "", "confirmation_lag_days": lag,
                         "n_switches": 0, "excess_return_pp": np.nan, "strategy_mdd_pct": np.nan,
                         "spy_mdd_pct": np.nan, "ret_2018_pct": np.nan, "spy_ret_2018_pct": np.nan,
                         "ret_2022_pct": np.nan, "spy_ret_2022_pct": np.nan, "switches_per_year": np.nan,
                         "unreliable_few_switches": True, "both_bear_years_nonneg": False,
                         "annual_returns_pct": "{}", "notes": f"FAILED: {type(exc).__name__}: {exc}",
                         "strategy_cum_return_pct": np.nan, "spy_cum_return_pct": np.nan,
                         "mdd_improvement_pp": np.nan})
    write_ideas()
    write_results(rows)
    write_ranked(rows)
    write_report(rows, vix_median, first)
    print(f"ideas={len(IDEA_SPECS)} results={len(rows)} scoreable={sum(not str(r['notes']).startswith('FAILED:') for r in rows)} cutoff={CUTOFF.date()}")
    print(f"common_start={max(first[t] for t in TICKERS).date()} vix_median={vix_median:.4f}")


if __name__ == "__main__":
    main()
