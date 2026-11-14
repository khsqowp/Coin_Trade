"""Coin LIQUIDATION-CLUSTER follower (UNVERIFIED). Idea: price tends to be pulled toward dense liquidation clusters.
Long when the estimated short-liquidation mass ABOVE price dominates the long-liquidation mass below (liq_imb>0.25), the
nearest dense cluster is within 3% (liq_dist_up_pct) and price momentum is not negative. Exit when the cluster is reached
(<0.3%), imbalance flips, or ATRx2.5 trailing stop.

Needs the extra columns liq_imb / liq_dist_up_pct produced by tp.liqmap (Binance-public proxy, see docs). The proxy only
has ~28 days of OI history + whatever the collectors have accumulated, so a backtest is NOT evidence: verifiable() returns the
reason and the gate treats this strategy as UNVERIFIABLE (blocked) until the required history exists."""
import numpy as np
from tp import ind, poolkit as pk

NEEDS_LIQ = True
MIN_DAYS = 90
META = {"id": "coin_liq_cluster", "family": "liq_cluster", "market": "crypto", "profile": "crypto_fast",
        "timeframes": ["5m", "15m"], "symbols": ["BTC/USDT", "ETH/USDT"], "validation": "unverified"}
RULES = {"liq_imbalance": "short-liq mass above minus long-liq mass below > 25% of total (+-5%)",
         "cluster_near": "nearest dense cluster above within 3%", "momentum_ok": "ROC(12) >= 0",
         "cluster_reached_exit": "exit when within 0.3% of the cluster", "atr_trail_stop": "exit when close < highest close - 2.5*ATR(14)"}
PROTECTIVE = {"atr_trail_stop"}
RULE_KINDS = {"liq_imbalance": "entry", "cluster_near": "filter", "momentum_ok": "filter", "cluster_reached_exit": "exit",
              "atr_trail_stop": "protective"}


def verifiable():
    """None if enough history exists, else the reason string (read by the harness; blocks the gate)."""
    try:
        from tp import liqmap
        days = liqmap.accumulated_days()
    except Exception:       # noqa: BLE001
        days = 0.0
    if days >= MIN_DAYS:
        return None
    return "UNVERIFIABLE: liquidation-proxy history is %.1f days (< %d required); results on shorter history are not evidence" % (days, MIN_DAYS)


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    n = len(df)
    if "liq_imb" not in df.columns:
        return pk.to_series(np.zeros(n), df)
    imb, dist = df["liq_imb"], df["liq_dist_up_pct"]
    c = df["close"]
    entry = (pk.cond(disabled, "liq_imbalance", imb > 0.25) & pk.cond(disabled, "cluster_near", (dist > 0.3) & (dist <= 3.0))
             & pk.cond(disabled, "momentum_ok", ind.roc(c, 12) >= 0))
    entry &= pk.b(imb.notna()) & pk.b(dist.notna())
    exit_sig = np.zeros(n, bool) if "cluster_reached_exit" in disabled else pk.b(dist <= 0.3) | pk.b(imb < 0)
    sig = pk.position_loop(entry, c.values, ind.atr(df, 14).values, exit_sig,
                           trail_mult=None if "atr_trail_stop" in disabled else 2.5)
    return pk.to_series(sig, df)
