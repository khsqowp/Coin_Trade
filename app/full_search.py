"""Comprehensive strategy search combining three improvement axes discussed with the
user, tested independently AND in every combination rather than picking just one:

  1. 파라미터 최적화 — grid search over each strategy's tunable thresholds (app/param_grids.py)
  2. 통계적 유의성 재검토 — bootstrap-based expectancy gate (app/validation.py) as an
     alternative to the flat "거래 >= 300건" rule, for strategies that trade too rarely
     to ever hit a large fixed count even with a real edge
  3. 더 짧은 주기 — also test each strategy on a shorter timeframe (app/registry.py의
     TIMEFRAME_VARIANTS) to see if trade frequency / sample size improves

Rather than literally re-running seven separate pipelines for every combination of
{1,2,3}, this runs ONE superset sweep — every strategy x every timeframe variant x
(default params AND grid-optimized params) x every symbol — and then derives all
seven combination views by filtering/aggregating that single result set. Nothing is
wastefully repeated; the same underlying backtests support every view.

Cost is explicitly not a concern per the user ("어차피 지금은 돈드는것도 아니니깐") since this
is backtesting only, so the sweep favors completeness over runtime.
"""
from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from backtesting import Backtest

from app.data import fetch_ohlcv
from app.markets import top_liquid_altcoins
from app.param_grids import PARAM_GRIDS
from app.registry import STRATEGIES, TIMEFRAME_VARIANTS
from app.validation import bootstrap_expectancy_gate

MIN_PROFIT_FACTOR = 1.25
MAX_DRAWDOWN_PCT = 10.0
MIN_TRADES = 300
BOOTSTRAP_MIN_TRADES = 20
MIN_USABLE_BARS = 250


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="전략 x 심볼 x 파라미터 x 주기 종합 탐색 (접근법 1/2/3 전 조합)")
    parser.add_argument("--symbols", default=None, help="쉼표 구분 심볼 목록. 생략하면 BTC/ETH + 거래량 상위 알트코인 자동 선택")
    parser.add_argument("--altcoin-count", type=int, default=5)
    parser.add_argument("--min-quote-volume", type=float, default=5_000_000)
    parser.add_argument("--since", default="2022-01-01T00:00:00Z")
    parser.add_argument("--until", default=None)
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--max-tries", type=int, default=12, help="전략별 파라미터 그리드에서 무작위로 시도할 조합 수 (5~20 권장)")
    parser.add_argument("--strategies", default=None, help="쉼표 구분 전략 이름 목록 (app/registry.py의 표시용 이름). 생략하면 전체")
    parser.add_argument("--min-profit-factor", type=float, default=MIN_PROFIT_FACTOR, help="하드게이트 최소 Profit Factor")
    parser.add_argument("--max-drawdown-pct", type=float, default=MAX_DRAWDOWN_PCT, help="하드게이트 최대 낙폭(%)")
    parser.add_argument("--min-trades", type=int, default=MIN_TRADES, help="하드게이트 최소 거래수")
    parser.add_argument("--bootstrap-min-trades", type=int, default=BOOTSTRAP_MIN_TRADES, help="부트스트랩 게이트 시도에 필요한 최소 거래수")
    return parser.parse_args()


def resolve_strategies(args: argparse.Namespace):
    if not args.strategies:
        return STRATEGIES
    wanted = {name.strip() for name in args.strategies.split(",")}
    return [entry for entry in STRATEGIES if entry[0] in wanted]


def resolve_symbols(args: argparse.Namespace) -> list[str]:
    if args.symbols:
        return [s.strip() for s in args.symbols.split(",")]
    core = ["BTC/USDT", "ETH/USDT"]
    print(f"거래량 상위 알트코인 {args.altcoin_count}개 조회 중...")
    altcoins = top_liquid_altcoins(limit=args.altcoin_count, exclude={"BTC", "ETH"}, min_quote_volume=args.min_quote_volume)
    print(f"  선택됨: {altcoins}")
    return core + altcoins


