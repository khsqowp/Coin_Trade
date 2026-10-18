"""미국주식 스윙전략 시나리오 스윕 — app/stock_swing_search.py와 동일 구조,
데이터 소스만 해외주식 API(app/kis_overseas_data.py)로 교체, 전략 30개 그대로 재사용.
국내와 상관관계/레짐이 다를 수 있어 최적 전략이 다를 수 있다는 가정하에 처음부터 다시 스윕한다.
"""
from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
from backtesting import Backtest

from app.broad_strategies import (
    AdxDiCrossStrategy, AroonCrossStrategy, AwesomeOscillatorStrategy, BollingerBreakoutStrategy,
    CciMeanReversionStrategy, ChaikinMoneyFlowStrategy, GoldenCrossStrategy, IchimokuCrossStrategy,
    KeltnerBreakoutStrategy, MacdZeroCrossStrategy, ObvTrendStrategy, ParabolicSarStrategy,
    RocMomentumStrategy, StochRsiStrategy, StochasticCrossStrategy, TemaTrendStrategy,
    TrixMomentumStrategy, VolumeSpikeBreakoutStrategy, WilliamsRStrategy,
    add_adx_di_indicators, add_aroon_indicators, add_awesome_osc_indicators, add_bb_breakout_indicators,
    add_cci_indicators, add_cmf_indicators, add_golden_cross_indicators, add_ichimoku_cross_indicators,
    add_keltner_indicators, add_macd_zero_indicators, add_obv_indicators, add_psar_indicators,
    add_roc_indicators, add_stochastic_indicators, add_stochrsi_indicators, add_tema_cross_indicators,
    add_trix_indicators, add_volume_spike_breakout_indicators, add_williams_r_indicators,
)
from app.extra_indicators import add_range_reversion_indicators, add_supertrend_indicators
from app.extra_strategies import RangeReversionStrategy, SupertrendStrategy
from app.kis_auth import issue_token
from app.kis_overseas_data import fetch_ohlcv_kis_overseas
from app.momentum_strategy import GapMomentumStrategy
from app.more_indicators import (
    add_bb_macd_indicators,
    add_dual_thrust_indicators,
    add_ema_cross_indicators,
    add_rsi2_indicators,
)
from app.param_grids import PARAM_GRIDS
from app.strategies import BollingerMacdStrategy, DualThrustStrategy, EmaCrossStrategy, Rsi2MeanReversionStrategy
from app.swing_indicators import add_donchian_indicators, add_donchian_indicators_fast, add_ma_pullback_indicators
from app.swing_strategies import DonchianTrendStrategy, MaPullbackFastSwingStrategy, MaPullbackSwingStrategy

