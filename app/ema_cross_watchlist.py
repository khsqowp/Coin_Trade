"""ema_cross 승자 전략을 대기업 대형주 45종목으로 넓혀 후보군을 만든다.

200일선 필터 특성상 "언제 어느 종목이 신호를 낼지" 미리 알 수 없으므로(사용자 지적),
반도체 편중을 피해 섹터를 최대한 분산한 대형주 워치리스트를 두고 다음 두 가지를 확인한다:
  1. 백테스트 — 종목별 ema_cross 기본값/최적화 성과 (app/stock_swing_search.py와 동일 게이트)
  2. 현재 상태 — 지금 이 순간 EMA9>EMA21 & 종가>SMA200 조건이 켜져 있는지, 최근 며칠 내
     골든크로스가 막 발생했는지(신규 진입 시그널) — 실제 감시 대상 후보를 뽑기 위함.
"""
from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
from backtesting import Backtest

from app.kis_auth import issue_token
from app.kis_data import fetch_ohlcv_kis
from app.more_indicators import add_ema_cross_indicators
from app.param_grids import PARAM_GRIDS
from app.strategies import EmaCrossStrategy

MIN_USABLE_BARS = 250
MIN_PROFIT_FACTOR = 1.25
MAX_DRAWDOWN_PCT = 15.0
MIN_TRADES = 5
FRESH_SIGNAL_LOOKBACK = 5  # 최근 며칠 내 크로스면 "막 발생한 신호"로 표시

