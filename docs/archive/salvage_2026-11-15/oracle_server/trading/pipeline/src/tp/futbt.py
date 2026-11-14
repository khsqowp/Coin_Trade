"""USDT-M perpetual-futures backtest engine (research only: NO order functionality exists in this module).

Signals: decided at the CLOSE of bar t, executed at the OPEN of bar t+1 (same convention as tp.bt). sig in [-1, 1]:
sign = direction (short allowed), magnitude = size multiple of the base exposure (volatility targeting etc.).
Sizing: target notional = |sig| * nf * equity_at_open, with nf (notional fraction) defaulting to `lev` (= the whole equity is posted as
isolated margin, margin = notional/lev). nf=0.25 reproduces the Risk Engine 25%-of-equity notional cap.
Costs (tp.costs.CostModel): fee_side on every traded notional, adverse slippage per side (plus optional bar-range term), real funding
from the 8h history (settlement at 00/08/16 UTC): margin -= qty * mark * rate (longs pay when rate > 0).
LIQUIDATION (mandatory, isolated margin): within a bar, if margin_balance + qty*(adverse_extreme - avg_entry) <= mmr*|qty|*adverse_extreme
(extreme = bar low for longs / high for shorts, a conservative stand-in for the mark price) the position is liquidated: the WHOLE position
margin is lost (the clearance fee 1.25% of notional exceeds the leftover maintenance margin), the strategy stays locked out of that
direction until its signal leaves it. Bankrupt (equity <= 0) stops the simulation.
Mark-price approximation: last-price OHLC from public klines (mark-price klines would be slightly smoother)."""
import numpy as np
import pandas as pd

from .costs import CostModel


