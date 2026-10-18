"""1등 후보(SK하이닉스 x ema_cross) 재검증 — 단순 재실행이 아니라 부트스트랩 기대수익
유의성 게이트(app/validation.py)로 "거래 26건짜리 수익률이 우연이 아닌지" 통계적으로 확인.
"""
from __future__ import annotations

from backtesting import Backtest

from app.kis_auth import issue_token
from app.kis_data import fetch_ohlcv_kis
from app.more_indicators import add_ema_cross_indicators
from app.param_grids import PARAM_GRIDS
from app.strategies import EmaCrossStrategy
from app.validation import bootstrap_expectancy_gate

SYMBOL = "000660"
NAME = "SK하이닉스"


def _score(stats) -> float:
    trades = stats.get("# Trades", 0)
    if trades < 3:
        return -999.0
    pf = stats.get("Profit Factor", float("nan"))
    return -999.0 if pf != pf else pf


def run() -> None:
    print("토큰 발급...")
    token = issue_token()
    print(f"{NAME}({SYMBOL}) 일봉 수집...")
    frame = fetch_ohlcv_kis(SYMBOL, token, "2019-01-01", None)
    enriched = add_ema_cross_indicators(frame).dropna()
    print(f"  {len(enriched)}봉 사용")

    for label, run_fn in [
        ("기본값", lambda bt: bt.run()),
        ("그리드 최적화", lambda bt: bt.optimize(**PARAM_GRIDS["ema_cross"], maximize=_score, method="grid", return_heatmap=False)),
    ]:
        bt = Backtest(enriched, EmaCrossStrategy, cash=10_000_000, commission=0.002, exclusive_orders=True)
        stats = run_fn(bt)
        trades_df = stats.get("_trades")
        n_trades = len(trades_df) if trades_df is not None else 0
        print(f"\n--- {label} ---")
        print(f"수익률 {stats.get('Return [%]'):.2f}%  PF {stats.get('Profit Factor'):.2f}  "
              f"MDD {abs(stats.get('Max. Drawdown [%]')):.2f}%  거래 {n_trades}건")
        if hasattr(stats, "_strategy"):
            print(f"파라미터: STOP_PCT={getattr(stats._strategy, 'STOP_PCT', None)}")

        if n_trades == 0:
            print("거래 없음 — 부트스트랩 불가")
            continue
        returns = trades_df["ReturnPct"].to_numpy(dtype=float)
        gate = bootstrap_expectancy_gate(returns, min_trades=20)
        print(f"부트스트랩(95% 신뢰구간, {gate['trades']}건 표본): {gate['reason']} "
              f"=> {'통과 (우연 아님)' if gate['passed'] else '미통과 (우연일 가능성 배제 못함)'}")


if __name__ == "__main__":
    run()
