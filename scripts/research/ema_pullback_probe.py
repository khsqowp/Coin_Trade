#!/usr/bin/env python3
"""Predeclared EMA pullback/reversal probe on local Binance Vision dev candles.

Read-only input; only rows with open_ms < cutoff are queried. Outputs a Markdown
report to the path supplied with --out. No whole-database hash is computed.
"""
import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(__file__).resolve().parents[2] / 'chart_predictor/data/vision_dev.sqlite'
CUTOFF_MS = int(pd.Timestamp('2026-10-09T00:00:00Z').timestamp() * 1000)
SYMBOLS = ('BNBUSDT', 'BTCUSDT', 'DOGEUSDT', 'ETHUSDT')
TF_MINUTES = (1, 3, 5, 10, 15, 30, 60, 120, 240, 360, 480, 720, 1440)
HORIZONS = (10, 20)
COSTS = {'base_0.1pct_RT': 0.001, 'stress_0.3pct_RT': 0.003}
BOOTSTRAPS = 2000
SEED = 20261115
MIN_TRADES = 30


def load_source(db, symbol):
    x = pd.read_sql_query(
        'SELECT open_ms,open AS o,high AS h,low AS l,close AS c,volume AS v '
        'FROM candles WHERE symbol=? AND open_ms<? ORDER BY open_ms',
        db, params=(symbol, CUTOFF_MS))
    x = x[x.open_ms + 60_000 <= CUTOFF_MS].reset_index(drop=True)
    return x


