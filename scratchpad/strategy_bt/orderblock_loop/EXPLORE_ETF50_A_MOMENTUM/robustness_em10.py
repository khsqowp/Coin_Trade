#!/usr/bin/env python3
"""Exploratory robustness checks for EM10, using TRAIN-only Yahoo ETF data."""

import os
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_DATA_DIR = "/Users/user/CODE/Coin_Trade/trading_data"
if os.environ.get("TRADING_DATA_DIR") != EXPECTED_DATA_DIR:
    raise RuntimeError("TRADING_DATA_DIR must be the repository-local trading_data path")

DATA_FILE = Path(EXPECTED_DATA_DIR) / "external/equities/us/yahoo_daily_us_etf.parquet"
OUT_DIR = Path(__file__).resolve().parent
TRAIN_CUTOFF = pd.Timestamp("2026-06-01")
SECTORS = ["XLE", "XLF", "XLK", "XLV", "XLY", "XLP"]
CASH = "SHY"
ALL_TICKERS = SECTORS + [CASH, "SPY"]
COST_PER_LEG = 0.0006


def load_panels():
    raw = pd.read_parquet(DATA_FILE)
    raw = raw.loc[raw["date"] <= TRAIN_CUTOFF].copy()
    raw = raw.drop_duplicates(subset=["ticker", "date"], keep="first")
    raw = raw.sort_values(["ticker", "date"])
    raw = raw.loc[raw["ticker"].isin(ALL_TICKERS)]
    adj_close = raw.pivot(index="date", columns="ticker", values="adj_close")
    listing = raw.groupby("ticker")["date"].min().to_dict()
    return adj_close, listing


ADJ_CLOSE, LISTING_DATE = load_panels()


def common_dates(tickers):
    return ADJ_CLOSE[tickers].dropna(how="any").index


def month_end_signal_dates(dates):
    s = pd.Series(dates, index=dates)
    grouped = s.groupby([dates.year, dates.month])
    return pd.DatetimeIndex(sorted(grouped.max().values))


def idea_dual_momentum(universe, cash, lookback_m, top_k):
    tickers = universe + [cash]
    dates = common_dates(tickers)
    px = ADJ_CLOSE[universe].loc[dates]
    momentum = px / px.shift(lookback_m * 21) - 1.0
    signals = month_end_signal_dates(dates)
    at_signal = momentum.reindex(signals)
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    first_valid = None
    for day in signals:
        row = at_signal.loc[day]
        if row.isna().any():
            continue
        if first_valid is None:
            first_valid = day
        picks = row.sort_values(ascending=False).index[:top_k]
        allocation = {ticker: (1.0 / top_k if row[ticker] > 0 else 0.0) for ticker in picks}
        cash_weight = 1.0 - sum(allocation.values())
        for ticker, weight in allocation.items():
            weights.loc[day:, ticker] = weight
        weights.loc[day:, cash] = cash_weight
        for ticker in universe:
            if ticker not in allocation:
                weights.loc[day:, ticker] = 0.0
    return weights, first_valid


def apply_lag_and_cost(weights_df, ret_df, eval_start, eval_end, shift_days=1, cost_per_leg=None):
    cost_rate = COST_PER_LEG if cost_per_leg is None else cost_per_leg
    active = weights_df.shift(shift_days)
    index = active.index[(active.index >= eval_start) & (active.index <= eval_end)]
    active = active.loc[index]
    returns = ret_df.loc[index]
    gross = (active * returns).sum(axis=1)
    delta = active.diff().abs().sum(axis=1)
    delta.iloc[0] = active.iloc[0].abs().sum()
    net = gross - cost_rate * delta
    net.iloc[-1] -= cost_rate * active.iloc[-1].abs().sum()
    return net


def spy_baseline(eval_start, eval_end, cost_per_leg=None):
    cost_rate = COST_PER_LEG if cost_per_leg is None else cost_per_leg
    px = ADJ_CLOSE["SPY"].loc[eval_start:eval_end].dropna()
    returns = px.pct_change().fillna(0.0)
    returns.iloc[0] -= cost_rate
    returns.iloc[-1] -= cost_rate
    return returns


