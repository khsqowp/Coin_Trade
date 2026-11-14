"""Performance statistics with multiple-testing correction (Bailey & Lopez de Prado). Pure numpy/stdlib, deterministic."""
import math
from statistics import NormalDist

import numpy as np

_N = NormalDist()
EULER = 0.5772156649015329


def sharpe_period(r):
    r = np.asarray(r, float)
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    return float(r.mean() / sd) if sd > 0 else 0.0


def sharpe_annual(r, ppy):
    return sharpe_period(r) * math.sqrt(ppy)


def moments(r):
    r = np.asarray(r, float)
    if len(r) < 4 or r.std() == 0:
        return 0.0, 3.0
    z = (r - r.mean()) / r.std()
    return float((z ** 3).mean()), float((z ** 4).mean())


def psr(r, sr_star=0.0):
    """Probabilistic Sharpe ratio: P(true per-period SR > sr_star) given sample skew/kurtosis and length."""
    r = np.asarray(r, float)
    T = len(r)
    if T < 10:
        return 0.5
    sr = sharpe_period(r)
    sk, ku = moments(r)
    den = math.sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4.0 * sr ** 2))
    return float(_N.cdf((sr - sr_star) * math.sqrt(T - 1) / den))


def expected_max_sr(sr_var, n_trials):
    """E[max SR] over n independent trials with variance sr_var of the SR estimates (per-period units)."""
    if n_trials < 2 or sr_var <= 0:
        return 0.0
    return math.sqrt(sr_var) * ((1 - EULER) * _N.inv_cdf(1 - 1.0 / n_trials) + EULER * _N.inv_cdf(1 - 1.0 / (n_trials * math.e)))


def dsr(r, trial_sr_period, n_trials=None):
    """Deflated Sharpe ratio: PSR against the expected maximum SR of the tried variants. trial_sr_period: per-period SRs of ALL trials."""
    trial_sr_period = np.asarray(trial_sr_period, float)
    n = n_trials or len(trial_sr_period)
    var = float(trial_sr_period.var(ddof=1)) if len(trial_sr_period) > 1 else 0.0
    sr0 = expected_max_sr(var, n)
    return psr(r, sr0), sr0


def max_drawdown(r):
    eq = np.cumprod(1 + np.asarray(r, float))
    peak = np.maximum.accumulate(eq)
    return float((1 - eq / peak).max()) if len(eq) else 0.0


def summarize(r, ppy):
    r = np.asarray(r, float)
    return {"bars": len(r), "total_return": float(np.prod(1 + r) - 1), "sharpe": round(sharpe_annual(r, ppy), 3),
            "mdd": round(max_drawdown(r), 4), "psr0": round(psr(r), 3)}