DAILY_STRATEGIES = [
    ("donchian_trend", DonchianTrendStrategy, add_donchian_indicators),
    ("ma_pullback_swing", MaPullbackSwingStrategy, add_ma_pullback_indicators),
    ("donchian_trend_fast", DonchianTrendStrategy, add_donchian_indicators_fast),
    ("ma_pullback_fast", MaPullbackFastSwingStrategy, add_ma_pullback_indicators),
    ("gap_momentum", GapMomentumStrategy, lambda frame: frame),
    ("ema_cross", EmaCrossStrategy, add_ema_cross_indicators),
    ("rsi2_meanrev", Rsi2MeanReversionStrategy, add_rsi2_indicators),
    ("bb_macd_adx", BollingerMacdStrategy, add_bb_macd_indicators),
    ("dual_thrust", DualThrustStrategy, add_dual_thrust_indicators),
    ("supertrend", SupertrendStrategy, add_supertrend_indicators),
    ("range_reversion", RangeReversionStrategy, add_range_reversion_indicators),
    ("golden_cross", GoldenCrossStrategy, add_golden_cross_indicators),
    ("macd_zero_cross", MacdZeroCrossStrategy, add_macd_zero_indicators),
    ("stochastic_cross", StochasticCrossStrategy, add_stochastic_indicators),
    ("williams_r", WilliamsRStrategy, add_williams_r_indicators),
    ("adx_di_cross", AdxDiCrossStrategy, add_adx_di_indicators),
    ("cci_meanrev", CciMeanReversionStrategy, add_cci_indicators),
    ("parabolic_sar", ParabolicSarStrategy, add_psar_indicators),
    ("keltner_breakout", KeltnerBreakoutStrategy, add_keltner_indicators),
    ("tema_cross", TemaTrendStrategy, add_tema_cross_indicators),
    ("awesome_osc", AwesomeOscillatorStrategy, add_awesome_osc_indicators),
    ("roc_momentum", RocMomentumStrategy, add_roc_indicators),
    ("obv_trend", ObvTrendStrategy, add_obv_indicators),
    ("bb_breakout", BollingerBreakoutStrategy, add_bb_breakout_indicators),
    ("volume_spike_breakout", VolumeSpikeBreakoutStrategy, add_volume_spike_breakout_indicators),
    ("ichimoku_cross", IchimokuCrossStrategy, add_ichimoku_cross_indicators),
    ("stochrsi_cross", StochRsiStrategy, add_stochrsi_indicators),
    ("trix_momentum", TrixMomentumStrategy, add_trix_indicators),
    ("aroon_cross", AroonCrossStrategy, add_aroon_indicators),
    ("cmf_trend", ChaikinMoneyFlowStrategy, add_cmf_indicators),
]

# 섹터 분산 미국 대형주 26종목 (NAS=나스닥, NYS=뉴욕증권거래소)
STOCK_UNIVERSE = [
    ("AAPL", "NAS", "Apple"), ("MSFT", "NAS", "Microsoft"), ("GOOGL", "NAS", "Alphabet"),
    ("AMZN", "NAS", "Amazon"), ("NVDA", "NAS", "Nvidia"), ("META", "NAS", "Meta"),
    ("TSLA", "NAS", "Tesla"), ("ADBE", "NAS", "Adobe"), ("NFLX", "NAS", "Netflix"),
    ("INTC", "NAS", "Intel"), ("AMD", "NAS", "AMD"), ("QCOM", "NAS", "Qualcomm"),
    ("COST", "NAS", "Costco"), ("PEP", "NAS", "PepsiCo"), ("CSCO", "NAS", "Cisco"),
    ("JPM", "NYS", "JPMorgan"), ("V", "NYS", "Visa"), ("JNJ", "NYS", "J&J"),
    ("WMT", "NYS", "Walmart"), ("PG", "NYS", "P&G"), ("UNH", "NYS", "UnitedHealth"),
    ("HD", "NYS", "Home Depot"), ("MA", "NYS", "Mastercard"), ("XOM", "NYS", "ExxonMobil"),
    ("KO", "NYS", "Coca-Cola"), ("DIS", "NYS", "Disney"),
    # 소형주 프로브(app/us_smallcap_probe.py)에서 ema_cross 게이트 통과 + 실제 매수&보유 우상향 확인된 종목
    ("GRC", "NYS", "Gorman-Rupp"), ("AAON", "NAS", "AAON"),
    # 2차 확장 프로브(app/us_candidate_probe2.py, app/us_lowprice_probe3.py) 통과분 —
    # 게이트 통과했어도 매수&보유가 실제로 하락한 종목(IDEXX Labs/American Airlines 등)은 제외
    ("T", "NYS", "AT&T"), ("FIX", "NYS", "Comfort Systems"), ("SAIA", "NAS", "Saia"),
    ("BAC", "NYS", "Bank of America"), ("CASY", "NAS", "Casey's General"), ("KMI", "NYS", "Kinder Morgan"),
    ("GOLD", "NYS", "Barrick"), ("KEY", "NYS", "KeyCorp"), ("RF", "NYS", "Regions Financial"),
    ("HBAN", "NAS", "Huntington Bancshares"),
    # 3차 확장(app/us_top500_probe.py, S&P500 스크리닝) — PF 5 이상 최상위권만 채택
    ("CIEN", "NYS", "Ciena"), ("CVNA", "NYS", "Carvana"), ("FICO", "NYS", "Fair Isaac"),
    ("RCL", "NYS", "Royal Caribbean Group"), ("BKNG", "NAS", "Booking Holdings"), ("HOOD", "NAS", "Robinhood Markets"),
    ("GE", "NYS", "GE Aerospace"), ("LRCX", "NAS", "Lam Research"), ("NUE", "NYS", "Nucor"),
    ("NTRS", "NAS", "Northern Trust"), ("GLW", "NYS", "Corning Inc."), ("DELL", "NYS", "Dell Technologies"),
    ("IBM", "NYS", "IBM"), ("APO", "NYS", "Apollo Global Management"), ("AMAT", "NAS", "Applied Materials"),
    ("IBKR", "NAS", "Interactive Brokers"), ("KKR", "NYS", "KKR & Co."),
]