def annual_returns(nav):
    yearly = nav.groupby(nav.index.year).agg(["first", "last"])
    return {int(year): row["last"] / row["first"] - 1.0 for year, row in yearly.iterrows()}


def total_return(returns):
    return float((1.0 + returns).prod() - 1.0)


def evaluate(lookback, top_k, cost=COST_PER_LEG, shift_days=1):
    weights, first_signal = idea_dual_momentum(SECTORS, CASH, lookback, top_k)
    if first_signal is None:
        raise RuntimeError(f"No valid signal for lookback={lookback}, top_k={top_k}")
    eval_start = first_signal
    eval_end = min(weights.index.max(), TRAIN_CUTOFF)
    returns = ADJ_CLOSE[weights.columns].pct_change().fillna(0.0)
    strategy = apply_lag_and_cost(weights, returns, eval_start, eval_end, shift_days, cost)
    baseline = spy_baseline(eval_start, eval_end, cost)
    strat_total = total_return(strategy)
    base_total = total_return(baseline)
    return {
        "lookback": lookback,
        "top_k": top_k,
        "start": eval_start,
        "end": eval_end,
        "strategy": strategy,
        "baseline": baseline,
        "strategy_total": strat_total,
        "baseline_total": base_total,
        "excess": strat_total - base_total,
    }


def random_weights(dates, signal_dates, rng):
    columns = SECTORS + [CASH]
    weights = pd.DataFrame(0.0, index=dates, columns=columns)
    for day in signal_dates:
        chosen = rng.choice(SECTORS, size=2, replace=False)
        weights.loc[day:, SECTORS] = 0.0
        weights.loc[day:, CASH] = 0.0
        weights.loc[day:, chosen] = 0.5
    return weights


def pct(value):
    return f"{value * 100:.2f}%"


