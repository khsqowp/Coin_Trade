"""올웨더 일봉 포트폴리오 시뮬레이터. 연구 전용이며 주문 기능이 없다."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi2(close: pd.Series) -> pd.Series:
    d = close.diff()
    up, down = d.clip(lower=0).rolling(2, min_periods=2).mean(), -d.clip(upper=0).rolling(2, min_periods=2).mean()
    rs = up / down.replace(0, np.nan)
    value = 100 - 100 / (1 + rs)
    value = value.mask(down.eq(0) & up.gt(0), 100).mask(down.eq(0) & up.eq(0), 50)
    return value.fillna(50)


def event_dates(events: pd.DataFrame | None, market: str, dates: pd.DatetimeIndex) -> tuple[set, set]:
    """E1 전일, E2 발표 당일 날짜 집합."""
    if events is None or events.empty:
        return set(), set()
    ev = events[events.market.str.upper().isin((market.upper(), "ALL"))]
    announcement = {pd.Timestamp(x).normalize() for x in ev.date}
    prior = set()
    for day in announcement:
        pos = dates.searchsorted(day)
        if 0 < pos < len(dates) and day <= dates[-1]:
            prior.add(dates[pos - 1])
    return prior, announcement


def cost_rates(market: str, role: str) -> tuple[float, float]:
    """편도 비용 (매수, 매도). ETF 국내 매도세는 없다."""
    if market.upper() == "US":
        return .0036, .0036
    base = .00015 + .0005
    return base, base + (.0018 if role == "stock" else 0.)


def cap_weight(role: str, inverse_cap: float = .25) -> float:
    return {"stock": .10, "sector": .20, "index": .50, "defensive": .50, "inverse": inverse_cap}[role]


def mean_reversion_entry(close: pd.Series, t: int) -> bool:
    return bool(rsi2(close).iloc[t] < 10 and close.iloc[t] > close.rolling(200, min_periods=200).mean().iloc[t])


def mean_reversion_exit(close: pd.Series, entry: float, age: int, t: int) -> bool:
    return bool(close.iloc[t] > close.rolling(5, min_periods=5).mean().iloc[t] or age >= 10 or close.iloc[t] <= entry * .93)


def inverse_hold_condition(index_close: pd.Series, t: int) -> bool:
    return bool(index_close.iloc[t] < index_close.rolling(200, min_periods=200).mean().iloc[t]
                and index_close.pct_change(20).iloc[t] < 0)


def target_weights(panel, regimes: pd.Series, lookback: int = 120, inverse_cap: float = .25,
                   mean_reversion: bool = True, event_overlay: bool = False,
                   events: pd.DataFrame | None = None, offset: int = 0) -> pd.DataFrame:
    """일별 종가 신호 목표비중. 모든 지표는 현재까지의 자료로 계산한다."""
    d, syms, close = panel.dates, panel.symbols, panel.c
    w = pd.DataFrame(0., index=d, columns=syms)
    prior, same = event_dates(events, panel.market, d) if event_overlay else (set(), set())
    idx = "069500" if panel.market == "KR" else "SPY"
    if idx not in syms: raise ValueError(f"기준 지수 ETF 누락: {idx}")
    roles = panel.roles
    sectors = [s for s in syms if roles[s] == "sector"]
    indices = [s for s in syms if roles[s] == "index"]
    defenses = [s for s in syms if roles[s] == "defensive"]
    inverses = [s for s in syms if roles[s] == "inverse"]
    stocks = [s for s in syms if roles[s] == "stock"]
    sma100, sma200 = close.rolling(100, min_periods=100).mean(), close.rolling(200, min_periods=200).mean()
    ret21, ret63, ret126, ret20 = (close.pct_change(n) for n in (21, 63, 126, 20))
    mr_names = indices + sectors
    mr_rsi = {s: rsi2(close[s]) for s in mr_names}
    mr_sma5 = {s: close[s].rolling(5, min_periods=5).mean() for s in mr_names}
    inverse_ok = (close[idx] < sma200[idx]) & ret20[idx].lt(0)
    stock_mom = close[stocks].pct_change(lookback) if stocks else pd.DataFrame(index=d)
    next_rebal = offset % 21
    held_mr: dict[str, tuple[float, int]] = {}
    previous_regime = None
    deferred = False
    for t, day in enumerate(d):
        regime = regimes.iloc[t]
        if regime != "RANGE": held_mr.clear()
        due = t >= next_rebal and t % 21 == offset % 21
        changed = previous_regime is not None and regime != previous_regime
        # BEAR 중 인버스 보유조건이 바뀌면(20일 수익률 양전 등) 즉시 재계산한다.
        if regime == "BEAR" and t and bool(inverse_ok.iloc[t]) != bool(inverse_ok.iloc[t-1]): changed = True
        rebal = due or changed or deferred or t == 0
        blocked_rebalance = day in prior or day in same
        if rebal and blocked_rebalance: deferred = True
        elif rebal: deferred = False
        previous_regime = regime
        row = pd.Series(0., index=syms)
        if regime == "BULL":
            scores = (ret126.iloc[t] + ret63.iloc[t]) / 2
            picks = [s for s in sectors if pd.notna(scores[s]) and scores[s] > 0 and close[s].iloc[t] > sma100[s].iloc[t]]
            picks = sorted(picks, key=lambda s: scores[s], reverse=True)[:3]
            for s in picks: row[s] += .5 / 3
            empty = 3 - len(picks)
            index_picks = [s for s in indices if pd.notna(ret126[s].iloc[t]) and ret126[s].iloc[t] > 0]
            index_picks.sort(key=lambda s: ret126[s].iloc[t], reverse=True)
            for s in index_picks[:empty]: row[s] += .5 / 3
            eligible = [s for s in stocks if bool(panel.stock_eligible[s].iloc[t]) and pd.notna(stock_mom[s].iloc[t])]
            eligible.sort(key=lambda s: stock_mom[s].iloc[t], reverse=True)
            chosen = eligible[:5]
            for s in chosen: row[s] = .10
            spare = max(0, 5 - len(chosen)) * .10
            row[idx] += min(spare, max(0, .5 - row[idx]))
        elif regime == "RANGE":
            row[idx] = .3
            bills = [s for s in defenses if "단기채권" in panel.names[s]] if panel.market == "KR" else [s for s in defenses if s == "BIL"]
            bill = bills[0] if bills else (defenses[0] if defenses else None)
            if mean_reversion and panel.market == "KR":
                previous_mr = set(held_mr)
                for s in list(held_mr):
                    entry, age = held_mr[s]; age += 1
                    if (close[s].iloc[t] > mr_sma5[s].iloc[t] or age >= 10 or close[s].iloc[t] <= entry * .93): held_mr.pop(s)
                    else: held_mr[s] = (entry, age)
                if day not in prior and day not in same:
                    candidates = [s for s in mr_names if s not in held_mr and mr_rsi[s].iloc[t] < 10 and close[s].iloc[t] > sma200[s].iloc[t]]
                    for s in candidates[:max(0, 4-len(held_mr))]: held_mr[s] = (float(close[s].iloc[t]), 0)
                for s in held_mr: row[s] += .1
                if bill: row[bill] = .3
            elif panel.market == "US":
                row[idx] = .5
                if bill: row[bill] = .5
            else:
                if bill: row[bill] = .3
        else:
            qualified = [s for s in defenses if pd.notna(ret126[s].iloc[t]) and ret126[s].iloc[t] > 0]
            qualified.sort(key=lambda s: ret126[s].iloc[t], reverse=True)
            if qualified:
                for s in qualified[:2]: row[s] = .5 / min(2, len(qualified))
            else:
                bills = [s for s in defenses if "단기채권" in panel.names[s] or s == "BIL"]
                if bills: row[bills[0]] = .5
            if inverse_cap and bool(inverse_ok.iloc[t]) and inverses: row[inverses[0]] = inverse_cap
        for s in syms: row[s] = min(max(row[s], 0), cap_weight(roles[s], inverse_cap))
        if blocked_rebalance and t:
            row = row.clip(upper=w.iloc[t-1])
        if day in prior and t:
            row = row.clip(upper=w.iloc[t-1])
        if day in same:
            for s in indices + sectors: row[s] = min(row[s], w.iloc[t-1][s] if t else 0)
        daily_mr = regime == "RANGE" and mean_reversion and panel.market == "KR"
        if daily_mr and not rebal and t:
            prev = w.iloc[t-1].copy()
            for s in indices + sectors:
                prev[s] += .1 * ((1 if s in held_mr else 0) - (1 if s in previous_mr else 0))
            w.iloc[t] = prev
        elif rebal:
            w.iloc[t] = row
        else:
            w.iloc[t] = w.iloc[t-1] if t else row
    return w

def ret120(s: pd.Series) -> pd.Series:
    return s.pct_change(120)


def simulate(panel, target: pd.DataFrame, events: pd.DataFrame | None = None,
             drawdown_breaker: bool = True, regimes: pd.Series | None = None) -> dict:
    """타깃 종가 신호, KR 다음 시가 / US 다음 종가 체결, 비용 차감."""
    d, syms = panel.dates, panel.symbols
    n, m = len(d), len(syms)
    values = np.zeros(m); cash = 1.0; eq = np.ones(n); turnover = np.zeros(n); costs = np.zeros(n)
    contributions = {role: np.zeros(n) for role in ("index", "sector", "defensive", "inverse", "stock")}
    daily_weights = np.zeros((n, m)); regime_daily = regimes.reindex(d).to_numpy() if regimes is not None else np.full(n, None, dtype=object)
    peak, breaker = 1.0, False
    tw = target.to_numpy(float); traded_breaker = False
    rates = [cost_rates(panel.market, panel.roles[s]) for s in syms]
    buy_fee = np.array([x[0] for x in rates]); sell_fee = np.array([x[1] for x in rates])
    role_idx = {r: np.array([panel.roles[s] == r for s in syms]) for r in contributions}
    for t in range(1, n):
        prev = panel.c.iloc[t-1].to_numpy(float)
        ref = panel.o.iloc[t].to_numpy(float) if panel.market == "KR" else panel.c.iloc[t].to_numpy(float)
        valid = np.isfinite(prev) & np.isfinite(ref) & (prev > 0) & (ref > 0)
        before_values = values.copy()
        values[valid] *= ref[valid] / prev[valid]
        pnl = values - before_values
        prev_equity = max(cash + before_values.sum(), 1e-12)
        for role, mask in role_idx.items(): contributions[role][t] += pnl[mask].sum() / prev_equity
        equity = cash + values.sum()
        desired = target.iloc[t-1].to_numpy(float).copy()
        desired = np.clip(desired, 0, 1)
        if desired.sum() > 1: desired /= desired.sum()
        if breaker:
            for j, sym in enumerate(syms):
                if panel.roles[sym] in ("index", "sector", "stock", "inverse"): desired[j] *= .5
        not_tradable = ~panel.tradable.iloc[t].to_numpy(bool)
        desired[not_tradable] = np.minimum(desired[not_tradable], values[not_tradable] / max(equity, 1e-12))
        delta = desired * equity - values
        # 목표비중·차단기 상태가 그대로면 드리프트 보정 매매를 하지 않는다(일일 미세 리밸런스 비용 방지).
        unchanged = t > 1 and breaker == traded_breaker and np.array_equal(tw[t-1], tw[t-2])
        if unchanged: delta[:] = 0.
        else: traded_breaker = breaker
        sells, buys = np.maximum(-delta, 0), np.maximum(delta, 0)
        fee = sells @ sell_fee + buys @ buy_fee
        cash -= delta.sum() + fee; values += delta
        turnover[t] = np.abs(delta).sum(); costs[t] = fee
        contributions["index"][t] -= fee * .0
        if panel.market == "KR":
            op = panel.o.iloc[t].to_numpy(float); cl = panel.c.iloc[t].to_numpy(float)
            valid_day = np.isfinite(op) & np.isfinite(cl) & (op > 0) & (cl > 0)
            pre_close = values.copy(); values[valid_day] *= cl[valid_day] / op[valid_day]
            pnl = values - pre_close
            for role, mask in role_idx.items(): contributions[role][t] += pnl[mask].sum() / prev_equity
        eq[t] = cash + values.sum()
        daily_weights[t] = values / max(eq[t], 1e-12)
        peak = max(peak, eq[t])
        if drawdown_breaker and eq[t] <= peak * .88: breaker = True
        elif breaker and (eq[t] >= peak * .94 or (regimes is not None and regimes.iloc[t] == "BULL")): breaker = False
    # 비용은 자산 역할별 손익과 별도 반환하며 contribution에서 현금비용으로 분리한다.
    return {"equity": pd.Series(eq, index=d), "regime": pd.Series(regime_daily, index=d),
            "weights": pd.DataFrame(daily_weights, index=d, columns=syms),
            "turnover": pd.Series(turnover, index=d), "costs": pd.Series(costs, index=d),
            "sleeve_contribution": {k: pd.Series(v, index=d) for k, v in contributions.items()}}
