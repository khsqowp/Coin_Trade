"""국장/미장 롱온리 top-N 모멘텀 로테이션 백테스트 — 매수&보유(등가중)를 이기는지 확인.

코인 momentum_rotation 은 달러중립 롱숏이지만 국내/미국 주식은 개인 공매도가 사실상 막혀
있으므로 롱온리로만 돌린다. 매 리밸런스에 최근 L일 수익률 상위 N종목 등가중 보유,
(옵션) 등가중 지수가 자기 200일선 아래면 전액 현금.

벤치마크: 유니버스 전체 등가중 매수&보유(EW-B&H). 알파 = 전략 CAGR - EW-B&H CAGR.

데이터는 app/kis_ohlcv_cache.py 로 종목당 1회만 받아 CSV 캐시(볼륨) 재사용.

실행:
  docker run --rm --entrypoint python --env-file ../.env \
    -v "$PWD:/app/app" -v "$PWD/../.kis-cache:/app/cache" \
    -e ROTATION_MARKET=KR ochestration-trading-momentum-rotation -m app.kr_us_rotation_backtest
"""
from __future__ import annotations

import itertools
import os

import numpy as np
import pandas as pd

from app.kis_auth import issue_token
from app.kis_ohlcv_cache import warm_cache

MARKET = os.environ.get("ROTATION_MARKET", "KR").upper()
SINCE = os.environ.get("ROTATION_SINCE", "2018-01-01")
UNTIL = os.environ.get("ROTATION_UNTIL") or None
COST_PER_SIDE_PCT = float(os.environ.get("ROTATION_COST_PCT", "0.10"))

LOOKBACKS = [20, 60, 120]
REBALS = [5, 10, 20]
TOP_NS = [3, 5, 8, 10]
REGIMES = ["none", "ew_sma200"]


def _universe() -> list[tuple]:
    if MARKET == "KR":
        from app.ema_cross_watchlist import STOCK_UNIVERSE
        return [("KR", code) for code, _ in STOCK_UNIVERSE]
    from app.us_swing_search import STOCK_UNIVERSE
    return [("US", sym, excd) for sym, excd, _ in STOCK_UNIVERSE]


def _load_closes() -> pd.DataFrame:
    token = issue_token()
    frames = warm_cache(_universe(), token, SINCE, UNTIL)
    closes = pd.DataFrame({s: f["Close"] for s, f in frames.items()}).sort_index()
    # 거래일 기준 정렬 — 최소 60% 종목이 값 있는 날만
    closes = closes[closes.notna().mean(axis=1) >= 0.6]
    return closes


def _metrics(equity_curve: pd.Series, daily: pd.Series) -> dict:
    years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
    final = equity_curve.iloc[-1]
    cagr = (final ** (1 / years) - 1) * 100 if final > 0 and years > 0 else -100.0
    peak = equity_curve.cummax()
    mdd = ((peak - equity_curve) / peak).max() * 100
    sharpe = float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0.0
    calmar = cagr / mdd if mdd > 0 else float("inf")
    yearly = {}
    for yr, grp in equity_curve.groupby(equity_curve.index.year):
        yearly[int(yr)] = round((grp.iloc[-1] / grp.iloc[0] - 1) * 100, 1)
    return {"cagr": cagr, "mdd": mdd, "sharpe": sharpe, "calmar": calmar,
            "final": final, "yearly": yearly}