MIN_USABLE_BARS = 250
MIN_PROFIT_FACTOR = 1.25
MAX_DRAWDOWN_PCT = 15.0
MIN_TRADES = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="미국주식 스윙전략 시나리오 스윕 (한투 모의투자 해외주식 데이터)")
    parser.add_argument("--since", default="2021-01-01")
    parser.add_argument("--until", default=None)
    parser.add_argument("--cash", type=float, default=10_000.0, help="USD 기준")
    parser.add_argument("--commission", type=float, default=0.001, help="미국주식은 거래세 없음, 수수료만 근사")
    parser.add_argument("--max-tries", type=int, default=12)
    return parser.parse_args()


def _score(stats) -> float:
    trades = stats.get("# Trades", 0)
    if trades < 3:
        return -999.0
    pf = stats.get("Profit Factor", float("nan"))
    if pf != pf:
        return -999.0
    return pf * min(trades / MIN_TRADES, 1.0)


def _build_row(symbol: str, name: str, strategy: str, params_source: str, stats) -> dict:
    pf = stats.get("Profit Factor", float("nan"))
    mdd = abs(stats.get("Max. Drawdown [%]", float("inf")))
    trades = stats.get("# Trades", 0)
    hard_pass = pf == pf and pf >= MIN_PROFIT_FACTOR and mdd <= MAX_DRAWDOWN_PCT and trades >= MIN_TRADES
    return {
        "symbol": symbol, "name": name, "strategy": strategy, "params_source": params_source,
        "return_pct": stats.get("Return [%]", float("nan")),
        "buy_hold_pct": stats.get("Buy & Hold Return [%]", float("nan")),
        "profit_factor": pf, "max_drawdown_pct": mdd, "trades": trades,
        "sharpe": stats.get("Sharpe Ratio", float("nan")),
        "hard_gate_pass": hard_pass,
    }


