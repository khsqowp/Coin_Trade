"""Offline relative-strength regime research. Signals at t earn returns at t+1."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import time
import numpy as np
import pandas as pd


UNIVERSE = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "JUP", "ARB", "FIL", "VET",
    "CAKE", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]  # copy of app/momentum_rotation_loop.UNIVERSE (not imported: avoid live-module side effects)


@dataclass(frozen=True)
class Config:
    detector: str = 'baseline'
    action: str = 'baseline'
    threshold: float = 0.5
    direction: str = 'above'
    scale: float = 0.5
    lookback: int = 28
    reversal: int = 5
    target_vol: float = 0.3
    L: int = 14
    R: int = 2
    K: int = 12

    def label(self):
        return '|'.join(f'{k}={v}' for k, v in asdict(self).items())


def _read_vision(path, cols):
    f = pd.read_csv(path, header=None, usecols=range(cols), low_memory=False)
    f = f.apply(pd.to_numeric, errors='coerce').dropna(subset=[0])
    t = f[0].astype('int64')
    t = t.where(t < 10**14, t // 1000)  # microsecond guard
    f.index = pd.to_datetime(t, unit='ms')
    return f


def load_cache(root=Path('.rs_cache')):
    """Daily closes (UTC last 1h close of day) + daily summed funding from the local data.binance.vision cache."""
    closes, funding, warnings = {}, {}, []
    for base in UNIVERSE:
        p = Path(root) / 'vision' / 'klines_1h' / f'{base}USDT.csv.gz'
        if not p.exists():
            continue
        try:
            f = _read_vision(p, 6)
            f = f[~f.index.duplicated()].sort_index()
            c = f[4].where(lambda x: x > 0).resample('1D').last()
            closes[base] = c
        except Exception as exc:  # noqa: BLE001
            warnings.append(f'{p}: {exc}'); continue
        p = Path(root) / 'vision' / 'funding' / f'{base}USDT.csv.gz'
        if p.exists():
            try:
                f = _read_vision(p, 3)
                funding[base] = f[2].fillna(0).resample('1D').sum()
            except Exception as exc:  # noqa: BLE001
                warnings.append(f'{p}: {exc}')
    if not closes:
        return pd.DataFrame(), pd.DataFrame(), warnings
    close = pd.DataFrame(closes).sort_index()
    close = close.reindex(pd.date_range(close.index.min(), close.index.max(), freq='D'))
    fund = pd.DataFrame(funding).reindex(index=close.index, columns=close.columns).fillna(0)
    return close, fund, warnings


def percentile(s, window=365, minimum=180):
    """Trailing inclusive empirical percentile; ties use pandas average rank."""
    return s.rolling(window, min_periods=minimum).rank(pct=True)


def ranked_book(close, L, K):
    mom = close.pct_change(L, fill_method=None)
    valid = mom.notna() & close.notna()
    rank = mom.where(valid).rank(axis=1, method='first')
    n = valid.sum(axis=1)
    weights = (rank.gt(n - K, axis=0).astype(float) - rank.le(K).astype(float)) * (0.5 / K)
    return weights.where(n.ge(2 * K), 0, axis=0).to_numpy()


def held_book(book, index, start, R):
    positions = np.flatnonzero(index >= pd.Timestamp(start))
    out = np.zeros_like(book)
    rebalance = np.zeros(len(index), dtype=bool)
    if len(positions):
        first = positions[0]
        selected = first + ((positions - first) // R) * R
        out[positions] = book[selected]
        rebalance[first::R] = True
    return out, rebalance


def mean_correlation(ret, window=30):
    """All pairs, pairwise-complete rolling correlation (45 names is small)."""
    sums = np.zeros(len(ret))
    counts = np.zeros(len(ret))
    for i, name in enumerate(ret.columns):
        for other in ret.columns[i + 1:]:
            c = ret[name].rolling(window, min_periods=window).corr(ret[other]).to_numpy()
            ok = np.isfinite(c)
            sums[ok] += c[ok]
            counts[ok] += 1
    return pd.Series(np.divide(sums, counts, out=np.full(len(ret), np.nan), where=counts > 0), index=ret.index)


def detectors(close, funding, baseline=None):
    idx = close.index
    btc = close.get('BTC', pd.Series(np.nan, index=idx))
    ret = close.pct_change(fill_method=None)
    br = btc.pct_change(fill_method=None)
    d = {}
    for n in (50, 100, 200):
        sma = btc.rolling(n, min_periods=n).mean()
        d[f'btc_trend_{n}'] = (btc / sma - 1)
        d[f'btc_slope_{n}'] = np.sign(sma.diff(20))
    vol = br.rolling(30, min_periods=30).std() * np.sqrt(365)
    d['btc_vol'] = vol
    d['btc_vol_pct'] = percentile(vol)
    d['btc_vol_ratio'] = vol / (br.rolling(180, min_periods=180).std() * np.sqrt(365))
    dispersion = close.pct_change(14, fill_method=None).std(axis=1)
    d['dispersion'] = dispersion
    d['dispersion_pct'] = percentile(dispersion)
    for n in (50, 200):
        sma = close.rolling(n, min_periods=n).mean()
        valid = close.notna() & sma.notna()
        d[f'breadth_{n}'] = (close.gt(sma) & valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)
    corr = mean_correlation(ret)
    d['corr'] = corr
    d['corr_pct'] = percentile(corr)
    dd = btc / btc.rolling(180, min_periods=180).max() - 1
    bm = btc.pct_change(14, fill_method=None)
    d['btc_drawdown'], d['btc_mom14'] = dd, bm
    d['rebound'] = ((dd < -0.2) & (bm > 0.15)).astype(float).where(dd.notna() & bm.notna())
    fm = funding.mean(axis=1).rolling(7, min_periods=7).mean()
    d['funding_mean'], d['funding_pct'] = fm, percentile(fm)
    d['market_mom'] = close.pct_change(30, fill_method=None).mean(axis=1)
    if baseline is not None:
        w = baseline['weights']
        d['book_carry'] = (w * funding).sum(axis=1)
        # Baseline earned returns through t are known at the close of t.
        d['strategy_vol'] = baseline['net'].reindex(idx).rolling(30, min_periods=30).std() * np.sqrt(365)
    return pd.DataFrame(d, index=idx)


class Engine:
    def __init__(self, close, funding, start='2022-01-01'):
        self.close = close
        self.funding = funding.reindex_like(close).fillna(0)
        self.start = start
        self.ret = close.pct_change(fill_method=None).fillna(0).to_numpy()
        self.books = {}
        self.features = pd.DataFrame(index=close.index)

    def book(self, L, K, R):
        key = (L, K, R)
        if key not in self.books:
            self.books[key] = held_book(ranked_book(self.close, L, K), self.close.index, self.start, R)
        return self.books[key]

    def prepare(self):
        baseline = self.run(Config())
        self.features = detectors(self.close, self.funding, baseline)
        return baseline

    def run(self, config):
        w, rb = self.book(config.L, config.K, config.R)
        w = w.copy()
        state = np.zeros(len(w), dtype=int)
        scale = np.ones(len(w))
        if config.action != 'baseline':
            x = self.features[config.detector].to_numpy()
            flag = regime_flag(x, config)
            state = flag.astype(int)
            if config.action == 'scale':
                scale[flag] = config.scale
            elif config.action == 'lookback':
                alternative, _ = self.book(config.lookback, config.K, config.R)
                w[flag] = alternative[flag]
            elif config.action == 'sleeve':
                alternative, _ = self.book(config.reversal, config.K, config.R)
                w[flag] = -alternative[flag] if config.scale else 0
            elif config.action == 'continuous':
                scale = np.clip(np.divide(config.target_vol, x, out=np.ones_like(x), where=np.isfinite(x) & (x > 0)), 0.25, 1.5)
                state = np.zeros(len(w), dtype=int)
        w *= scale[:, None]
        delta = np.abs(np.diff(w, axis=0, prepend=np.zeros((1, w.shape[1])))).sum(axis=1)
        earned = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
        turnover = np.r_[0, delta[:-1]]
        gross = (earned * self.ret).sum(axis=1) - turnover * 0.001
        net = gross - (earned * self.funding.to_numpy()).sum(axis=1)
        idx = self.close.index
        mask = idx >= pd.Timestamp(self.start)
        result = pd.DataFrame({'net': net, 'without_funding': gross, 'turnover': turnover,
                               'gross': np.abs(earned).sum(axis=1), 'rebalance': np.r_[False, rb[:-1]],
                               'flip': np.r_[False, state[1:] != state[:-1]]}, index=idx).loc[mask]
        # A signal change at t is recorded as a flip on earning date t+1.
        result['flip'] = pd.Series(np.r_[False, False, (state[1:] != state[:-1])[:-1]], index=idx).loc[mask]
        return {'daily': result, 'net': result.net, 'weights': pd.DataFrame(w, index=idx, columns=self.close.columns)}


def regime_flag(x, c):
    if c.direction == 'above':
        return np.isfinite(x) & (x > c.threshold)
    if c.direction == 'below':
        return np.isfinite(x) & (x < c.threshold)
    return np.isfinite(x) & ((x < c.threshold) | (x > 1 - c.threshold))


def metrics(daily, column='net'):
    if daily.empty:
        return {k: None for k in ('CAGR', 'MDD', 'Calmar', 'Sharpe', 'worst_day', 'time_in_market', 'annual_turnover', 'rebalances_yr', 'flips_yr')} | {'days': 0, 'years': {}}
    r = daily[column]
    equity = (1 + r).cumprod()
    peak = equity.cummax().clip(lower=1)
    mdd = float((1 - equity / peak).max())
    years = len(r) / 365
    cagr = float(equity.iloc[-1] ** (1 / years) - 1) if equity.iloc[-1] > 0 else -1.0
    std = r.std()
    return {'CAGR': cagr, 'MDD': mdd, 'Calmar': cagr / mdd if mdd > 0 else None,
            'Sharpe': float(r.mean() / std * np.sqrt(365)) if std > 0 else None,
            'worst_day': float(r.min()), 'time_in_market': float((daily.gross > 0.05).mean()),
            'annual_turnover': float(daily.turnover.sum() / years),
            'rebalances_yr': float(daily.rebalance.sum() / years), 'flips_yr': float(daily.flip.sum() / years),
            'days': len(r), 'years': {str(y): float((1 + s).prod() - 1) for y, s in r.groupby(r.index.year)}}


def diagnostic(features, baseline):
    rows = []
    for name, series in features.items():
        lo = series.expanding(min_periods=180).quantile(1 / 3)
        hi = series.expanding(min_periods=180).quantile(2 / 3)
        bucket = pd.Series(np.where(series <= lo, 0, np.where(series <= hi, 1, 2)), index=series.index)
        bucket = bucket.where(series.notna() & lo.notna()).shift(1).reindex(baseline.index)
        for b in range(3):
            r = baseline.net[bucket == b]
            std = r.std()
            signs = {str(y): int(np.sign(s.mean())) for y, s in r.groupby(r.index.year)}
            rows.append({'detector': name, 'tercile': b + 1, 'n': len(r), 'mean': float(r.mean()),
                         'Sharpe': float(r.mean() / std * np.sqrt(365)) if std > 0 else None, 'year_signs': signs})
    return rows


def threshold_grid(name):
    if name.endswith('_pct') or name.startswith('breadth'):
        return [0.25, 0.5, 0.75]
    if name.startswith('btc_slope') or name == 'rebound':
        return [-0.5, 0, 0.5]
    if name == 'btc_vol_ratio':
        return [0.8, 1, 1.2]
    if name in ('btc_vol', 'strategy_vol'):
        return [0.3, 0.6, 0.9]
    if name == 'dispersion':
        return [0.05, 0.1, 0.2]
    if name == 'corr':
        return [0.3, 0.5, 0.7]
    if name in ('funding_mean', 'book_carry'):
        return [-0.0001, 0, 0.0001]
    return [-0.1, 0, 0.1]


def config_grid(features):
    out = []
    for name in features:
        directions = ['above', 'below']
        if name.endswith('_pct') or name.startswith('breadth'):
            directions += ['extremes']
        for threshold in threshold_grid(name):
            for direction in directions:
                if direction == 'extremes' and threshold >= 0.5:
                    continue
                common = dict(detector=name, threshold=threshold, direction=direction)
                out += [Config(**common, action='scale', scale=s) for s in (0, 0.5)]
                out += [Config(**common, action='lookback', lookback=L) for L in (7, 14, 28)]
                out += [Config(**common, action='sleeve', reversal=L, scale=1) for L in (3, 5, 7)]
                out += [Config(**common, action='sleeve', reversal=5, scale=0)]
    for name in ('btc_vol', 'strategy_vol'):
        if name in features:
            out += [Config(detector=name, action='continuous', target_vol=v) for v in (0.15, 0.3, 0.45)]
    return out


def neighbours(config):
    grids = {'threshold': threshold_grid(config.detector)}
    if config.action == 'scale':
        grids['scale'] = [0, 0.5]
    if config.action == 'lookback':
        grids['lookback'] = [7, 14, 28]
    if config.action == 'sleeve':
        grids['reversal'] = [3, 5, 7]
        grids['scale'] = [0, 1]
    if config.action == 'continuous':
        grids = {'target_vol': [0.15, 0.3, 0.45]}
    out = []
    values = asdict(config)
    for key, grid in grids.items():
        i = grid.index(values[key])
        for j in (i - 1, i + 1):
            if 0 <= j < len(grid):
                out.append(Config(**(values | {key: grid[j]})))
    return out


def self_test():
    rng = np.random.default_rng(73)
    idx = pd.date_range('2020-01-01', periods=1200)
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.03, (len(idx), 26)), axis=0)), index=idx,
                         columns=['BTC'] + [f'S{i}' for i in range(25)])
    fund = pd.DataFrame(rng.normal(0, 0.0002, close.shape), index=idx, columns=close.columns)
    a = Engine(close, fund, '2021-01-01')
    a.prepare()
    cut = idx[1000]
    altered = close.copy()
    altered.loc[cut:] *= rng.uniform(0.5, 2, altered.loc[cut:].shape)
    altered_fund = fund.copy()
    altered_fund.loc[cut:] += 0.01
    b = Engine(altered, altered_fund, '2021-01-01')
    b.prepare()
    configs = config_grid(a.features)
    before = idx < cut
    for c in [Config()] + configs:
        np.testing.assert_allclose(a.run(c)['weights'].loc[before], b.run(c)['weights'].loc[before], atol=0, rtol=0)
    result = a.run(Config())
    w = result['weights'].to_numpy()
    daily = result['daily']
    earned = result['weights'].shift(1).fillna(0)
    expected = (earned * close.pct_change(fill_method=None).fillna(0)).sum(axis=1)
    expected -= earned.diff().abs().sum(axis=1).fillna(0) * 0.001
    expected -= (earned * fund).sum(axis=1)
    np.testing.assert_allclose(daily.net, expected.loc[daily.index], atol=1e-14)
    np.testing.assert_allclose(w.sum(axis=1), 0, atol=1e-14)
    started = time.perf_counter()
    for _ in range(10):
        a.run(configs[0])
    elapsed = (time.perf_counter() - started) / 10
    assert elapsed < 1, f'single config took {elapsed:.3f}s'
    return {'configs_checked': len(configs) + 1, 'seconds_per_config': elapsed, 'future_cut': str(cut.date())}
