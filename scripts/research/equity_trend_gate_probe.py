#!/usr/bin/env python3
"""Exploratory KR/US trend-gate rerun on the existing local survivor caches."""
from pathlib import Path
import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parents[2] / '.kis-cache-local'
K = 10
KR_ETFS = {'069500','091160','091170','091180','102110','102970','114260','114800',
           '117460','117680','117700','132030','133690','139230','139260','140700',
           '140710','143860','148070','153130','157490','229200','244580','261240','305720','307950'}


def metrics(nav, exposure, turnover, label):
    nav = nav.dropna()
    ret = nav.pct_change().dropna()
    years = (nav.index[-1] - nav.index[0]).days / 365.2425
    cagr = ((nav.iloc[-1] ** (1 / years) - 1) * 100) if nav.iloc[-1] > 0 and years > 0 else -100.
    drawdown = nav / nav.cummax() - 1
    annual = ((1 + ret).groupby(ret.index.year).prod() - 1) * 100
    return {
        'label': label, 'start': str(nav.index[0].date()), 'end': str(nav.index[-1].date()),
        'cagr_pct': float(cagr), 'mdd_pct': float(-drawdown.min() * 100),
        'sharpe': float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() else 0.,
        'exposure_pct': float(np.mean(exposure) * 100), 'one_way_turnover_x': float(turnover),
        'annual_returns_pct': {str(int(y)): round(float(v), 3) for y, v in annual.items()},
    }


def read_market(prefix):
    frames = {}
    for path in sorted(CACHE.glob(f'{prefix}_*.csv')):
        frame = pd.read_csv(path, parse_dates=['timestamp']).dropna(
            subset=['Open', 'High', 'Low', 'Close']).set_index('timestamp').sort_index()
        frame = frame[~frame.index.duplicated(keep='last')]
        frames[path.stem[len(prefix) + 1:]] = frame
    return frames


def kr_run(frames, gated, fee, slip, stock_tax):
    opens = pd.concat({s:f.Open for s,f in frames.items()}, axis=1).sort_index()
    closes = pd.concat({s:f.Close for s,f in frames.items()}, axis=1).reindex(opens.index)
    dates = opens.index
    mom = closes / closes.shift(60) - 1
    bench_sma = closes['069500'].rolling(200, min_periods=200).mean()
    month_end = pd.Series(np.arange(len(dates)), index=dates).groupby(
        dates.tz_localize(None).to_period('M') if dates.tz is not None else dates.to_period('M')
    ).last().to_numpy()
    targets = pd.DataFrame(0., index=dates, columns=opens.columns)
    current = pd.Series(0., index=opens.columns)
    for i in range(len(dates) - 1):
        if i in month_end and i >= 200:
            if gated and (pd.isna(bench_sma.iloc[i]) or closes['069500'].iloc[i] <= bench_sma.iloc[i]):
                current[:] = 0.
            else:
                eligible = closes.iloc[i].notna() & opens.iloc[i + 1].notna()
                picks = mom.iloc[i].where(eligible).nlargest(K).dropna().index
                current[:] = 0.
                if len(picks): current.loc[picks] = 1 / len(picks)
        targets.iloc[i + 1] = current.to_numpy()
    prev = targets.shift(1).fillna(0.)
    delta = targets - prev
    buys = delta.clip(lower=0).sum(axis=1)
    sells = -delta.clip(upper=0).sum(axis=1)
    gross = (targets * (opens.shift(-1) / opens - 1)).sum(axis=1, min_count=1).fillna(0.)
    taxable_sells = (-delta.clip(upper=0)).multiply(
        pd.Series({s: 0. if s in KR_ETFS else 1. for s in opens.columns}), axis=1).sum(axis=1)
    net = gross - (fee + slip) * (buys + sells) - stock_tax * taxable_sells
    net = net.loc['2011':]
    nav = (1 + net).cumprod()
    exposure = targets.loc[net.index].sum(axis=1).to_numpy()
    turnover = float((buys.loc[net.index].sum() + sells.loc[net.index].sum()) / 2)
    return metrics(nav, exposure, turnover, 'KR_mom60_monthly_top10' + ('_SMA200_gate' if gated else '_base'))