def _process_symbol(symbol: str, name: str, frame: pd.DataFrame, cash: float, commission: float, max_tries: int) -> list[dict]:
    rows: list[dict] = []
    if frame.empty or len(frame) < MIN_USABLE_BARS:
        print(f"  [{name}/{symbol}] 데이터 부족({len(frame)}봉), 건너뜀")
        return rows

    for strategy_name, strategy_cls, indicator_fn in DAILY_STRATEGIES:
        enriched = indicator_fn(frame).dropna()
        if len(enriched) < MIN_USABLE_BARS:
            print(f"  [{strategy_name}/{name}/{symbol}] 워밍업 이후 데이터 부족, 건너뜀")
            continue

        try:
            default_stats = Backtest(enriched, strategy_cls, cash=cash, commission=commission, exclusive_orders=True).run()
            row = _build_row(symbol, name, strategy_name, "default", default_stats)
            rows.append(row)
            print(f"  [{strategy_name}/{name}/default] 수익률 {row['return_pct']:.1f}% PF {row['profit_factor']:.2f} "
                  f"거래 {row['trades']}건 게이트={'P' if row['hard_gate_pass'] else 'F'}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [오류] {strategy_name}/{name}/default: {exc}")

        grid = PARAM_GRIDS.get(strategy_name, {})
        if grid:
            try:
                bt = Backtest(enriched, strategy_cls, cash=cash, commission=commission, exclusive_orders=True)
                optimized_stats = bt.optimize(**grid, maximize=_score, method="grid", max_tries=max_tries, random_state=42, return_heatmap=False)
                row = _build_row(symbol, name, strategy_name, "optimized", optimized_stats)
                rows.append(row)
                print(f"  [{strategy_name}/{name}/optimized] 수익률 {row['return_pct']:.1f}% PF {row['profit_factor']:.2f} "
                      f"거래 {row['trades']}건 게이트={'P' if row['hard_gate_pass'] else 'F'}")
            except Exception as exc:  # noqa: BLE001
                print(f"  [오류] {strategy_name}/{name}/optimized: {exc}")

    return rows


def run(args: argparse.Namespace) -> None:
    print("[1/3] 한투 모의투자 토큰 발급 중...")
    token = issue_token()

    print(f"[2/3] {len(STOCK_UNIVERSE)}개 종목 일봉 데이터 순차 수집 중 ({args.since} ~ {args.until or '현재'})...")
    frames: dict[str, pd.DataFrame] = {}
    for symbol, excd, name in STOCK_UNIVERSE:
        try:
            frame = fetch_ohlcv_kis_overseas(symbol, excd, token, args.since, args.until)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}({symbol}): 수집 실패 ({exc}), 건너뜀")
            continue
        frames[symbol] = frame
        print(f"  {name}({symbol}): {len(frame)}봉")

    available = [(symbol, name) for symbol, _, name in STOCK_UNIVERSE if symbol in frames]
    print(f"[3/3] 전략 {len(DAILY_STRATEGIES)}개 x 종목 {len(available)}개 백테스트 (프로세스 병렬)...")
    started = time.monotonic()
    rows: list[dict] = []
    max_workers = min(len(available), os.cpu_count() or 4, 4)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_symbol, symbol, name, frames[symbol], args.cash, args.commission, args.max_tries): (symbol, name)
            for symbol, name in available
        }
        for future in as_completed(futures):
            symbol, name = futures[future]
            try:
                rows.extend(future.result())
            except Exception as exc:  # noqa: BLE001
                print(f"[오류] {name}({symbol}) 처리 실패: {exc}")

    elapsed = time.monotonic() - started
    print(f"\n총 소요 {elapsed:.0f}초, 시나리오 {len(rows)}건")
    _print_ranked(rows)


def _print_ranked(rows: list[dict]) -> None:
    print("\n" + "=" * 90)
    print(f"{'종목':<10}{'전략':<20}{'파라미터':<10}{'수익률':>9}{'매수보유':>9}{'PF':>7}{'MDD':>7}{'거래':>6}{'게이트':>6}")
    for row in sorted(rows, key=lambda r: (r["profit_factor"] if r["profit_factor"] == r["profit_factor"] else -999), reverse=True):
        print(f"{row['name']:<10}{row['strategy']:<20}{row['params_source']:<10}"
              f"{row['return_pct']:>8.1f}%{row['buy_hold_pct']:>8.1f}%{row['profit_factor']:>7.2f}"
              f"{row['max_drawdown_pct']:>6.1f}%{row['trades']:>6}{'  P' if row['hard_gate_pass'] else '  F':>6}")

    passed = [r for r in rows if r["hard_gate_pass"]]
    print(f"\n게이트 통과 (PF>={MIN_PROFIT_FACTOR}, MDD<={MAX_DRAWDOWN_PCT}%, 거래>={MIN_TRADES}건): {len(passed)}/{len(rows)}건")


if __name__ == "__main__":
    run(parse_args())