def main():
    grid = [evaluate(lb, k) for lb in range(9, 16) for k in range(1, 4)]
    winner = next(item for item in grid if item["lookback"] == 12 and item["top_k"] == 2)
    threshold = winner["excess"] * 0.5
    neighbors = [item for item in grid if abs(item["lookback"] - 12) <= 1
                 and abs(item["top_k"] - 2) <= 1 and item is not winner]
    neighbor_pass = sum(item["excess"] >= threshold for item in neighbors)
    all_pass = sum(item["excess"] >= threshold for item in grid)

    double_cost = evaluate(12, 2, cost=0.0012)
    delayed = evaluate(12, 2, shift_days=2)

    listing_lines = []
    for ticker in SECTORS + [CASH]:
        listed = LISTING_DATE.get(ticker)
        listing_lines.append((ticker, listed))
    covers_2008 = all(date is not None and pd.Timestamp(date).year <= 2008 for _, date in listing_lines)
    annual_rows = []
    if covers_2008:
        strat_nav = (1.0 + winner["strategy"]).cumprod()
        base_nav = (1.0 + winner["baseline"]).cumprod()
        annual_rows = [annual_returns(strat_nav).get(2008), annual_returns(base_nav).get(2008)]

    eval_dates = common_dates(SECTORS + [CASH])
    signals = month_end_signal_dates(eval_dates)
    signals = signals[(signals >= winner["start"]) & (signals <= winner["end"])]
    ret_df = ADJ_CLOSE[SECTORS + [CASH]].pct_change().fillna(0.0)
    rng = np.random.default_rng(42)
    random_totals = []
    for _ in range(100):
        weights = random_weights(eval_dates, signals, rng)
        net = apply_lag_and_cost(weights, ret_df, winner["start"], winner["end"])
        random_totals.append(total_return(net))
    random_array = np.asarray(random_totals)
    percentile = 100.0 * np.mean(random_array <= winner["strategy_total"])
    baseline_total = winner["baseline_total"]
    random_excess = random_array - baseline_total
    random_at_or_below_em10 = int(np.sum(random_array <= winner["strategy_total"]))

    lines = [
        "# EM10 강건성 탐색 결과",
        "",
        "**탐색 전용(EXPLORATORY ONLY): 이 디렉터리는 정식 사전등록 전 강건성 검증이며 `TRAIN_TRIALS.csv`에 행을 추가하지 않았다.** TEST(2026-06-01 초과)는 parquet 로드 직후 제거했고 이후 계산에 쓰지 않았다.",
        "",
        "## 공통 방법",
        "",
        "Yahoo `adj_close`로 신호와 일별 수익을 계산했다. 6개 섹터 ETF 중 월말 12개월(21거래일×개월) 수익률 상위 2개를 선택하고, 양수 모멘텀인 자리만 각각 50% 보유하며 나머지는 SHY에 둔다. 신호는 1거래일 지연 체결 근사, 비용은 비중 변화 절대값 합계에 편도 6bp를 곱하고 마지막 청산에도 같은 비용을 부과했다. 유니버스 공통 거래일과 첫 유효 신호 이후부터 2026-06-01까지 평가했다. SPY 기준선도 각 실행의 정확한 평가기간 및 같은 비용을 썼다.",
        "",
        "## 1. 격자 평탄도",
        "",
        "아래 27개 조합은 lookback 9~15개월, top_k 1~3 전체다. 초과수익은 전략 총수익률에서 같은 기간 SPY 총수익률을 뺀 값이다.",
        "",
        "| Lookback | 평가기간 | top_k=1 | top_k=2 | top_k=3 |",
        "|---:|---|---:|---:|---:|",
    ]
    for lb in range(9, 16):
        row = [item for item in grid if item["lookback"] == lb]
        period = f"{row[0]['start'].date()}~{row[0]['end'].date()}"
        lines.append(f"| {lb}개월 | {period} | {row[0]['excess']*100:+.2f}%p | {row[1]['excess']*100:+.2f}%p | {row[2]['excess']*100:+.2f}%p |")
    lines += [
        "",
        f"EM10 승자 초과수익은 **{winner['excess']*100:+.2f}%p**이고, 절반 기준은 **{threshold*100:+.2f}%p**다. lookback ±1, top_k ±1 범위의 나머지 인접 조합은 {neighbor_pass}/{len(neighbors)}개({neighbor_pass/len(neighbors)*100:.1f}%)가 절반 기준을 충족했다. 필요한 기준 70%는 **{'통과' if neighbor_pass/len(neighbors) >= 0.70 else '실패'}**다.",
        f"전체 격자에서는 {all_pass}/27개({all_pass/27*100:.1f}%)가 승자의 절반 이상이다. 평가 시작일은 모든 격자 조합에서 유니버스 공통 날짜와 해당 lookback의 첫 유효 월말 신호로 자동 산출했다.",
        "",
        "## 2. 비용 2배",
        "",
        f"편도 비용을 6bp에서 12bp로 높여 왕복 24bp로 계산했다. 기본 EM10 초과수익 {winner['excess']*100:+.2f}%p에서 {double_cost['excess']*100:+.2f}%p로 변했다(감소 { (winner['excess']-double_cost['excess'])*100:.2f}%p). 초과수익 유지 여부: **{'유지' if double_cost['excess'] > 0 else '소멸'}**.",
        "",
        "## 3. 체결 1봉 추가 지연",
        "",
        f"신호 적용을 shift(1)에서 shift(2)로 바꿨다. 기본 초과수익 {winner['excess']*100:+.2f}%p, 추가 지연 초과수익 {delayed['excess']*100:+.2f}%p, 차이 { (delayed['excess']-winner['excess'])*100:+.2f}%p다. 전략 총수익률은 {winner['strategy_total']*100:.2f}%에서 {delayed['strategy_total']*100:.2f}%로 바뀌었다.",
        "",
        "## 4. 2008년 데이터 확인",
        "",
        "| 티커 | parquet 첫 관측일 |",
        "|---|---|",
    ]
    for ticker, date in listing_lines:
        lines.append(f"| {ticker} | {pd.Timestamp(date).date() if date is not None else '데이터 없음'} |")
    if covers_2008:
        lines += ["", f"7개 모두 2008년을 포함한다. 기존 `annual_returns()` 방식의 2008년 연간수익률은 EM10 **{annual_rows[0]*100:+.2f}%**, SPY 기준선 **{annual_rows[1]*100:+.2f}%**다."]
    else:
        lines += ["", "유니버스 일부가 2008년에 상장 전이므로 **2008 데이터 없음**; 해당 연도 전략 비교는 계산하지 않았다."]
    lines += [
        "",
        "## 5. 무작위 선택 비교 (최소화 버전)",
        "",
        f"매월 같은 월말 신호일마다 6개 섹터 중 2개를 균등 무작위로 뽑고 각 50% 투자했다. 현금 비중은 없으며, 평가기간·비용·1봉 지연은 EM10과 동일하다. 100회 시드 42 결과의 전략 총수익률은 최소 {random_array.min()*100:.2f}%, 중앙값 {np.median(random_array)*100:.2f}%, 최대 {random_array.max()*100:.2f}%다. SPY 대비 무작위 초과수익 분포는 최소 {random_excess.min()*100:+.2f}%p, 중앙값 {np.median(random_excess)*100:+.2f}%p, 최대 {random_excess.max()*100:+.2f}%p다.",
        f"EM10 전략 총수익률 {winner['strategy_total']*100:.2f}%는 무작위 100회 결과의 {random_at_or_below_em10}/100개 이상이며 경험적 {percentile:.1f}백분위에 해당한다. 이 100회 비교는 정식 무작위 귀무검정(200회 이상) 요건을 충족하지 않는 탐색용 신호다.",
        "",
        "## 결론",
        "",
    ]
    if neighbor_pass / len(neighbors) >= 0.70 and double_cost["excess"] > 0 and percentile >= 95:
        conclusion = "격자 인접값 기준을 통과하고 비용 2배에서도 초과수익이 남으며 무작위 선택 상위 5% 안에 든다. 따라서 EM10은 탐색 결과상 고원형 강건 신호로 보이며 정식 PREREG에 올릴 가치가 있다. 다만 현재는 100회 무작위 비교이고 사전등록·다중검정 보정·워크포워드가 없으므로 전략이 검증됐다는 뜻은 아니다."
    else:
        failures = []
        if neighbor_pass / len(neighbors) < 0.70:
            failures.append("인접 격자 평탄도 70% 기준 실패")
        if double_cost["excess"] <= 0:
            failures.append("비용 2배에서 초과수익 소멸")
        if percentile < 95:
            failures.append("무작위 100회 비교에서 상위 5% 미달")
        conclusion = "EM10은 현재 자료로 정식 PREREG에 올릴 근거가 부족해 후보에서 탈락시킨다. 판단 근거: " + ", ".join(failures) + ". 이 결과는 탐색 단계이며 정식 다중검정 보정·워크포워드 검증을 대체하지 않는다."
    lines += [conclusion, "", "확인 안 됨: 실제 시가 체결, 배당 재투자 현금흐름의 원자료 검증, 다중검정 보정, 200회 이상 무작위 귀무, 워크포워드 성과는 이 작업에서 검증하지 않았다.", ""]
    (OUT_DIR / "ROBUSTNESS_EM10.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'ROBUSTNESS_EM10.md'}")
    print(f"grid=27; neighbors={neighbor_pass}/{len(neighbors)}; all_ge_half={all_pass}/27")
    print(f"base_excess={winner['excess']*100:.4f}pp; double_cost_excess={double_cost['excess']*100:.4f}pp; delayed_excess={delayed['excess']*100:.4f}pp")
    print(f"random_percentile={percentile:.1f}; random_total_min_median_max={random_array.min():.6f},{np.median(random_array):.6f},{random_array.max():.6f}")


if __name__ == "__main__":
    main()