def _score(stats) -> float:
    """grid search maximize 함수 — 거래수가 너무 적으면 페널티, 그 외엔 PF 우선."""
    trades = stats.get("# Trades", 0)
    if trades < 5:
        return -999.0
    pf = stats.get("Profit Factor", float("nan"))
    if pf != pf:
        return -999.0
    return pf * min(trades / MIN_TRADES, 1.0)


def _gate_hard(stats) -> bool:
    pf = stats.get("Profit Factor", float("nan"))
    mdd = abs(stats.get("Max. Drawdown [%]", float("inf")))
    trades = stats.get("# Trades", 0)
    return pf == pf and pf >= MIN_PROFIT_FACTOR and mdd <= MAX_DRAWDOWN_PCT and trades >= MIN_TRADES


def _gate_bootstrap(stats) -> tuple[bool, dict]:
    trades_df = stats.get("_trades")
    if trades_df is None or len(trades_df) == 0:
        return False, {"reason": "거래 없음", "trades": 0, "lower_bound": float("nan")}
    returns = trades_df["ReturnPct"].to_numpy(dtype=float)
    mdd = abs(stats.get("Max. Drawdown [%]", float("inf")))
    result = bootstrap_expectancy_gate(returns, min_trades=BOOTSTRAP_MIN_TRADES)
    passed = result["passed"] and mdd <= MAX_DRAWDOWN_PCT
    return passed, result


def _build_row(name, symbol, timeframe, is_default_timeframe, params_source, stats) -> dict:
    hard_pass = _gate_hard(stats)
    bootstrap_pass, bootstrap_info = _gate_bootstrap(stats)
    return {
        "strategy": name, "symbol": symbol, "timeframe": timeframe,
        "is_default_timeframe": is_default_timeframe, "params_source": params_source,
        "return_pct": stats.get("Return [%]", float("nan")),
        "buy_hold_pct": stats.get("Buy & Hold Return [%]", float("nan")),
        "profit_factor": stats.get("Profit Factor", float("nan")),
        "max_drawdown_pct": abs(stats.get("Max. Drawdown [%]", float("inf"))),
        "trades": stats.get("# Trades", 0),
        "hard_gate_pass": hard_pass,
        "bootstrap_gate_pass": bootstrap_pass,
        "bootstrap_lower_bound": bootstrap_info["lower_bound"],
        "sharpe": stats.get("Sharpe Ratio", float("nan")),
        "sortino": stats.get("Sortino Ratio", float("nan")),
        "calmar": stats.get("Calmar Ratio", float("nan")),
    }