def aggregate(raw, minutes):
    """Only aligned buckets containing every source 1m candle are retained."""
    width = minutes * 60_000
    x = raw.copy()
    x['bucket'] = (x.open_ms // width) * width
    grouped = x.groupby('bucket', sort=True)
    out = grouped.agg(o=('o', 'first'), h=('h', 'max'), l=('l', 'min'),
                      c=('c', 'last'), v=('v', 'sum'), n=('open_ms', 'size'),
                      first=('open_ms', 'min'), last=('open_ms', 'max')).reset_index()
    good = ((out['n'] == minutes) & (out['first'] == out['bucket']) &
            (out['last'] == out['bucket'] + (minutes - 1) * 60_000))
    out = out.loc[good, ['bucket', 'o', 'h', 'l', 'c', 'v']].rename(
        columns={'bucket': 'open_ms'}).reset_index(drop=True)
    return out[out.open_ms + width <= CUTOFF_MS].reset_index(drop=True)


def signals(f):
    o, h, l, c = (f[k].to_numpy(float) for k in ('o', 'h', 'l', 'c'))
    close = pd.Series(c)
    e20 = close.ewm(span=20, adjust=False, min_periods=20).mean().to_numpy()
    e50 = close.ewm(span=50, adjust=False, min_periods=50).mean().to_numpy()
    e200 = close.ewm(span=200, adjust=False, min_periods=200).mean().to_numpy()
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
    aligned_up = (e20 > e50) & (e50 > e200) & (e200 > np.r_[np.nan, e200[:-1]])
    aligned_dn = (e20 < e50) & (e50 < e200) & (e200 < np.r_[np.nan, e200[:-1]])
    # Pullback reaches from the trend side to EMA20 or no farther than 1 ATR
    # through it; confirmation closes beyond the preceding candle extreme.
    long_zone = (l <= e20) & (l >= e20 - atr)
    short_zone = (h >= e20) & (h <= e20 + atr)
    bull_confirm = (c > o) & (c > np.r_[np.nan, h[:-1]])
    bear_confirm = (c < o) & (c < np.r_[np.nan, l[:-1]])
    masks = {'long': aligned_up & long_zone & bull_confirm,
             'short': aligned_dn & short_zone & bear_confirm}
    return masks, atr


def continuity(raw):
    t = raw.open_ms.to_numpy(np.int64)
    if len(t) < 2:
        return {'rows': len(t), 'missing_1m': None, 'gap_count': None,
                'largest_gap_minutes': None}
    delta = np.diff(t) // 60_000
    gaps = delta[delta > 1]
    return {'rows': int(len(t)), 'missing_1m': int(np.maximum(delta - 1, 0).sum()),
            'gap_count': int(len(gaps)),
            'largest_gap_minutes': int(gaps.max()) if len(gaps) else 0}


def wilson(k, n):
    if n == 0:
        return [None, None]
    z = 1.95996398454
    p = k / n
    d = 1 + z*z/n
    mid = (p + z*z/(2*n))/d
    rad = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return [float(mid-rad), float(mid+rad)]


def cluster_ci(records, key, seed):
    if not records:
        return None
    days = np.asarray([r['signal_ms'] // 86_400_000 for r in records])
    values = np.asarray([r[key] for r in records], dtype=float)
    unique = np.unique(days)
    daily_sum = np.asarray([values[days == d].sum() for d in unique])
    daily_count = np.asarray([(days == d).sum() for d in unique])
    rng = np.random.default_rng(seed)
    estimates = np.empty(BOOTSTRAPS)
    for b in range(BOOTSTRAPS):
        draw = rng.integers(0, len(unique), len(unique))
        estimates[b] = daily_sum[draw].sum() / daily_count[draw].sum()
    return [float(x) for x in np.quantile(estimates, [.025, .975])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='docs/research/ema_pullback_long_history_20261115.md')
    args = parser.parse_args()
    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    raw_by_symbol = {s: load_source(db, s) for s in SYMBOLS}
    source_checks = {s: continuity(x) for s, x in raw_by_symbol.items()}
    results = []
    manifests = []
    for symbol in SYMBOLS:
        raw = raw_by_symbol[symbol]
        source_t = raw.open_ms.to_numpy(np.int64)
        source_o = raw.o.to_numpy(float)
        source_h = raw.h.to_numpy(float)
        source_l = raw.l.to_numpy(float)
        for tf in TF_MINUTES:
            width = tf * 60_000
            f = aggregate(raw, tf)
            if len(f) < 210:
                manifests.append({'symbol': symbol, 'tf': tf, 'complete_bars': len(f),
                                  'signals': 0, 'status': 'INSUFFICIENT_EMA200_WARMUP'})
                continue
            masks, atr = signals(f)
            manifests.append({'symbol': symbol, 'tf': tf, 'complete_bars': len(f),
                              'signals': int(masks['long'].sum() + masks['short'].sum()),
                              'status': 'OK'})
            op, hi, lo, cl = (f[k].to_numpy(float) for k in ('o', 'h', 'l', 'c'))
            times = f.open_ms.to_numpy(np.int64)
            for i in np.flatnonzero(masks['long'] | masks['short']):
                side = 1 if masks['long'][i] else -1
                entry_i = i + 1
                if entry_i >= len(f) or not np.isfinite(atr[i]) or atr[i] <= 0:
                    continue
                entry = op[entry_i]
                risk = float(atr[i])
                stop = entry - side*risk
                target = entry + side*2*risk
                for horizon in HORIZONS:
                    end_i = entry_i + horizon
                    if end_i > len(f):
                        continue
                    start_ms = int(times[entry_i])
                    end_ms = int(times[end_i - 1]) + width
                    a = np.searchsorted(source_t, start_ms)
                    b = np.searchsorted(source_t, end_ms)
                    expected = (end_ms - start_ms) // 60_000
                    # Require continuous minute-level executable path, not just
                    # a complete aggregated signal/entry candle.
                    if b - a != expected or expected <= 0:
                        continue
                    path_o, path_l, path_h = source_o[a:b], source_l[a:b], source_h[a:b]
                    stop_hit = path_l <= stop if side > 0 else path_h >= stop
                    target_hit = path_h >= target if side > 0 else path_l <= target
                    touched = np.flatnonzero(stop_hit | target_hit)
                    exit_price = float(cl[end_i - 1])
                    outcome = 'timeout'
                    if len(touched):
                        j = touched[0]
                        if stop_hit[j]:  # conservative stop-first on same 1m candle
                            outcome = 'stop'
                            exit_price = min(path_o[j], stop) if side > 0 else max(path_o[j], stop)
                        else:
                            outcome, exit_price = 'target', target
                    raw_ret = side * (exit_price / entry - 1)
                    results.append({'symbol': symbol, 'tf': tf, 'horizon': horizon,
                                    'side': 'long' if side > 0 else 'short',
                                    'signal_ms': int(times[i] + width), 'start_ms': start_ms,
                                    'expiry_ms': end_ms, 'outcome': outcome,
                                    'target_first': float(outcome == 'target'),
                                    'gross_return': raw_ret, 'risk_pct': risk / entry})
    db.close()

    # Per symbol/TF/horizon, greedily retain chronological events whose full
    # holding intervals do not overlap. Long and short compete in one stream.
    groups = {}
    for r in results:
        groups.setdefault((r['symbol'], r['tf'], r['horizon']), []).append(r)
    chosen = []
    for events in groups.values():
        last_end = -1
        for r in sorted(events, key=lambda x: (x['signal_ms'], x['side'])):
            if r['start_ms'] >= last_end:
                chosen.append(r)
                last_end = r['expiry_ms']

    rows = []
    for tf in TF_MINUTES:
        denom = sum(m['complete_bars'] for m in manifests if m['tf'] == tf)
        for horizon in HORIZONS:
            for side in ('long', 'short', 'both'):
                cell = [r for r in chosen if r['tf'] == tf and r['horizon'] == horizon
                        and (side == 'both' or r['side'] == side)]
                eligible = [r for r in results if r['tf'] == tf and r['horizon'] == horizon
                            and (side == 'both' or r['side'] == side)]
                raw_signals = sum(m['signals'] for m in manifests if m['tf'] == tf)
                row = {'tf_minutes': tf, 'horizon_bars': horizon, 'side': side,
                       'raw_trade_n': len(eligible), 'independent_n': len(cell),
                       'coverage_of_complete_bars': raw_signals / denom if denom else 0.0,
                       'coverage_note': 'raw direction signals / available complete bars; may exceed 1 due two sides',
                       'status': 'NOT_EVALUABLE' if len(cell) < MIN_TRADES else 'EXPLORATORY'}
                if cell:
                    n = len(cell)
                    row.update({
                        'target_first_rate': float(np.mean([r['target_first'] for r in cell])),
                        'target_first_wilson95': wilson(sum(r['outcome'] == 'target' for r in cell), n),
                        'target_first_day_cluster95': cluster_ci(cell, 'target_first', SEED+tf+horizon),
                        'stop_rate': float(np.mean([r['outcome'] == 'stop' for r in cell])),
                        'timeout_rate': float(np.mean([r['outcome'] == 'timeout' for r in cell])),
                        'gross_mean_pct': float(np.mean([r['gross_return'] for r in cell])*100),
                    })
                    for label, cost in COSTS.items():
                        nets = [r['gross_return'] - cost for r in cell]
                        pos = [float(x > 0) for x in nets]
                        row[label+'_net_positive_rate'] = float(np.mean(pos))
                        row[label+'_net_positive_wilson95'] = wilson(sum(pos), n)
                        row[label+'_net_positive_day_cluster95'] = cluster_ci(
                            [dict(r, metric=v) for r, v in zip(cell, pos)], 'metric',
                            SEED+tf+horizon+(0 if cost == .001 else 100000))
                        row[label+'_mean_net_pct'] = float(np.mean(nets)*100)
                        row[label+'_mean_net_day_cluster95_pct'] = [
                            100*x for x in cluster_ci(
                                [dict(r, metric=r['gross_return']-cost) for r in cell],
                                'metric', SEED+tf+horizon+(0 if cost == .001 else 100000))]
                rows.append(row)

    report = [
        '# EMA20/50/200 pullback reversal — development probe', '',
        '**Decision: exploratory only; no edge is established by this report.**', '',
        '## Fixed design', '',
        f'- Read-only DB: `{DB}`; exact table/columns: `candles(symbol, open_ms, open, high, low, close, volume, ...)`.',
        '- The SQL predicate is `open_ms < cutoff`; additionally, source 1m candles must close no later than cutoff. No row at/after cutoff enters indicators, signal, entry, or outcome.',
        f'- Exclusive cutoff: `{pd.Timestamp(CUTOFF_MS, unit="ms", tz="UTC").isoformat()}`.',
        f'- Symbols: {", ".join(SYMBOLS)} (the four symbols retained in prior local continuity-screened long-history probes; SOL/XRP are excluded).',
        f'- Timeframes: {", ".join(str(x) for x in TF_MINUTES)} minutes (1m through 1d). One predeclared rule per TF; horizons {HORIZONS[0]}/{HORIZONS[1]} TF bars.',
        '- Regime: EMA20>EMA50>EMA200 and EMA200 rising for long; strict inverse and falling EMA200 for short. EMAs are close-based, adjust=False.',
        '- Pullback + confirmation is a single candle: long low lies in [EMA20−1ATR14, EMA20], bullish candle closes above prior high; short high lies in [EMA20, EMA20+1ATR14], bearish candle closes below prior low.',
        '- Entry next TF candle open; stop is 1 ATR14 from entry, target 2 times that entry-to-stop distance; timeout after 10/20 full TF candles.',
        '- Stop/target path checked against original 1m OHLC. If both touch in the same minute, stop wins. At timeout, exit at final TF close.',
        '- Separate chronological non-overlap selection for each symbol/TF/horizon; both directions compete, selection uses timestamps only, not outcomes.',
        '- Fee scenarios are round-trip costs of 0.10% and 0.30%, deducted from unlevered return. No additional slippage, spread, funding, or margin model.',
        '- Accuracy is target-first outcome rate (not candle-direction accuracy); net-positive rate is reported separately after costs. Coverage is directional signals / complete TF bars; both-side coverage can exceed 100%.',
        '- Uncertainty: 95% UTC-day cluster bootstrap (2,000 replicates) and Wilson interval for target-first/net-positive proportions. Cells with fewer than 30 non-overlapping trades are NOT_EVALUABLE.',
        '- No whole-DB hash was computed. No M4 confidence calibration, no leverage PnL, no sealed-data evaluation, and no post-result tuning.',
        '', '## Source 1m continuity (strict gaps are excluded from aggregate bars and trade paths)', '',
        '| Symbol | Cutoff rows | Missing 1m intervals | Gap count | Largest gap (minutes) |',
        '|---|---:|---:|---:|---:|']
    for s, q in source_checks.items():
        report.append(f"| {s} | {q['rows']} | {q['missing_1m']} | {q['gap_count']} | {q['largest_gap_minutes']} |")
    report += ['', '## Results', '',
        '| TF | Horizon | Side | Raw n | Independent N | Coverage | Target-first (cluster 95% CI) | Stop | Timeout | Net-positive base | Mean net base % (cluster CI) | Net-positive stress | Mean net stress % (cluster CI) | Status |',
        '|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---|---:|---|---|']
    for r in rows:
        def pct(v): return '—' if v is None else f'{v:.1%}'
        def ci(key):
            x=r.get(key)
            return '—' if not x else f'[{x[0]:.1%}, {x[1]:.1%}]'
        def pctci(key, val):
            x=r.get(key)
            return '—' if not x else f"{val:.3f} [{x[0]:.3f}, {x[1]:.3f}]"
        report.append('| {tf}m | {h} | {side} | {raw} | {n} | {cov} | {target} {tci} | {stop} | {timeout} | {npb} | {mb} | {nps} | {ms} | {status} |'.format(
            tf=r['tf_minutes'], h=r['horizon_bars'], side=r['side'], raw=r['raw_trade_n'],
            n=r['independent_n'], cov=pct(r['coverage_of_complete_bars']),
            target=pct(r.get('target_first_rate')),
            tci=ci('target_first_day_cluster95'), stop=pct(r.get('stop_rate')),
            timeout=pct(r.get('timeout_rate')),
            npb=pct(r.get('base_0.1pct_RT_net_positive_rate')),
            mb=pctci('base_0.1pct_RT_mean_net_day_cluster95_pct', r.get('base_0.1pct_RT_mean_net_pct', float('nan'))),
            nps=pct(r.get('stress_0.3pct_RT_net_positive_rate')),
            ms=pctci('stress_0.3pct_RT_mean_net_day_cluster95_pct', r.get('stress_0.3pct_RT_mean_net_pct', float('nan'))),
            status=r['status']))
    report += ['', '## Availability and limits', '',
        '| Symbol | TF | Complete bars | Direction signals | Availability |',
        '|---|---:|---:|---:|---|']
    for m in manifests:
        report.append(f"| {m['symbol']} | {m['tf']}m | {m['complete_bars']} | {m['signals']} | {m['status']} |")
    report += ['', '- “Direction signals” counts raw candidates before entry-path availability and non-overlap selection. Coverage denominator is pooled complete bars across the four symbols.',
        '- Cross-timeframe events are not deduplicated. The daily and long TF cells may be weakly supported because EMA200 requires a long warm-up and the local archive has finite history.',
        '- Directional return accuracy, M4 calibration, leverage-adjusted PnL, liquidation risk, and generalization beyond this dev slice are not established.',
        '- This is one uncalibrated hypothesis evaluation, not a sealed test. Do not treat the best-looking cell as selected evidence.', '']
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n'.join(report), encoding='utf-8')
    print('REPORT', out_path)
    print('source_continuity', source_checks)
    print('candidate_records', len(results), 'nonoverlap_records', len(chosen), 'result_rows', len(rows))


if __name__ == '__main__':
    main()