STOCK_UNIVERSE = [
    # 기존 20종목 (반도체/2차전지 포함)
    ("005930", "삼성전자"), ("000660", "SK하이닉스"), ("035420", "NAVER"), ("035720", "카카오"),
    ("005380", "현대차"), ("000270", "기아"), ("051910", "LG화학"), ("006400", "삼성SDI"),
    ("105560", "KB금융"), ("055550", "신한지주"), ("012330", "현대모비스"), ("373220", "LG에너지솔루션"),
    ("068270", "셀트리온"), ("003670", "포스코퓨처엠"), ("005490", "POSCO홀딩스"), ("015760", "한국전력"),
    ("032830", "삼성생명"), ("086790", "하나금융지주"), ("316140", "우리금융지주"), ("034730", "SK"),
    # 섹터 분산 추가 25종목 — 통신/에너지/해운/화학/비철금속/은행/보험/IT서비스/상사/화장품/
    # 식품/건설/방산/게임/엔터/핀테크/바이오/전자부품/소재/증권
    ("017670", "SK텔레콤"), ("030200", "KT"), ("096770", "SK이노베이션"), ("010950", "S-Oil"),
    ("011200", "HMM"), ("011170", "롯데케미칼"), ("010130", "고려아연"), ("024110", "기업은행"),
    ("000810", "삼성화재"), ("018260", "삼성에스디에스"), ("028260", "삼성물산"), ("090430", "아모레퍼시픽"),
    ("097950", "CJ제일제당"), ("051900", "LG생활건강"), ("000720", "현대건설"), ("047810", "한국항공우주"),
    ("259960", "크래프톤"), ("036570", "엔씨소프트"), ("352820", "하이브"), ("323410", "카카오뱅크"),
    ("207940", "삼성바이오로직스"), ("009150", "삼성전기"), ("011790", "SKC"), ("006800", "미래에셋증권"),
    ("005940", "NH투자증권"),
    # 소형주 프로브(app/kr_smallcap_probe.py)에서 ema_cross 게이트 통과 + 실제 매수&보유 우상향 확인된 종목
    ("058470", "리노공업"), ("214150", "클래시스"), ("041830", "인바디"),
    # 2차 확장 프로브(app/kr_candidate_probe2.py, app/kr_lowprice_probe3.py) 통과분 —
    # 게이트 통과했어도 매수&보유가 실제로 하락한 종목(덴티움/대상/한국가스공사/흥국화재/팬오션 등)은 제외
    ("214450", "파마리서치"), ("161890", "한국콜마"), ("003690", "코리안리"), ("001270", "부국증권"),
    ("003540", "대신증권"), ("082640", "동양생명"), ("003230", "삼양식품"), ("001510", "SK증권"),
    ("005180", "빙그레"), ("029780", "삼성카드"),
    # 3차 확장(app/kr_top200_probe.py, 코스피 시총상위 200 스크리닝) — PF 5 이상 최상위권만 채택
    ("042700", "한미반도체"), ("402340", "SK스퀘어"), ("022100", "포스코DX"), ("007660", "이수페타시스"),
    ("307950", "현대오토에버"), ("298040", "효성중공업"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ema_cross 대형주 45종목 워치리스트 백테스트 + 현재 신호 상태")
    parser.add_argument("--since", default="2019-01-01")
    parser.add_argument("--until", default=None)
    parser.add_argument("--cash", type=float, default=10_000_000)
    parser.add_argument("--commission", type=float, default=0.002)
    parser.add_argument("--max-tries", type=int, default=20)
    return parser.parse_args()


def _score(stats) -> float:
    trades = stats.get("# Trades", 0)
    if trades < 3:
        return -999.0
    pf = stats.get("Profit Factor", float("nan"))
    return -999.0 if pf != pf else pf * min(trades / MIN_TRADES, 1.0)


def _current_signal(enriched: pd.DataFrame) -> dict:
    ema9, ema21, sma200, close = enriched["EMA9"], enriched["EMA21"], enriched["SMA200"], enriched["Close"]
    above_now = bool(ema9.iloc[-1] > ema21.iloc[-1] and close.iloc[-1] > sma200.iloc[-1])
    crossed_up_recently = False
    for lag in range(1, FRESH_SIGNAL_LOOKBACK + 1):
        if len(enriched) <= lag:
            break
        if ema9.iloc[-lag - 1] <= ema21.iloc[-lag - 1] and ema9.iloc[-lag] > ema21.iloc[-lag]:
            crossed_up_recently = True
            break
    return {
        "signal_active": above_now,
        "fresh_cross": crossed_up_recently,
        "last_date": str(enriched.index[-1].date()),
        "last_close": float(close.iloc[-1]),
    }


def _process_symbol(symbol: str, name: str, frame: pd.DataFrame, cash: float, commission: float, max_tries: int) -> dict | None:
    if frame.empty or len(frame) < MIN_USABLE_BARS:
        print(f"  [{name}/{symbol}] 데이터 부족({len(frame)}봉), 건너뜀")
        return None

    enriched = add_ema_cross_indicators(frame).dropna()
    if len(enriched) < MIN_USABLE_BARS:
        print(f"  [{name}/{symbol}] 워밍업 이후 데이터 부족, 건너뜀")
        return None

    signal = _current_signal(enriched)

    try:
        default_stats = Backtest(enriched, EmaCrossStrategy, cash=cash, commission=commission, exclusive_orders=True).run()
    except Exception as exc:  # noqa: BLE001
        print(f"  [오류] {name}/default: {exc}")
        default_stats = None

    optimized_stats = None
    grid = PARAM_GRIDS.get("ema_cross", {})
    if grid:
        try:
            bt = Backtest(enriched, EmaCrossStrategy, cash=cash, commission=commission, exclusive_orders=True)
            optimized_stats = bt.optimize(**grid, maximize=_score, method="grid", max_tries=max_tries, random_state=42, return_heatmap=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  [오류] {name}/optimized: {exc}")

    def _row(stats, source):
        if stats is None:
            return None
        pf = stats.get("Profit Factor", float("nan"))
        mdd = abs(stats.get("Max. Drawdown [%]", float("inf")))
        trades = stats.get("# Trades", 0)
        hard_pass = pf == pf and pf >= MIN_PROFIT_FACTOR and mdd <= MAX_DRAWDOWN_PCT and trades >= MIN_TRADES
        return {"symbol": symbol, "name": name, "source": source, "return_pct": stats.get("Return [%]", float("nan")),
                "profit_factor": pf, "max_drawdown_pct": mdd, "trades": trades, "hard_gate_pass": hard_pass}

    result = {
        "symbol": symbol, "name": name, "signal": signal,
        "default": _row(default_stats, "default"),
        "optimized": _row(optimized_stats, "optimized"),
    }
    d = result["default"]
    o = result["optimized"]
    default_summary = "-" if not d else f"{d['return_pct']:.1f}% PF{d['profit_factor']:.2f}"
    optimized_summary = "-" if not o else f"{o['return_pct']:.1f}% PF{o['profit_factor']:.2f}"
    fresh_tag = "(신규!)" if signal["fresh_cross"] else ""
    print(f"  [{name}] 신호={'ON' if signal['signal_active'] else 'off'}{fresh_tag} "
          f"기본:{default_summary} 최적:{optimized_summary}")
    return result


def run(args: argparse.Namespace) -> None:
    print("[1/3] 한투 모의투자 토큰 발급...")
    token = issue_token()

    print(f"[2/3] {len(STOCK_UNIVERSE)}개 종목 일봉 순차 수집...")
    frames: dict[str, pd.DataFrame] = {}
    for symbol, name in STOCK_UNIVERSE:
        try:
            frame = fetch_ohlcv_kis(symbol, token, args.since, args.until)
        except Exception as exc:  # noqa: BLE001 — 한 종목 실패해도 나머지는 계속
            print(f"  {name}({symbol}): 수집 실패 ({exc}), 건너뜀")
            continue
        frames[symbol] = frame
        print(f"  {name}({symbol}): {len(frame)}봉")

    print("[3/3] ema_cross 백테스트 + 현재 신호 점검 (프로세스 병렬)...")
    started = time.monotonic()
    results: list[dict] = []
    available = [(symbol, name) for symbol, name in STOCK_UNIVERSE if symbol in frames]
    max_workers = min(len(available), os.cpu_count() or 4, 4)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_symbol, symbol, name, frames[symbol], args.cash, args.commission, args.max_tries): (symbol, name)
            for symbol, name in available
        }
        for future in as_completed(futures):
            symbol, name = futures[future]
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as exc:  # noqa: BLE001
                print(f"[오류] {name}({symbol}) 처리 실패: {exc}")

    elapsed = time.monotonic() - started
    print(f"\n총 소요 {elapsed:.0f}초, 종목 {len(results)}개 처리")
    _print_report(results)


def _print_report(results: list[dict]) -> None:
    print("\n" + "=" * 100)
    print("=== 지금 신호 켜진 종목 (EMA9>EMA21 & 종가>SMA200) ===")
    active = [r for r in results if r["signal"]["signal_active"]]
    if not active:
        print("  없음")
    for r in sorted(active, key=lambda r: r["signal"]["fresh_cross"], reverse=True):
        tag = " [신규크로스 5일이내]" if r["signal"]["fresh_cross"] else ""
        d = r["default"]
        default_return = "-" if not d else f"{d['return_pct']:.1f}%"
        print(f"  {r['name']:<10} 종가 {r['signal']['last_close']:,.0f} ({r['signal']['last_date']}){tag} "
              f"백테스트 기본수익률: {default_return}")

    print("\n=== 백테스트 게이트 통과 (수익률순, 상위 20) ===")
    rows = []
    for r in results:
        for key in ("default", "optimized"):
            row = r[key]
            if row and row["hard_gate_pass"]:
                rows.append(row)
    for row in sorted(rows, key=lambda r: -r["return_pct"])[:20]:
        print(f"  {row['name']:<10}{row['source']:<10} 수익률{row['return_pct']:>7.1f}% "
              f"PF{row['profit_factor']:>7.2f} MDD{row['max_drawdown_pct']:>6.1f}% 거래{row['trades']:>4}건")


if __name__ == "__main__":
    run(parse_args())
