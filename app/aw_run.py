"""사전등록 올웨더 연구 격자 실행기. 로컬 캐시만 사용한다."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app import aw_engine as E, aw_regime as R
from app.aw_data import load_panel


def metrics(eq: pd.Series) -> dict:
    x = eq.dropna()
    if len(x) < 2 or x.iloc[0] <= 0:
        return {"cagr": np.nan, "mdd": np.nan, "calmar": np.nan, "peryear": {}}
    years = max((x.index[-1] - x.index[0]).days / 365.25, 1 / 252)
    cagr = (x.iloc[-1] / x.iloc[0]) ** (1 / years) - 1
    dd = x / x.cummax() - 1
    ye = x.groupby(x.index.year).last()
    base = ye.shift(1); base.iloc[0] = x.iloc[0]
    yearly = (ye / base - 1).to_dict()
    return {"cagr": float(cagr), "mdd": float(-dd.min()), "calmar": float(cagr / -dd.min()) if dd.min() < 0 else None,
            "peryear": {str(k): float(v) for k, v in yearly.items()}}


def _bench(panel, symbol, bond=None):
    close = panel.c[symbol].dropna()
    return pd.Series(np.linspace(1, 1, len(panel.dates)), index=panel.dates) if close.empty else (close.reindex(panel.dates).ffill() / close.iloc[0]).fillna(1)


def _period_return(series: pd.Series, mask: pd.Series) -> float:
    x = series.loc[mask].dropna()
    return float(x.iloc[-1] / x.iloc[0] - 1) if len(x) > 1 and x.iloc[0] else np.nan


def _period_cagr(series: pd.Series, mask: pd.Series) -> float:
    x = series.dropna()
    if len(x) < 2: return np.nan
    returns = x.pct_change().replace([np.inf, -np.inf], np.nan)
    selected = returns.loc[mask.reindex(returns.index, fill_value=False)].dropna()
    if selected.empty: return np.nan
    growth = float((1 + selected).prod())
    return growth ** (252 / len(selected)) - 1 if growth > 0 else -1.0


def _daily_metrics(eq: pd.Series, mask: pd.Series | None = None) -> dict:
    r = eq.pct_change().dropna()
    if mask is not None:
        r = r.loc[mask.reindex(r.index, fill_value=False)]
    sharpe = float(r.mean() / r.std(ddof=1) * np.sqrt(252)) if len(r) > 1 and r.std(ddof=1) > 0 else np.nan
    return {"sharpe": sharpe}


def _window_metrics(eq: pd.Series, mask: pd.Series | None = None) -> dict:
    if mask is None: mask = pd.Series(True, index=eq.index)
    selected = eq.loc[mask.reindex(eq.index, fill_value=False)]
    m = metrics(selected) if len(selected) else metrics(pd.Series(dtype=float))
    m.update(_daily_metrics(eq, mask))
    return m

def _windows(eq: pd.Series) -> dict:
    n = len(eq); cut = int(n * .6)
    fold = [int(i * n / 3) for i in range(4)]
    return {"IS": eq.iloc[:cut + 1], "OOS": eq.iloc[cut:], "F1": eq.iloc[fold[0]:fold[1] + 1],
            "F2": eq.iloc[fold[1]:fold[2] + 1], "F3": eq.iloc[fold[2]:]}


def run(market: str, out_path: str):
    panel = load_panel(market)
    needed = ["069500" if market == "KR" else "SPY"]
    missing_etfs = [s for s in panel.missing if s in {x["code"] for x in __import__("app.aw_universe", fromlist=["etfs"]).etfs(market)}]
    if missing_etfs or any(s not in panel.symbols for s in needed):
        raise SystemExit("ETF 캐시가 없어 실행할 수 없습니다. 누락 ETF: " + ", ".join(missing_etfs or needed))
    index = needed[0]
    sectors = [s for s in panel.symbols if panel.roles[s] == "sector"]
    macro = "261240" if market == "KR" else "IEF"
    if macro not in panel.symbols:
        raise SystemExit(f"매크로 레짐 ETF 캐시 누락: {macro}")
    events_path = Path(__file__).resolve().parents[1] / "data" / "aw_events.csv"
    events = pd.read_csv(events_path, parse_dates=["date"]) if events_path.exists() else pd.DataFrame(columns=["date", "market", "event"])
    combos = itertools.product((3, 5, 10), (60, 120), (0., .25), (False, True), (False, True))
    results, regimes_by_hysteresis = {}, {}
    for hyst, lookback, inv, mr, overlay in combos:
        score = R.classify(panel.c, market, index, sectors, macro, hyst)
        regimes_by_hysteresis.setdefault(hyst, {str(k.date()): str(v) for k, v in score.regime.items()})
        # 세 오프셋의 성과 곡선 평균. 각 오프셋은 독립적인 시작 리밸런스 경로다.
        runs = []
        for offset in (0, 7, 14):
            target = E.target_weights(panel, score.regime, lookback, inv, mr, overlay, events, offset)
            res = E.simulate(panel, target, events, regimes=score.regime)
            runs.append(res)
        eq = pd.concat([r["equity"] for r in runs], axis=1).mean(axis=1)
        avg_turn = pd.concat([r["turnover"] for r in runs], axis=1).mean(axis=1)
        avg_cost = pd.concat([r["costs"] for r in runs], axis=1).mean(axis=1)
        sleeve_names = runs[0]["sleeve_contribution"]
        avg_sleeves = {name: pd.concat([r["sleeve_contribution"][name] for r in runs], axis=1).mean(axis=1)
                       for name in sleeve_names}
        key = f"H{hyst}_L{lookback}_I{int(inv*100)}_MR{int(mr)}_EV{int(overlay)}"
        mask_b = panel.dates >= pd.Timestamp("2019-01-01")
        turnover_windows = {"A": float(avg_turn.sum() / max(len(avg_turn)/252, 1e-12)),
                            "B": float(avg_turn.loc[mask_b].sum() / max(mask_b.sum()/252, 1e-12))}
        cost_windows = {"A": float(avg_cost.sum() / max(len(avg_cost)/252, 1e-12)),
                        "B": float(avg_cost.loc[mask_b].sum() / max(mask_b.sum()/252, 1e-12))}
        results[key] = {"params": {"hysteresis": hyst, "stock_lookback": lookback, "inverse_cap": inv,
                                   "mean_reversion": mr, "event_overlay": overlay}, "metrics": metrics(eq),
                       "equity": {str(k.date()): float(v) for k, v in eq.items()},
                       "annual_turnover": turnover_windows, "annual_cost": cost_windows,
                       "turnover": float(np.mean([r["turnover"].sum() for r in runs])),
                       "costs": float(np.mean([r["costs"].sum() for r in runs]))}
    # 벤치마크는 요청된 네 종류, 기존 로테이션은 유니버스에서 동일 120일 모멘텀 K5 대용으로 고정.
    bench = {"index_hold": _bench(panel, index)}
    benchmark_activity = {"index_hold": {"turnover": 0., "costs": 0.}}
    bond = next((s for s in panel.symbols if ("단기채권" in panel.names[s]) or s == "BIL"), None)
    if bond:
        daily_i = bench["index_hold"].pct_change().fillna(0)
        daily_b = _bench(panel, bond).pct_change().fillna(0)
        mix = pd.Series(index=panel.dates, dtype=float); mix.iloc[0] = 1.0
        weight_i, weight_b = .6, .4
        for t in range(1, len(mix)):
            if panel.dates[t].month != panel.dates[t-1].month:
                weight_i, weight_b = .6, .4
            daily_return = weight_i*daily_i.iloc[t] + weight_b*daily_b.iloc[t]
            mix.iloc[t] = mix.iloc[t-1] * (1 + daily_return)
            if 1 + daily_return > 0:
                weight_i = weight_i*(1+daily_i.iloc[t])/(1+daily_return)
                weight_b = weight_b*(1+daily_b.iloc[t])/(1+daily_return)
        bench["index60_bond40"] = mix
        benchmark_activity["index60_bond40"] = {"turnover": 0., "costs": 0.}
    bench["cash"] = pd.Series(1., index=panel.dates)
    benchmark_activity["cash"] = {"turnover": 0., "costs": 0.}
    stock_symbols = [s for s in panel.symbols if panel.roles[s] == "stock"]
    if stock_symbols:
        target = pd.DataFrame(0., index=panel.dates, columns=panel.symbols)
        momentum = panel.c.pct_change(120)
        for t in range(0, len(panel.dates), 21):
            eligible = [s for s in stock_symbols if panel.stock_eligible[s].iloc[t] and pd.notna(momentum[s].iloc[t])]
            for s in sorted(eligible, key=lambda x: momentum[x].iloc[t], reverse=True)[:5]:
                target.iloc[t, target.columns.get_loc(s)] = .20
            if t:
                # 다음 21일 동안 같은 월간 신호를 유지한다.
                target.iloc[t:min(t + 21, len(target))] = target.iloc[t]
        rotation_result = E.simulate(panel, target, drawdown_breaker=False)
        rotation = rotation_result["equity"]
        bench["momentum_rotation_120_21_k5"] = rotation / rotation.iloc[0]
        benchmark_activity["momentum_rotation_120_21_k5"] = {"turnover": float(rotation_result["turnover"].sum()),
                                                               "costs": float(rotation_result["costs"].sum())}
    # 평가 기준을 같은 날짜/수익률 인덱스로 내보낸다.
    bench_metrics = {k: metrics(v) for k, v in bench.items()}
    benchmark_index = bench["index_hold"]
    bond_curve = _bench(panel, bond) if bond else None
    for key, item in results.items():
        eq = pd.Series(item["equity"])
        eq.index = pd.DatetimeIndex(eq.index)
        full = metrics(eq)
        y22 = full["peryear"].get("2022", np.nan)
        regime_series = pd.Series(regimes_by_hysteresis[item["params"]["hysteresis"]])
        # 날짜 문자열 키를 날짜 인덱스로 바꾸고, t일 레짐은 t+1일 수익률에 적용되므로 하루 민다.
        regime_series.index = pd.DatetimeIndex(regime_series.index)
        regime_series = regime_series.shift(1)
        range_years = [2011, 2012, 2013, 2014, 2015, 2016] if market == "KR" else [2015, 2016, 2018]
        range_mask = eq.index.year.isin(range_years)
        range_return = _period_cagr(eq, pd.Series(range_mask, index=eq.index))
        bond_return = _period_cagr(bond_curve, pd.Series(range_mask, index=eq.index)) if bond_curve is not None else np.nan
        bull_mask = regime_series.reindex(eq.index).eq("BULL")
        strat_bull = _period_cagr(eq, bull_mask)
        index_bull = _period_cagr(benchmark_index, bull_mask)
        folds = _windows(eq)
        bench_folds = _windows(benchmark_index)
        calmar_wins = 0
        for fold_name in ("F1", "F2", "F3"):
            a, b = metrics(folds[fold_name]), metrics(bench_folds[fold_name])
            if a["calmar"] is not None and b["calmar"] is not None and a["calmar"] > b["calmar"]: calmar_wins += 1
        hyst = item["params"]["hysteresis"]
        hyst_grid = (3, 5, 10)
        hpos = hyst_grid.index(hyst)
        neighbor_hyst = {hyst_grid[i] for i in (hpos - 1, hpos + 1) if 0 <= i < len(hyst_grid)}
        peers = [x for x in results.values() if x["params"]["hysteresis"] in neighbor_hyst and
                 all(x["params"][k] == item["params"][k] for k in ("stock_lookback", "inverse_cap", "mean_reversion", "event_overlay"))]
        stable = all(np.sign(x["metrics"]["cagr"]) == np.sign(full["cagr"]) for x in peers)
        criteria = {"mdd_le_20": full["mdd"] <= .20, "2022_ge_minus5": y22 >= -.05,
                    "range_gt_bond": bool(np.isfinite(range_return) and np.isfinite(bond_return) and range_return > bond_return),
                    "bull_ge_70pct_index": bool(np.isfinite(strat_bull) and np.isfinite(index_bull) and strat_bull >= .7 * index_bull),
                    "calmar_2_of_3_folds": calmar_wins >= 2, "neighbor_sign_stable": stable}
        # 평가 A/B: strategy and every benchmark share identical daily-return masks.
        masks = {"A": pd.Series(True, index=eq.index), "B": pd.Series(eq.index >= pd.Timestamp("2019-01-01"), index=eq.index)}
        item["window_metrics"] = {name: {"strategy": _window_metrics(eq, mask),
            "benchmarks": {bk: _window_metrics(bv.reindex(eq.index).ffill(), mask) for bk, bv in bench.items()},
            "annual_turnover": item["annual_turnover"][name],
            "annual_cost": item["annual_cost"][name]} for name, mask in masks.items()}
        item["criteria"] = criteria
        item["evaluation"] = {"range_cagr": range_return, "bond_range_cagr": bond_return,
                              "bull_cagr": strat_bull, "index_bull_cagr": index_bull, "fold_calmar_wins": calmar_wins,
                              "folds": {k: metrics(v) for k, v in folds.items()},
                              "regime_cagr": {r: _period_cagr(eq, regime_series.reindex(eq.index).eq(r)) for r in ("BULL", "RANGE", "BEAR")}}
        item["criteria_pass_count"] = sum(x is True for x in criteria.values())
        item["criteria_status"] = {k: ("PASS" if v is True else "FAIL" if v is False else "NOT_COMPUTED") for k, v in criteria.items()}
    benchmark_windows = {}
    for name, curve in bench.items():
        benchmark_windows[name] = {}
        for label, mask in {"A": pd.Series(True, index=curve.index),
                            "B": pd.Series(curve.index >= pd.Timestamp("2019-01-01"), index=curve.index)}.items():
            elapsed = max(mask.sum()/252, 1e-12)
            benchmark_windows[name][label] = {"metrics": _window_metrics(curve, mask),
                "annual_turnover": benchmark_activity[name]["turnover"] / elapsed,
                "annual_cost": benchmark_activity[name]["costs"] / elapsed}
    report = {"market": market, "dates": [str(panel.dates[0].date()), str(panel.dates[-1].date())],
              "regimes_by_hysteresis": regimes_by_hysteresis,
              "missing_symbols": panel.missing, "config_count": len(results), "benchmarks": bench_metrics,
              "benchmark_windows": benchmark_windows, "grid": results}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print("configs", len(results), "saved", out_path)
    ranked = sorted(results.items(), key=lambda kv: (kv[1]["criteria_pass_count"], kv[1]["metrics"]["calmar"] if kv[1]["metrics"]["calmar"] is not None else -np.inf), reverse=True)
    print("TOP", "config pass_count calmar A_sharpe B_sharpe")
    for key, item in ranked[:10]:
        print(key, item["criteria_pass_count"], item["metrics"]["calmar"], item["window_metrics"]["A"]["strategy"]["sharpe"], item["window_metrics"]["B"]["strategy"]["sharpe"])
    for k, b in bench_metrics.items(): print("BENCH", k, "A", b, "B", _window_metrics(bench[k], pd.Series(bench[k].index >= pd.Timestamp("2019-01-01"), index=bench[k].index)))


def main(argv=None):
    p = argparse.ArgumentParser(description="올웨더 사전등록 격자 백테스트")
    p.add_argument("market", choices=("KR", "US"))
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    run(args.market, args.out)


if __name__ == "__main__":
    main()
