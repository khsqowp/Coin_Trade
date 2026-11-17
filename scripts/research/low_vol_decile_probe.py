#!/usr/bin/env python3
"""Round 5: low-realized-volatility decile factor on the 92-symbol KR/US survivor caches.

Copy of scripts/research/low_skew_decile_probe.py (Round 4). The ONLY change to the
strategy is the ranking statistic: G1 skewness -> sample std (ddof=1).

Fixed before running (do not change after results):
  * signal: sample standard deviation (ddof=1) of the last 63 close-to-close simple
    returns (64 consecutive valid closes on the market union calendar);
    s == 0 or non-finite -> ineligible that date (same exclusion as the Round 4 G1)
  * rank ascending std (ties: ticker string), hold the lowest 10% of the eligible
    cross-section, K = max(1, floor(0.10 * n_eligible)), equal weight
  * decisions every 21 trading-calendar sessions (index 0, 21, 42, ...); signal uses the
    decision-date close, orders fill at the next session close; shares are then fixed
    (weights drift) until the next scheduled execution
Reused unchanged from scripts/research/equity_trend_gate_probe.py: Close loading
(read_market), calendars (KR union calendar from 2011; US all-symbol common dates),
base/stress fee+slippage constants and KR 20 bp stock sell tax with ETF exemption,
and the CAGR/MDD/Sharpe formula (metrics).
Exploratory E2 only: survivor cohort, already-inspected period, not independent OOS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parent))
from equity_trend_gate_probe import KR_ETFS, metrics, read_market  # noqa: E402
import low_skew_decile_probe as skew_probe  # noqa: E402  (overlap diagnostic only)

WINDOW = 63
REBALANCE = 21
DECILE = 0.10
# (fee, slippage) per side exactly as equity_trend_gate_probe.main(); KR adds 20 bp stock sell tax.
COSTS = {
    'KR': {'base': (.00065, .0005), 'stress': (.00115, .0005)},
    'US': {'base': (.0008, .0010), 'stress': (.0036, .0025)},
}
KR_STOCK_TAX = .0020
# Reporting-only tag (US costs have no ETF distinction); used for the ETF pick share statistic.
US_ETFS_REPORT = {'BIL', 'DBC', 'EEM', 'EFA', 'GLD', 'IBB', 'IEF', 'ITA', 'IWM', 'KRE', 'MTUM', 'QQQ',
                  'QUAL', 'SH', 'SHY', 'SMH', 'SOXX', 'SPY', 'TIP', 'TLT', 'USMV', 'UUP', 'VLUE', 'VNQ',
                  'XBI', 'XHB', 'XLB', 'XLC', 'XLE', 'XLF', 'XLI', 'XLK', 'XLP', 'XLRE', 'XLU', 'XLV',
                  'XLY', 'XME'}


def vol_matrix(closes: pd.DataFrame, n: int = WINDOW) -> pd.DataFrame:
    """Sample std (ddof=1) of n returns on the union calendar; NaN unless all n returns
    in the window are valid; s == 0 or non-finite -> NaN (same exclusion as G1)."""
    rets = (closes / closes.shift(1) - 1).to_numpy(dtype=float)
    out = np.full(rets.shape, np.nan)
    win = sliding_window_view(rets, n, axis=0)            # (T-n+1, N, n)
    s = win.std(axis=2, ddof=1)
    s[~np.isfinite(s) | (s == 0) | ~np.isfinite(win).all(axis=2)] = np.nan
    out[n - 1:] = s
    return pd.DataFrame(out, index=closes.index, columns=closes.columns)


def rank_lowest(scores: pd.Series) -> list[str]:
    s = scores.dropna()
    return sorted(s.index, key=lambda t: (s[t], t))


def _rebalance(cash, shares, px, picks, frozen, buy_c, sell_c):
    """Trade to equal-weight `picks` at close `px`; returns new cash/shares, flows and fees.

    Positions with no valid close (`frozen`) cannot trade and keep their shares.
    The investable scale is bisected so post-trade cash stays >= 0 after costs.
    """
    tradable = [s for s in shares if s not in frozen]
    value = {s: shares[s] * px[s] for s in tradable}
    frozen_val = sum(shares[s] * px.get(s, np.nan) for s in frozen if not np.isnan(px.get(s, np.nan)))
    nav_pre = cash + sum(value.values()) + frozen_val
    names = sorted(set(tradable) | set(picks))

    def trade(scale):
        tgt = {s: (scale * (nav_pre - frozen_val) / len(picks) if s in picks else 0.) for s in names}
        buys = sum(max(tgt[s] - value.get(s, 0.), 0.) for s in names)
        sells = {s: max(value.get(s, 0.) - tgt[s], 0.) for s in names}
        fee = buys * buy_c + sum(v * sell_c[s] for s, v in sells.items())
        return tgt, buys, sum(sells.values()), fee, cash - buys + sum(sells.values()) - fee

    lo, hi = 0., 1.
    if trade(1.)[4] < 0:
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if trade(mid)[4] >= 0 else (lo, mid)
        hi = lo
    tgt, buys, sells, fee, new_cash = trade(hi)
    new_shares = {s: shares[s] for s in frozen}
    new_shares.update({s: tgt[s] / px[s] for s in names if tgt[s] > 0})
    return max(new_cash, 0.), new_shares, buys, sells, fee, nav_pre


def last_valid(closes: pd.DataFrame) -> pd.DataFrame:
    """Mark-to-market price: last actual close (stale marks only for NAV, never for fills)."""
    return closes.ffill()


def run_factor(closes, g1, market, scenario, etfs, report_etfs):
    fee, slip = COSTS[market][scenario]
    buy_c = fee + slip
    tax = KR_STOCK_TAX if market == 'KR' else 0.
    sell_c = {s: fee + slip + (0. if s in etfs else tax) for s in closes.columns}
    marks = last_valid(closes)
    dates = closes.index
    cash, shares = 1., {}
    navs, exposure, turnover, total_fee = [], [], 0., 0.
    pending, log = None, []
    for j, day in enumerate(dates):
        px_row, mark_row = closes.iloc[j], marks.iloc[j]
        last = j == len(dates) - 1
        if pending is not None and not last:
            ranking, n_elig = pending
            k = max(1, int(np.floor(DECILE * n_elig)))
            picks = [s for s in ranking if pd.notna(px_row[s])][:k]
            frozen = {s for s in shares if pd.isna(px_row[s])}
            px = {s: (px_row[s] if pd.notna(px_row[s]) else mark_row[s]) for s in closes.columns}
            if picks:
                cash, shares, b, sl, f, nav_pre = _rebalance(cash, shares, px, picks, frozen, buy_c, sell_c)
                turnover += (b + sl) / nav_pre
                total_fee += f
                log.append({'exec_date': str(day.date()), 'eligible': n_elig, 'k': k, 'picks': picks,
                            'etf_picks': sum(p in report_etfs for p in picks), 'frozen': sorted(frozen)})
            pending = None
        if last and shares:  # terminal liquidation (stale-marked names at last actual close)
            proceeds = sum(q * mark_row[s] for s, q in shares.items())
            f = sum(q * mark_row[s] * sell_c[s] for s, q in shares.items())
            turnover += proceeds / (cash + proceeds)
            total_fee += f
            cash, shares = cash + proceeds - f, {}
        if j % REBALANCE == 0 and not last:
            row = g1.loc[day]
            pending = (rank_lowest(row), int(row.notna().sum()))
        held = sum(q * mark_row[s] for s, q in shares.items())
        navs.append(cash + held)
        exposure.append(held / (cash + held))
    nav = pd.Series(navs, index=dates)
    out = metrics(nav, exposure, turnover / 2, f'{market}_lowvol_decile_{scenario}')
    years = (dates[-1] - dates[0]).days / 365.2425
    out.update(scenario=scenario, terminal_nav=float(nav.iloc[-1]), total_cost_nav_units=total_fee,
               one_way_turnover_per_year=turnover / 2 / years, rebalances=len(log),
               avg_holdings=float(np.mean([len(r['picks']) for r in log])),
               avg_eligible=float(np.mean([r['eligible'] for r in log])),
               etf_pick_share_pct=100 * sum(r['etf_picks'] for r in log) / sum(len(r['picks']) for r in log),
               frozen_events=sum(len(r['frozen']) for r in log))
    return out, log


def run_buy_hold(closes, market, scenario, etfs):
    """Same-cohort equal-weight B&H: 1/N budget per symbol, bought at the strategy's first
    execution close (index 1) or the symbol's first later close; budget waits in cash until
    then; never bought on the final date; liquidated with sell costs on the final date."""
    fee, slip = COSTS[market][scenario]
    buy_c = fee + slip
    tax = KR_STOCK_TAX if market == 'KR' else 0.
    marks = last_valid(closes)
    dates, syms = closes.index, list(closes.columns)
    budget = 1. / len(syms)
    cash, shares, bought, navs, exposure, total_fee, turnover = 1., {}, set(), [], [], 0., 0.
    for j, day in enumerate(dates):
        px, mk = closes.iloc[j], marks.iloc[j]
        last = j == len(dates) - 1
        if j >= 1 and not last:
            nav_pre = cash + sum(q * mk[s] for s, q in shares.items())
            gross = 0.
            for s in syms:
                if s not in bought and pd.notna(px[s]):
                    shares[s] = budget / (1 + buy_c) / px[s]
                    gross += budget / (1 + buy_c)
                    bought.add(s)
            cash -= gross * (1 + buy_c)
            total_fee += gross * buy_c
            turnover += gross / nav_pre
        if last:
            proceeds = sum(q * mk[s] for s, q in shares.items())
            f = sum(q * mk[s] * (fee + slip + (0. if s in etfs else tax)) for s, q in shares.items())
            turnover += proceeds / (cash + proceeds)
            total_fee += f
            cash, shares = cash + proceeds - f, {}
        held = sum(q * mk[s] for s, q in shares.items())
        navs.append(cash + held)
        exposure.append(held / (cash + held))
    nav = pd.Series(navs, index=dates)
    out = metrics(nav, exposure, turnover / 2, f'{market}_equal_weight_buy_hold_{scenario}')
    out.update(scenario=scenario, terminal_nav=float(nav.iloc[-1]), total_cost_nav_units=total_fee,
               names_never_bought=sorted(set(syms) - bought))
    return out


def market_inputs(market):
    frames = read_market(market)
    union = pd.concat({s: f.Close for s, f in frames.items()}, axis=1).sort_index()
    g1 = vol_matrix(union)   # name kept from the Round 4 copy; holds the std signal
    if market == 'KR':   # equity_trend_gate_probe.kr_run: union calendar, NAV from 2011
        closes = union.loc['2011':]
    else:                # equity_trend_gate_probe.us_run: dates where all symbols have closes
        closes = union.dropna(how='any')
    return frames, closes, g1.reindex(closes.index), union


def overlap_with_lowskew(closes, union, market, etfs, report_etfs, vol_log):
    """Per-execution |vol picks & skew picks| / |vol picks|, Round 4 skew run at base cost."""
    g1 = skew_probe.g1_matrix(union).reindex(closes.index)
    _, skew_log = skew_probe.run_factor(closes, g1, market, 'base', etfs, report_etfs)
    skew_by_date = {r['exec_date']: set(r['picks']) for r in skew_log}
    ratios = [len(set(r['picks']) & skew_by_date[r['exec_date']]) / len(r['picks'])
              for r in vol_log if r['exec_date'] in skew_by_date]
    jacc = [len(set(r['picks']) & skew_by_date[r['exec_date']]) /
            len(set(r['picks']) | skew_by_date[r['exec_date']])
            for r in vol_log if r['exec_date'] in skew_by_date]
    return {'matched_rebalances': len(ratios), 'vol_rebalances': len(vol_log),
            'mean_share_of_vol_picks_in_skew_picks_pct': 100 * float(np.mean(ratios)),
            'median_share_pct': 100 * float(np.median(ratios)),
            'mean_jaccard_pct': 100 * float(np.mean(jacc))}


def main():
    results = {'fixed': {'window': WINDOW, 'rebalance_sessions': REBALANCE, 'decile': DECILE,
                         'weighting': 'equal', 'costs': COSTS, 'kr_stock_sell_tax': KR_STOCK_TAX}}
    for market in ('KR', 'US'):
        frames, closes, g1, union = market_inputs(market)
        assert len(frames) == 92, f'{market}: expected 92 cached symbols, found {len(frames)}'
        etfs = KR_ETFS if market == 'KR' else set()
        report_etfs = KR_ETFS if market == 'KR' else US_ETFS_REPORT
        block = {'symbols': len(frames), 'start': str(closes.index[0].date()),
                 'end': str(closes.index[-1].date()), 'sessions': len(closes)}
        for scenario in ('base', 'stress'):
            fac, log = run_factor(closes, g1, market, scenario, etfs, report_etfs)
            block[f'factor_{scenario}'] = fac
            block[f'buy_hold_{scenario}'] = run_buy_hold(closes, market, scenario, etfs)
            if scenario == 'base':
                counts = pd.Series([p for r in log for p in r['picks']]).value_counts()
                block['most_held_symbols_base'] = {k: int(v) for k, v in counts.head(12).items()}
                block['rebalance_log_base'] = log
                block['overlap_with_lowskew_base'] = overlap_with_lowskew(
                    closes, union, market, etfs, report_etfs, log)
        results[market] = block
    print(json.dumps(results, ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    main()