def _process_symbol(symbol: str, args: argparse.Namespace) -> list[dict]:
    """한 심볼에 대해 (선택된) 전략 x 모든 주기 변형 x (기본/최적화 파라미터)를 실행.
    심볼별로 독립적인 데이터 캐시를 쓰므로 프로세스 간 경합 없이 병렬 실행 가능."""
    data_cache: dict[str, object] = {}
    rows: list[dict] = []

    for name, strategy_cls, default_timeframe, indicator_fn in resolve_strategies(args):
        timeframes = [default_timeframe] + TIMEFRAME_VARIANTS.get(name, [])
        grid = PARAM_GRIDS.get(name, {})

        for timeframe in timeframes:
            is_default_timeframe = timeframe == default_timeframe
            if timeframe not in data_cache:
                print(f"[데이터] {symbol} {timeframe} 캔들 수집 중...")
                data_cache[timeframe] = fetch_ohlcv(symbol, timeframe, args.since, args.until)
            frame = data_cache[timeframe]
            if frame.empty or len(frame) < MIN_USABLE_BARS:
                print(f"  {name}/{symbol}/{timeframe}: 데이터 부족, 건너뜀")
                continue

            enriched = indicator_fn(frame).dropna()
            if len(enriched) < MIN_USABLE_BARS:
                print(f"  {name}/{symbol}/{timeframe}: 워밍업 이후 데이터 부족, 건너뜀")
                continue

            try:
                default_stats = Backtest(enriched, strategy_cls, cash=args.cash,
                                          commission=args.commission, exclusive_orders=True).run()
            except Exception as exc:  # noqa: BLE001 — 한 조합 실패해도 나머지는 계속
                print(f"  [오류] {name}/{symbol}/{timeframe} (기본값): {exc}")
                default_stats = None
            if default_stats is not None:
                row = _build_row(name, symbol, timeframe, is_default_timeframe, "default", default_stats)
                rows.append(row)
                print(f"  [{name}/{symbol}/{timeframe}/default] PF {row['profit_factor']:.2f} "
                      f"거래 {row['trades']}건 hard={'P' if row['hard_gate_pass'] else 'F'} "
                      f"boot={'P' if row['bootstrap_gate_pass'] else 'F'}")

            if grid:
                try:
                    bt = Backtest(enriched, strategy_cls, cash=args.cash,
                                  commission=args.commission, exclusive_orders=True)
                    optimized_stats = bt.optimize(**grid, maximize=_score, method="grid",
                                                   max_tries=args.max_tries, random_state=42,
                                                   return_heatmap=False)
                except Exception as exc:  # noqa: BLE001
                    print(f"  [오류] {name}/{symbol}/{timeframe} (최적화): {exc}")
                    optimized_stats = None
                if optimized_stats is not None:
                    row = _build_row(name, symbol, timeframe, is_default_timeframe, "optimized", optimized_stats)
                    rows.append(row)
                    print(f"  [{name}/{symbol}/{timeframe}/optimized] PF {row['profit_factor']:.2f} "
                          f"거래 {row['trades']}건 hard={'P' if row['hard_gate_pass'] else 'F'} "
                          f"boot={'P' if row['bootstrap_gate_pass'] else 'F'}")

    return rows


def run(args: argparse.Namespace) -> None:
    global MIN_PROFIT_FACTOR, MAX_DRAWDOWN_PCT, MIN_TRADES, BOOTSTRAP_MIN_TRADES
    MIN_PROFIT_FACTOR = args.min_profit_factor
    MAX_DRAWDOWN_PCT = args.max_drawdown_pct
    MIN_TRADES = args.min_trades
    BOOTSTRAP_MIN_TRADES = args.bootstrap_min_trades
    print(f"게이트 기준: PF>={MIN_PROFIT_FACTOR}, MDD<={MAX_DRAWDOWN_PCT}%, "
          f"하드게이트 거래수>={MIN_TRADES}건, 부트스트랩 최소 거래수>={BOOTSTRAP_MIN_TRADES}건")

    symbols = resolve_symbols(args)
    rows: list[dict] = []
    started = time.monotonic()

    # 심볼 단위로 "프로세스" 병렬화 (스레드 아님). Backtest.optimize()가 내부적으로
    # fork 기반 ProcessPoolExecutor를 새로 띄우는데, 그 fork가 멀티스레드 프로세스 안에서
    # 일어나면 다른 스레드가 들고 있는 락(예: malloc, 로깅)을 자식이 그대로 물려받아
    # 교착 상태에 빠질 수 있다(실제로 스레드 버전에서 5분 넘게 멈추는 걸 확인함).
    # 각 워커를 별도 OS 프로세스로 두면 fork 시점에 해당 프로세스가 항상 단일 스레드라
    # 이 문제가 생기지 않는다. 오버서브스크립션을 막기 위해 워커 수는 적당히 제한한다.
    # 32개 심볼 x 8프로세스로 돌렸을 때 각 프로세스가 독립적인 ccxt 인스턴스로 Bybit를
    # 동시에 두드리다 API 쪽에서 사실상 응답이 멈추는 현상을 겪었다(CPU는 낮은데 네트워크만
    # 소모되며 로그가 몇 분간 안 늘어남). 동시 요청 수를 줄이기 위해 워커 수를 낮춘다.
    max_workers = min(len(symbols), os.cpu_count() or 4, 3)
    print(f"{len(symbols)}개 심볼을 {max_workers}개 프로세스로 병렬 처리합니다.")
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_symbol, symbol, args): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                rows.extend(future.result())
            except Exception as exc:  # noqa: BLE001 — 한 심볼 실패해도 나머지 결과는 유지
                print(f"[오류] 심볼 {symbol} 처리 실패: {exc}")

    elapsed = time.monotonic() - started
    print(f"\n총 소요 시간: {elapsed/60:.1f}분, 결과 {len(rows)}건")
    _print_views(rows)