def _ew_buy_hold(closes: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    rets = closes.pct_change().fillna(0.0)
    # 시작 시점 존재 종목 등가중, 이후 드리프트 허용(진짜 매수&보유)
    valid0 = closes.iloc[0].notna()
    w0 = valid0 / valid0.sum()
    shares = w0  # 가격=정규화 아님; 단순히 등가중 인덱스로 근사
    port_daily = (rets * w0).sum(axis=1)  # 등가중 리밸런스 근사(일간). B&H 하한으로 충분
    eq = (1 + port_daily).cumprod()
    return eq, port_daily


def _sim(closes: pd.DataFrame, lookback: int, rebal: int, top_n: int, regime: str) -> dict:
    rets = closes.pct_change()
    mom = closes.pct_change(lookback)
    ew_index = (1 + rets.mean(axis=1).fillna(0.0)).cumprod()
    ew_sma = ew_index.rolling(200).mean()

    dates = closes.index
    start = max(lookback + 1, 200)
    w = pd.Series(0.0, index=closes.columns)
    last_w = w.copy()
    daily = []
    idx = []
    turnovers = []

    for i in range(start, len(dates)):
        d = dates[i]
        g = (w * rets.loc[d].fillna(0.0)).sum()
        daily.append(g)
        idx.append(d)

        if (i - start) % rebal == 0:
            cash = regime == "ew_sma200" and ew_index.iloc[i] < ew_sma.iloc[i]
            m = mom.loc[d].dropna()
            m = m[closes.loc[d].notna()]
            nw = pd.Series(0.0, index=closes.columns)
            if not cash and len(m) >= top_n:
                winners = m.sort_values(ascending=False).index[:top_n]
                nw[winners] = 1.0 / top_n
            turn = (nw - last_w).abs().sum()
            turnovers.append(turn)
            # 비용은 다음 날 반영되도록 당일 수익에서 차감
            daily[-1] -= turn * COST_PER_SIDE_PCT / 100
            w, last_w = nw, nw.copy()

    dseries = pd.Series(daily, index=idx)
    eq = (1 + dseries).cumprod()
    r = _metrics(eq, dseries)
    r["ann_turn"] = float(np.sum(turnovers)) / ((idx[-1] - idx[0]).days / 365.25)
    return r


def run() -> None:
    print(f"[{MARKET}] 캐시 워밍/로드 (since {SINCE})...")
    closes = _load_closes()
    print(f"유효 {closes.shape[1]}종목, {closes.index[0].date()} ~ {closes.index[-1].date()} "
          f"({closes.shape[0]}거래일)\n")

    bh_eq, bh_daily = _ew_buy_hold(closes)
    bh = _metrics(bh_eq, bh_daily)
    print(f"[벤치마크] 등가중 매수&보유: CAGR {bh['cagr']:+.1f}%, MDD {bh['mdd']:.1f}%, "
          f"Sharpe {bh['sharpe']:.2f}, Calmar {bh['calmar']:.2f}")
    print(f"  연도별 {bh['yearly']}\n")

    rows = []
    for lb, rb, tn, rg in itertools.product(LOOKBACKS, REBALS, TOP_NS, REGIMES):
        r = _sim(closes, lb, rb, tn, rg)
        r.update(lb=lb, rb=rb, tn=tn, rg=rg, alpha=r["cagr"] - bh["cagr"])
        rows.append(r)

    rows.sort(key=lambda x: -x["calmar"])
    print(f"{'룩백':>5} {'리밸':>5} {'TopN':>5} {'레짐':>10} | {'CAGR':>8} {'MDD':>7} "
          f"{'Sharpe':>7} {'Calmar':>7} {'알파':>8} {'연회전':>7}")
    print("-" * 90)
    for r in rows[:20]:
        print(f"{r['lb']:>5} {r['rb']:>5} {r['tn']:>5} {r['rg']:>10} | {r['cagr']:>+7.1f}% "
              f"{r['mdd']:>6.1f}% {r['sharpe']:>7.2f} {r['calmar']:>7.2f} {r['alpha']:>+7.1f}% "
              f"{r['ann_turn']:>6.1f}x")

    beat = [r for r in rows if r["alpha"] > 0]
    print(f"\nEW-B&H 이긴 조합: {len(beat)}/{len(rows)}")
    print("\n[상위 5 조합 연도별]")
    for r in rows[:5]:
        print(f"  룩백{r['lb']}/리밸{r['rb']}/top{r['tn']}/{r['rg']}: {r['yearly']}")
    best = rows[0]
    print(f"\n최고 Calmar: 룩백{best['lb']}/리밸{best['rb']}/top{best['tn']}/{best['rg']} "
          f"CAGR {best['cagr']:+.1f}% vs B&H {bh['cagr']:+.1f}% (알파 {best['alpha']:+.1f}%), "
          f"MDD {best['mdd']:.1f}% vs {bh['mdd']:.1f}%")
    print(f"\n비용가정: 편도 {COST_PER_SIDE_PCT}% (수수료+세금+슬리피지). "
          f"배당 미반영, 생존편향 있음(현재 유니버스 고정).")


if __name__ == "__main__":
    run()
