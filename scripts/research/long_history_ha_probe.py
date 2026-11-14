#!/usr/bin/env python3
"""Exploratory causal 30m Heikin-Ashi continuation probe on local Vision data."""
import sqlite3
import numpy as np
import pandas as pd

DB = 'chart_predictor/data/vision_dev.sqlite'
CUTOFF_MS = int(pd.Timestamp('2026-10-09T00:00:00Z').timestamp() * 1000)
SYMBOLS = ('BNBUSDT', 'BTCUSDT', 'DOGEUSDT', 'ETHUSDT')  # exclude SOL/XRP gap-contaminated history
HORIZONS = (10, 20)
LEVERAGES = (10, 20)
ROUND_TRIP_FEE = 0.001


def main():
    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    results = []
    for symbol in SYMBOLS:
        raw = pd.read_sql_query(
            'SELECT open_ms,open AS o,high AS h,low AS l,close AS c,volume AS v '
            'FROM candles WHERE symbol=? AND open_ms<? ORDER BY open_ms',
            db, params=(symbol, CUTOFF_MS),
        )
        raw['dt'] = pd.to_datetime(raw.open_ms, unit='ms', utc=True)
        raw = raw.set_index('dt')
        bars = raw.resample('30min', origin='epoch', label='left', closed='left').agg(
            {'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last', 'v': 'sum', 'open_ms': 'first'}
        ).dropna()
        bars = bars[bars.open_ms + 1_800_000 <= CUTOFF_MS].copy()

        # Heikin-Ashi state is recursive and uses only this and earlier completed bars.
        ha_close = (bars.o + bars.h + bars.l + bars.c) / 4
        ha_open = np.empty(len(bars))
        ha_open[0] = (bars.o.iloc[0] + bars.c.iloc[0]) / 2
        for i in range(1, len(bars)):
            ha_open[i] = (ha_open[i - 1] + ha_close.iloc[i - 1]) / 2
        green = pd.Series(ha_close.to_numpy() > ha_open, index=bars.index)
        prior_high = bars.h.shift(1).rolling(20, min_periods=20).max()
        prior_low = bars.l.shift(1).rolling(20, min_periods=20).min()

        # [00:00,04:00) is labeled 04:00, preventing use of an unfinished 4h candle.
        h4 = bars.c.resample('4h', origin='epoch', label='right', closed='left').last().dropna()
        ema50 = h4.ewm(span=50, adjust=False, min_periods=50).mean()
        h4_up = ema50.gt(ema50.shift(1)).reindex(bars.index, method='ffill').ffill().fillna(False).astype(bool)
        previous_two_green = green.shift(1).rolling(2, min_periods=2).sum().eq(2)
        previous_two_red = (~green).shift(1).rolling(2, min_periods=2).sum().eq(2)
        signals = {
            'long': (green & previous_two_green & bars.c.gt(prior_high) & h4_up).to_numpy(),
            'short': ((~green) & previous_two_red & bars.c.lt(prior_low) & (~h4_up)).to_numpy(),
        }

        previous_close = bars.c.shift(1)
        true_range = pd.concat((bars.h - bars.l, (bars.h - previous_close).abs(),
                                (bars.l - previous_close).abs()), axis=1).max(axis=1)
        atr14 = true_range.rolling(14, min_periods=14).mean().to_numpy()
        op, hi, lo, cl = (bars[k].to_numpy(float) for k in ('o', 'h', 'l', 'c'))
        times = bars.open_ms.to_numpy(np.int64)

        for side_name, side, mask in (('long', 1, signals['long']), ('short', -1, signals['short'])):
            candidates = np.flatnonzero(mask)
            for horizon in HORIZONS:
                full_horizon = [i for i in candidates if i + 1 + horizon <= len(bars)]
                for leverage in LEVERAGES:
                    n = first_target = net_positive = liquidation_rejects = 0
                    net_returns = []
                    for i in full_horizon:
                        entry_i = i + 1
                        entry = op[entry_i]
                        risk = 1.5 * atr14[i]
                        if not np.isfinite(risk) or risk <= 0:
                            continue
                        if risk / entry >= 1 / leverage - 0.005:
                            liquidation_rejects += 1
                            continue
                        stop = entry - side * risk
                        target = entry + side * 2 * risk
                        exit_price = cl[entry_i + horizon - 1]
                        reason = 'timeout'
                        for j in range(entry_i, entry_i + horizon):
                            hit_stop = lo[j] <= stop if side > 0 else hi[j] >= stop
                            hit_target = hi[j] >= target if side > 0 else lo[j] <= target
                            if hit_stop or hit_target:
                                # Conservative same-bar ambiguity convention: stop wins ties.
                                exit_price = stop if hit_stop else target
                                reason = 'stop' if hit_stop else 'target'
                                break
                        net = side * (exit_price / entry - 1) - ROUND_TRIP_FEE
                        net_returns.append(net)
                        n += 1
                        first_target += reason == 'target'
                        net_positive += net > 0
                    if n:
                        results.append((symbol, side_name, horizon, leverage, n, len(full_horizon),
                                        liquidation_rejects, first_target / n, net_positive / n,
                                        np.mean(net_returns) * 100))
    db.close()
    print('symbol,side,horizon_bars,leverage,n,eligible_signals,liq_rejected,target_first,net_positive,mean_net_pct')
    for row in results:
        print(','.join(map(str, row)))
    for horizon in HORIZONS:
        for leverage in LEVERAGES:
            for side in ('long', 'short'):
                subset = [r for r in results if r[1] == side and r[2] == horizon and r[3] == leverage]
                total = sum(r[4] for r in subset)
                if total:
                    print('POOLED', side, horizon, leverage, 'n', total,
                          'target_first', sum(r[4] * r[7] for r in subset) / total,
                          'net_positive', sum(r[4] * r[8] for r in subset) / total,
                          'weighted_mean_net_pct', sum(r[4] * r[9] for r in subset) / total)


if __name__ == '__main__':
    main()