def us_run(frames, gated, fee, slip, rebalance='daily'):
    common_close = pd.concat({s:f.Close for s,f in frames.items()}, axis=1).dropna(how='any').sort_index()
    symbols = sorted(frames)
    common_open = pd.concat({s:frames[s].Open.reindex(common_close.index) for s in symbols}, axis=1)[symbols]
    common_close = common_close[symbols]
    sma = frames['SPY'].Close.rolling(200, min_periods=200).mean().reindex(common_close.index)
    momentum = pd.concat({s:(frames[s].Close / frames[s].Close.shift(126) - 1).reindex(common_close.index)
                          for s in symbols}, axis=1)[symbols]
    dates = common_close.index
    nav = 1.; cash = 1.; shares = {s:0. for s in symbols}; navs=[]; exposure=[]; total_turnover=0.
    month_periods = dates.tz_localize(None).to_period('M') if dates.tz is not None else dates.to_period('M')
    month_end_indices=set(pd.Series(np.arange(len(dates)),index=dates).groupby(month_periods).last().to_numpy())
    current_weights={}
    for j, day in enumerate(dates):
        op = common_open.loc[day]
        close = common_close.loc[day]
        nav_open = cash + sum(q * op[s] for s,q in shares.items() if q and pd.notna(op[s]))
        if j:
            signal_day = dates[j - 1]
            should_rebalance=(rebalance=='daily' or j-1 in month_end_indices)
            if should_rebalance:
                risk_off = gated and (pd.isna(sma.loc[signal_day]) or frames['SPY'].Close.get(signal_day, np.nan) <= sma.loc[signal_day])
                if risk_off:
                    current_weights={}
                else:
                    scores = momentum.loc[signal_day].dropna().nlargest(K)
                    current_weights = {s:1/len(scores) for s in scores.index} if len(scores) else {}
                weights=current_weights
                target = {s:(nav_open * weights[s] / op[s] if s in weights and pd.notna(op[s]) and op[s] > 0 else 0.) for s in symbols}
                turnover = sum(abs((target[s] - shares[s]) * op[s]) for s in symbols if pd.notna(op[s]))
                charges = turnover * (fee + slip)
                gross_buy = sum(target[s] * op[s] for s in symbols if pd.notna(op[s]))
                if gross_buy + charges > nav_open and charges > 0:
                    scale = nav_open / (gross_buy + charges)
                    target = {s:q*scale for s,q in target.items()}
                    turnover = sum(abs((target[s] - shares[s]) * op[s]) for s in symbols if pd.notna(op[s]))
                    charges = turnover * (fee + slip)
                    gross_buy = sum(target[s] * op[s] for s in symbols if pd.notna(op[s]))
                total_turnover += turnover / max(nav_open, 1e-12)
                cash = nav_open - gross_buy - charges
                shares = target
        nav_close = cash + sum(q * close[s] for s,q in shares.items() if q and pd.notna(close[s]))
        navs.append(nav_close)
        exposure.append(sum(q * close[s] for s,q in shares.items() if q and pd.notna(close[s])) / nav_close if nav_close else 0.)
    series = pd.Series(navs, index=dates)
    return metrics(series, exposure, total_turnover / 2,
                   f'US_mom126_{rebalance}_top10' + ('_SMA200_gate' if gated else '_base'))


def main():
    kr = read_market('KR'); us = read_market('US')
    assert len(kr) == 92 and '069500' in kr
    assert len(us) == 92 and 'SPY' in us
    out=[]
    for gated in (False, True):
        for scenario, fee, slip in (('base', .00065, .0005), ('stress', .00115, .0005)):
            r=kr_run(kr, gated, fee, slip, .0020); r['scenario']=scenario; out.append(r)
        for scenario, fee, slip in (('base', .0008, .0010), ('stress', .0036, .0025)):
            r=us_run(us, gated, fee, slip); r['scenario']=scenario; out.append(r)
        for scenario, fee, slip in (('base', .0008, .0010), ('stress', .0036, .0025)):
            r=us_run(us, gated, fee, slip, rebalance='monthly'); r['scenario']=scenario; out.append(r)
    for row in out: print(row)


if __name__ == '__main__':
    main()