def _better(a: dict, b: dict) -> bool:
    """True면 a가 b보다 낫다 (PF 기준). NaN PF는 항상 진다."""
    pf_a, pf_b = a["profit_factor"], b["profit_factor"]
    if pf_a != pf_a:
        return False
    if pf_b != pf_b:
        return True
    return pf_a > pf_b


def _view(rows: list[dict], *, timeframe_filter, params_filter, gate_key: str) -> list[dict]:
    best_by_key: dict[tuple, dict] = {}
    for row in rows:
        if not (params_filter(row) and timeframe_filter(row)):
            continue
        key = (row["strategy"], row["symbol"])
        current = best_by_key.get(key)
        if current is None or _better(row, current):
            best_by_key[key] = row
    return [row for row in best_by_key.values() if row[gate_key]]


def _print_views(rows: list[dict]) -> None:
    only_default_tf = lambda r: r["is_default_timeframe"]
    any_tf = lambda r: True
    only_default_params = lambda r: r["params_source"] == "default"
    only_optimized_params = lambda r: r["params_source"] == "optimized"
    any_params = lambda r: True

    view_defs = [
        ("0. 베이스라인 (기본 주기 · 기본 파라미터 · 기존 게이트)", only_default_tf, only_default_params, "hard_gate_pass"),
        ("1. 파라미터 최적화만", only_default_tf, only_optimized_params, "hard_gate_pass"),
        ("2. 통계적 유의성 게이트만", only_default_tf, only_default_params, "bootstrap_gate_pass"),
        ("3. 주기 변경만", any_tf, only_default_params, "hard_gate_pass"),
        ("1+2. 파라미터 최적화 + 통계적 유의성", only_default_tf, only_optimized_params, "bootstrap_gate_pass"),
        ("2+3. 주기 변경 + 통계적 유의성", any_tf, only_default_params, "bootstrap_gate_pass"),
        ("1+3. 파라미터 최적화 + 주기 변경", any_tf, only_optimized_params, "hard_gate_pass"),
        ("1+2+3. 전부 결합", any_tf, any_params, "bootstrap_gate_pass"),
    ]

    print("\n" + "=" * 78)
    for title, timeframe_filter, params_filter, gate_key in view_defs:
        passed = _view(rows, timeframe_filter=timeframe_filter, params_filter=params_filter, gate_key=gate_key)
        print(f"\n--- {title} ---")
        if not passed:
            print("  통과한 조합 없음")
            continue
        for row in sorted(passed, key=lambda r: -r["profit_factor"]):
            excess = row['return_pct'] - row['buy_hold_pct']
            print(f"  {row['strategy']:<14} {row['symbol']:<10} {row['timeframe']:<5} "
                  f"({row['params_source']}) 수익률 {row['return_pct']:.2f}% (매수보유 {row['buy_hold_pct']:.2f}%, "
                  f"초과 {excess:+.2f}%p) PF {row['profit_factor']:.2f} "
                  f"MDD {row['max_drawdown_pct']:.2f}% 거래 {row['trades']}건 "
                  f"Sharpe {row['sharpe']:.2f} Sortino {row['sortino']:.2f} Calmar {row['calmar']:.2f}")


if __name__ == "__main__":
    run(parse_args())
