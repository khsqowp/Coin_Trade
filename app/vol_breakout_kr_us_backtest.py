"""Exploratory daily Larry Williams volatility breakout backtest (local CSV only)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".kis-cache-local"
REPORT_MD = ROOT / "docs/kr-us-equity-trader/vol_breakout_0.5_rule_report.md"
REPORT_JSON = REPORT_MD.with_suffix(".json")
COSTS = {
    "KR": {"base": (0.00065, 0.00245), "stress": (0.00115, 0.00295)},
    "US": {"base": (0.0008, 0.0008), "stress": (0.0036, 0.0036)},
}


def make_trades(frame: pd.DataFrame, multiplier: float = 0.5) -> list[dict]:
    """Signal on t; exit at t+1 open, then t+1 independently gets its own signal."""
    required = ["Open", "High", "Low"]
    if len(frame) < 2 or any(c not in frame for c in required):
        return []
    f = frame.sort_index()
    opens = f["Open"].to_numpy(dtype=float)
    highs = f["High"].to_numpy(dtype=float)
    ranges = f["High"].to_numpy(dtype=float) - f["Low"].to_numpy(dtype=float)
    dates = f.index
    trades = []
    # Iteration deliberately advances one day after entry: position exits at the
    # next open, so that same next day remains eligible for a fresh signal.
    for i in range(1, len(f) - 1):
        trigger = float(opens[i] + multiplier * ranges[i - 1])
        if highs[i] >= trigger:
            trades.append({"entry_date": _date(dates[i]), "entry_price": trigger,
                           "exit_date": _date(dates[i + 1]),
                           "exit_price": float(opens[i + 1]),
                           "signal_date": _date(dates[i])})
    return trades


def _date(x) -> str:
    return pd.Timestamp(x).isoformat()


def _metrics(eq: pd.Series, daily: pd.Series) -> dict:
    if len(eq) < 2:
        return {"cagr_pct": 0.0, "sharpe": 0.0, "mdd_pct": 0.0,
                "calmar": 0.0, "final_equity": float(eq.iloc[-1]) if len(eq) else 1.0,
                "yearly_return_pct": {}}
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    final = float(eq.iloc[-1])
    cagr = (final ** (1 / years) - 1) * 100 if final > 0 and years > 0 else -100.0
    mdd = float(((eq.cummax() - eq) / eq.cummax()).max() * 100)
    std = float(daily.std())
    sharpe = float(daily.mean() / std * np.sqrt(252)) if std > 0 else 0.0
    yearly = {str(int(y)): float((g.iloc[-1] / g.iloc[0] - 1) * 100)
              for y, g in eq.groupby(eq.index.year)}
    return {"cagr_pct": float(cagr), "sharpe": sharpe, "mdd_pct": mdd,
            "calmar": float(cagr / mdd) if mdd > 0 else None,
            "final_equity": final, "yearly_return_pct": yearly}


def _symbol_result(frame: pd.DataFrame, multiplier: float,
                   buy_cost: float, sell_cost: float, notional: float) -> dict:
    f = frame.sort_index()
    trades = make_trades(f, multiplier)
    # Net return includes costs on both fills, as a fraction of entry cash spent:
    # (exit*(1-sell_cost) - entry*(1+buy_cost)) / (entry*(1+buy_cost)).
    for t in trades:
        t["net_return"] = ((t["exit_price"] * (1 - sell_cost) -
                            t["entry_price"] * (1 + buy_cost)) /
                           (t["entry_price"] * (1 + buy_cost)))
        t["gross_return"] = t["exit_price"] / t["entry_price"] - 1
        t["dollar_pnl"] = notional * t["net_return"]
    if len(f):
        dates = pd.DatetimeIndex(f.index)
        pnl_values = np.zeros(len(dates), dtype=float)
        factor_values = np.ones(len(dates), dtype=float)
        date_positions = {d.isoformat(): i for i, d in enumerate(dates)}
        for t in trades:
            pos = date_positions.get(t["exit_date"])
            if pos is not None:
                pnl_values[pos] += t["dollar_pnl"]
                factor_values[pos] *= 1 + t["net_return"]
        daily_pnl = pd.Series(pnl_values, index=dates)
        # Per-symbol statistics compound each sequential trade's net return;
        # the fixed-notional portfolio below separately sums dollar P&L.
        equity = pd.Series(factor_values, index=dates).cumprod()
        daily_ret = equity.pct_change().fillna(0.0)
        years = (dates[-1] - dates[0]).days / 365.25 if len(dates) > 1 else 0
        final = float(equity.iloc[-1])
        cagr = (final ** (1 / years) - 1) * 100 if final > 0 and years > 0 else (-100.0 if final <= 0 else 0.0)
        mdd = float(((equity.cummax() - equity) / equity.cummax()).max() * 100) if len(equity) else 0.0
        bh = float((f["Close"].iloc[-1] / f["Close"].iloc[0]) ** (1 / years) - 1) * 100 if years > 0 and f["Close"].iloc[0] > 0 else 0.0
    else:
        equity, daily_ret, cagr, mdd, bh = pd.Series(dtype=float), pd.Series(dtype=float), 0., 0., 0.
    return {"rows": len(f), "start": _date(f.index[0]) if len(f) else None,
            "end": _date(f.index[-1]) if len(f) else None, "trade_count": len(trades),
            "win_rate_pct": float(np.mean([t["net_return"] > 0 for t in trades]) * 100) if trades else 0.0,
            "cagr_pct": float(cagr), "mdd_pct": mdd,
            "total_return_pct": float((equity.iloc[-1] - 1) * 100) if len(equity) else 0.0,
            "buy_hold_cagr_pct": bh, "beats_buy_hold": cagr > bh,
            "trades": trades, "daily_pnl": {d.isoformat(): float(v) for d, v in daily_pnl.items()} if len(f) else {}}


def _ew_buy_hold(closes: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    # Port of app/kr_us_rotation_backtest.py::_ew_buy_hold.
    daily = (closes.pct_change().fillna(0.0) * closes.iloc[0].notna()).sum(axis=1) / closes.iloc[0].notna().sum()
    return (1 + daily).cumprod(), daily


def _market_result(market: str, frames: dict[str, pd.DataFrame], multiplier: float,
                   scenario: str) -> dict:
    buy, sell = COSTS[market][scenario]
    per_symbol = {s: _symbol_result(f, multiplier, buy, sell, 10000.0) for s, f in frames.items()}
    # Full overlapping cohort window: only timestamps present for every symbol.
    closes = pd.concat({s: f["Close"] for s, f in frames.items()}, axis=1).dropna(how="any").sort_index()
    if len(closes) >= 2:
        bh_eq, bh_daily = _ew_buy_hold(closes)
        bh = _metrics(bh_eq, bh_daily)
        idx = closes.index
        pnl = pd.Series(0.0, index=idx)
        for res in per_symbol.values():
            for d, amount in res["daily_pnl"].items():
                dt = pd.Timestamp(d)
                if dt in pnl.index:
                    pnl.loc[dt] += amount
        initial = 10000.0 * len(frames)
        strategy_daily = pnl / initial
        strategy_eq = 1 + strategy_daily.cumsum()
        strat = _metrics(strategy_eq, strategy_daily)
    else:
        bh = _metrics(pd.Series([1.0], index=closes.index), pd.Series([0.0], index=closes.index))
        strat = dict(bh)
        idx = closes.index
    cagr = [v["cagr_pct"] for v in per_symbol.values()]
    mdd = [v["mdd_pct"] for v in per_symbol.values()]
    wins = sum(sum(t["net_return"] > 0 for t in v["trades"]) for v in per_symbol.values())
    count = sum(v["trade_count"] for v in per_symbol.values())
    return {"market": market, "cost_scenario": scenario, "multiplier": multiplier,
            "costs_one_way_pct": {"buy": buy * 100, "sell": sell * 100},
            "symbol_count": len(frames), "cohort_overlap_start": _date(idx[0]) if len(idx) else None,
            "cohort_overlap_end": _date(idx[-1]) if len(idx) else None,
            "cohort_overlap_rows": len(idx), "per_symbol": per_symbol,
            "symbol_distribution": {"mean_cagr_pct": float(np.mean(cagr)) if cagr else 0.,
                "median_cagr_pct": float(np.median(cagr)) if cagr else 0.,
                "mean_mdd_pct": float(np.mean(mdd)) if mdd else 0.,
                "median_mdd_pct": float(np.median(mdd)) if mdd else 0.,
                "beats_buy_hold_count": sum(v["beats_buy_hold"] for v in per_symbol.values()),
                "beats_buy_hold_pct": 100 * sum(v["beats_buy_hold"] for v in per_symbol.values()) / len(per_symbol) if per_symbol else 0.},
            "equal_weight_buy_hold": bh, "fixed_notional_portfolio": strat,
            "fixed_notional_per_symbol": 10000.0, "portfolio_total_starting_notional": 10000.0 * len(frames),
            "total_trade_count": count, "pooled_win_rate_pct": wins / count * 100 if count else 0.0,
            "portfolio_vs_buy_hold_cagr_diff_pct_points": strat["cagr_pct"] - bh["cagr_pct"]}


def _load() -> dict[str, dict[str, pd.DataFrame]]:
    out = {"KR": {}, "US": {}}
    for market in out:
        for path in sorted(CACHE.glob(f"{market}_*.csv")):
            df = pd.read_csv(path, parse_dates=["timestamp"])
            df = df.dropna(subset=["Open", "High", "Low", "Close"])
            df = df.set_index("timestamp").sort_index()
            out[market][path.stem[len(market) + 1:]] = df
    return out


def _fmt(x: float) -> str:
    return f"{x:+.2f}%"


def _report(data: dict) -> str:
    lines = ["# Larry Williams Volatility Breakout 0.5 — KR/US 탐색 백테스트", "",
        "## 해석 및 필수 한계", "",
        "- 이 표본은 현재 워치리스트에서 추적하는 KR 92개와 US 92개 대형·유동성 종목으로 구성된 **생존자 코호트**다. 2010~2026년 사이 상장폐지·합병되거나 워치리스트에서 제외된 종목은 빠져 있어 진정한 과거 시점 투자 가능 유니버스가 아니며, 결과를 위쪽으로 편향시킨다.",
        "- 0.5가 단일 헤드라인 규칙이다. 사전 지정한 별도 민감도 확인인 0.4/0.6 외에는 어떤 파라미터도 조정하지 않았고, 세 배수 결과를 합치거나 평균 내지 않았다.",
        "- 이는 SPEC.md의 E2 단계 단일 탐색 백테스트다. 봉인/홀드아웃 검증 결과가 아니며 어느 방향으로도 거래 가능한 엣지를 입증하지 않는다. 성과가 매수보유보다 낮은 시장·비용 시나리오도 그대로 기록한다.",
        "- 진입 다음 거래일 시가에 청산하므로 모든 거래는 정확히 하룻밤 보유하며, 해당 한 세션의 오버나이트 갭 위험에 노출된다.",
        "- CSV에 저장된 분할/배당 조정 OHLCV를 사용했다. 체결은 지정 규칙의 가격으로 가정했으며, 시장 충격·호가 스프레드는 명시된 비용 외 별도 모델링하지 않았다.",
        "- 순 거래 수익률 = `(exit × (1 − sell_cost) − entry × (1 + buy_cost)) / (entry × (1 + buy_cost))`. 포트폴리오는 종목당 고정 10,000 단위 notional을 사용하고 재투자하지 않으며, 초기 포트폴리오 notional로 나눈 일별 달러 손익을 누적했다.", ""]
    for market in ("KR", "US"):
        lines += [f"## {market}", "", "### 헤드라인 규칙: 배수 0.5", ""]
        for scenario in ("base", "stress"):
            r = data["headline"][market][scenario]
            p, b, d = r["fixed_notional_portfolio"], r["equal_weight_buy_hold"], r["symbol_distribution"]
            lines += [f"#### 비용: {scenario} (매수 {r['costs_one_way_pct']['buy']:.3f}%, 매도 {r['costs_one_way_pct']['sell']:.3f}% 편도)", "",
                f"- 개별 종목 전체 이력: CAGR 평균/중앙값 **{_fmt(d['mean_cagr_pct'])} / {_fmt(d['median_cagr_pct'])}**, MDD 평균/중앙값 **{d['mean_mdd_pct']:.2f}% / {d['median_mdd_pct']:.2f}%**; 종목별 B&H CAGR 상회 **{d['beats_buy_hold_count']}/{r['symbol_count']} ({d['beats_buy_hold_pct']:.1f}%)**.",
                f"- 동일가중 B&H (공통 날짜 {r['cohort_overlap_start']}–{r['cohort_overlap_end']}, {r['cohort_overlap_rows']}행): CAGR **{b['cagr_pct']:.2f}%**, Sharpe **{b['sharpe']:.3f}**, MDD **{b['mdd_pct']:.2f}%**, Calmar **{b['calmar']}**.",
                f"- 고정 notional 포트폴리오 (종목당 10,000, 총 초기 notional {r['portfolio_total_starting_notional']:,.0f}): CAGR **{p['cagr_pct']:.2f}%**, Sharpe **{p['sharpe']:.3f}**, MDD **{p['mdd_pct']:.2f}%**, Calmar **{p['calmar']}**; 연간 수익률(%) `{json.dumps(p['yearly_return_pct'], ensure_ascii=False, sort_keys=True)}`.",
                f"- B&H 대비 포트폴리오 CAGR 차이 **{r['portfolio_vs_buy_hold_cagr_diff_pct_points']:+.2f}%p**. 전체 체결 **{r['total_trade_count']:,}건**, pooled net win rate **{r['pooled_win_rate_pct']:.2f}%**.",
                "- 종목별 원자료(거래별 가격·날짜·수익률 포함)는 동반 JSON `headline` 아래에 있다.", ""]
    lines += ["## 0.4 / 0.6 민감도 확인 (비주요 결과)", "",
        "이 결과는 헤드라인 0.5 수치와 분리된 참고 분석이며, 0.5와 합산하거나 평균 내지 않았다.", ""]
    for mult in (0.4, 0.6):
        lines += [f"### 배수 {mult:.1f}", ""]
        for market in ("KR", "US"):
            for scenario in ("base", "stress"):
                r = data["sensitivity"][str(mult)][market][scenario]
                p = r["fixed_notional_portfolio"]
                lines.append(f"- {market} {scenario}: portfolio CAGR {p['cagr_pct']:.2f}%, Sharpe {p['sharpe']:.3f}, MDD {p['mdd_pct']:.2f}%, Calmar {p['calmar']}, trades {r['total_trade_count']:,}, pooled win {r['pooled_win_rate_pct']:.2f}%; B&H CAGR {r['equal_weight_buy_hold']['cagr_pct']:.2f}%, 차이 {r['portfolio_vs_buy_hold_cagr_diff_pct_points']:+.2f}%p.")
        lines.append("")
    lines += ["## 재현", "", "저장소 루트에서 `python -m app.vol_breakout_kr_us_backtest` 실행. 캐시 CSV만 직접 읽으며 네트워크나 KIS 인증 모듈을 사용하지 않는다.", ""]
    return "\n".join(lines)


def run() -> dict:
    frames = _load()
    data = {"metadata": {"rule": "Larry Williams volatility breakout", "headline_multiplier": 0.5,
        "sensitivity_multipliers": [0.4, 0.6], "cache_files": {m: len(v) for m, v in frames.items()},
        "fixed_notional_per_symbol": 10000.0, "source": ".kis-cache-local CSV files only"}, "headline": {}, "sensitivity": {}}
    for market in ("KR", "US"):
        data["headline"][market] = {s: _market_result(market, frames[market], 0.5, s) for s in ("base", "stress")}
    for mult in (0.4, 0.6):
        data["sensitivity"][str(mult)] = {m: {s: _market_result(m, frames[m], mult, s) for s in ("base", "stress")} for m in ("KR", "US")}
    # Store raw fills once per market/multiplier. Cost scenarios share identical
    # fills, so duplicating the ledger and zero-P&L dates bloats JSON without
    # adding verification value. Each ledger row is [entry_date, entry_price,
    # exit_date, exit_price]; costs and exact net-return formula are in report.
    data["raw_trade_ledger"] = {}
    for market in ("KR", "US"):
        data["raw_trade_ledger"].setdefault(market, {})
        for mult, results in [(0.5, data["headline"][market]["base"])] + [
                (float(k), data["sensitivity"][k][market]["base"]) for k in ("0.4", "0.6")]:
            data["raw_trade_ledger"][market][str(mult)] = {
                symbol: [[t["entry_date"], t["entry_price"], t["exit_date"], t["exit_price"]]
                         for t in result["trades"]]
                for symbol, result in results["per_symbol"].items()}
    for tree in [data["headline"][m][s] for m in ("KR", "US") for s in ("base", "stress")]:
        for result in tree["per_symbol"].values():
            result.pop("trades", None)
            result.pop("daily_pnl", None)
    for multiplier in data["sensitivity"].values():
        for market_results in multiplier.values():
            for tree in market_results.values():
                for result in tree["per_symbol"].values():
                    result.pop("trades", None)
                    result.pop("daily_pnl", None)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    REPORT_MD.write_text(_report(data) + "\n")
    print(f"Completed local-cache run: KR={len(frames['KR'])}, US={len(frames['US'])} symbols")
    print(f"Markdown: {REPORT_MD}\nJSON: {REPORT_JSON}")
    for m in ("KR", "US"):
        r = data["headline"][m]["base"]
        p = r["fixed_notional_portfolio"]
        print(f"{m} base: CAGR {p['cagr_pct']:.2f}%, Sharpe {p['sharpe']:.3f}, MDD {p['mdd_pct']:.2f}%, "
              f"trades {r['total_trade_count']}, win {r['pooled_win_rate_pct']:.2f}%, "
              f"B&H CAGR {r['equal_weight_buy_hold']['cagr_pct']:.2f}%")
    return data


if __name__ == "__main__":
    run()