def funding_per_bar(index, bar_ms, f_ts_ms, f_rate):
    """Sum of funding rates settled inside (bar_open, bar_open+bar] for every bar. f_ts_ms sorted ascending."""
    if f_ts_ms is None or len(f_ts_ms) == 0:
        return np.zeros(len(index))
    t0 = ((index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(milliseconds=1)).values.astype("int64")   # unit-agnostic
    cs = np.concatenate([[0.0], np.cumsum(f_rate)])
    lo = np.searchsorted(f_ts_ms, t0, side="right")
    hi = np.searchsorted(f_ts_ms, t0 + bar_ms, side="right")
    return cs[hi] - cs[lo]


def simulate(df, sig, cost, lev=1.0, nf=None, fr=None, rebalance_band=0.15, bar_ms=None):
    """Returns dict(ret: Series, h: Series (|qty|>0 at close), fees, funding, n_liq, n_open, bankrupt, equity: Series)."""
    n = len(df)
    nf = float(lev if nf is None else nf)
    o, h_, l_, c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
    tgt = np.r_[0.0, np.asarray(sig, float)[:-1]]            # position wanted during bar i = signal of bar i-1
    fr = np.zeros(n) if fr is None else fr
    fee_s, slip0, mmr = cost.fee_side, cost.slip, cost.mmr
    rng_frac = cost.slip_range_frac
    cash, qty, entry, margin = 1.0, 0.0, 0.0, 0.0
    eq = np.empty(n)
    hold = np.zeros(n, bool)
    fees = fund = 0.0
    n_liq = n_open = 0
    lock = 0                                                  # direction locked after a liquidation (+1/-1/0)
    bankrupt = False
    prev_eq = 1.0
    q_unit = 0.0
    for i in range(n):
        t = tgt[i]
        if lock != 0 and (t == 0 or np.sign(t) != lock):
            lock = 0
        if lock != 0:
            t = 0.0
        if qty == 0.0 and t == 0.0:
            eq[i] = cash
            prev_eq = cash
            continue
        # ---- rebalance at the open
        e_open = cash + margin + qty * (o[i] - entry)
        if qty == 0.0:
            q_unit = nf * e_open / o[i]          # base units for |sig|=1, fixed for the whole trade (no rebalancing for price/equity drift)
        want = np.sign(t) * abs(t) * q_unit if t != 0 else 0.0                 # target qty (base units)
        need = (want != qty) and (qty == 0.0 or want == 0.0 or np.sign(want) != np.sign(qty) or abs(want - qty) > rebalance_band * abs(qty))
        if need:
            slip = max(slip0, rng_frac * (h_[i] - l_[i]) / o[i]) if rng_frac else slip0
            dq = want - qty
            px = o[i] * (1 + slip * np.sign(dq))
            # reduce / close / flip part
            if qty != 0.0 and np.sign(dq) != np.sign(qty):
                closing = min(abs(dq), abs(qty))
                frac = closing / abs(qty)
                realized = np.sign(qty) * closing * (px - entry)
                rel = margin * frac
                cash += rel + realized
                margin -= rel
                fee = closing * px * fee_s
                cash -= fee
                fees += fee
                qty -= np.sign(qty) * closing
                dq = want - qty
                if qty == 0.0:
                    entry, margin = 0.0, 0.0
            # open / add part
            if dq != 0.0 and (qty == 0.0 or np.sign(dq) == np.sign(qty)):
                notional = abs(dq) * px
                cap = cash / (1.0 / lev + fee_s) if lev > 0 else 0.0
                if notional > cap:
                    notional = max(cap, 0.0)
                if notional > 0:
                    add_q = np.sign(dq) * notional / px
                    m_add = notional / lev
                    fee = notional * fee_s
                    entry = (qty * entry + add_q * px) / (qty + add_q) if qty != 0.0 else px
                    if qty == 0.0:
                        n_open += 1
                    qty += add_q
                    cash -= m_add + fee
                    margin += m_add
                    fees += fee
        # ---- funding, liquidation, mark-to-market
        if qty != 0.0:
            if fr[i] != 0.0:
                pay = qty * c[i] * fr[i]
                margin -= pay
                fund += pay
            ext = l_[i] if qty > 0 else h_[i]
            if margin + qty * (ext - entry) <= mmr * abs(qty) * ext:
                lock = 1 if qty > 0 else -1
                n_liq += 1
                qty, entry, margin = 0.0, 0.0, 0.0                # whole margin lost
        e = cash + margin + (qty * (c[i] - entry) if qty != 0.0 else 0.0)
        eq[i] = e
        hold[i] = qty != 0.0
        if e <= 1e-9:
            bankrupt = True
            eq[i:] = 0.0
            break
    s = pd.Series(eq, index=df.index)
    ret = s.pct_change().fillna(s.iloc[0] - 1.0)
    if bankrupt:
        ret = ret.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return {"ret": ret, "h": pd.Series(hold.astype(float), index=df.index), "equity": s, "fees": fees, "funding": fund,
            "n_liq": n_liq, "n_open": n_open, "bankrupt": bankrupt}


def load_funding(symbol_usdt, db_path=None):
    """(ts_ms ndarray, rate ndarray) from deriv.sqlite funding_hist (public /fapi/v1/fundingRate)."""
    import sqlite3
    from . import deriv
    con = sqlite3.connect("file:%s?mode=ro" % (db_path or deriv.DB), uri=True)
    rows = con.execute("SELECT ts_ms, rate FROM funding_hist WHERE symbol=? ORDER BY ts_ms", (symbol_usdt,)).fetchall()
    con.close()
    return np.array([r[0] for r in rows], dtype="int64"), np.array([r[1] for r in rows], float)


def mirror(df):
    """Inverse-price mirror: a LONG strategy applied to mirror(df) yields the matching SHORT signal on df (o'=1/o, h'=1/l, l'=1/h)."""
    m = pd.DataFrame({"open": 1.0 / df["open"], "high": 1.0 / df["low"], "low": 1.0 / df["high"], "close": 1.0 / df["close"],
                      "volume": df["volume"]}, index=df.index)
    for k in df.columns:
        if k not in m.columns:
            m[k] = df[k]
    return m
