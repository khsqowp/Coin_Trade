"""코인간 상대모멘텀 로테이션(선물 롱숏) 라이브 루프 — 백테스트에서 검증된 설정
(lookback 14일 / 3일마다 리밸런스 / 상위·하위 8개, 연환산 29.16%, MDD 18.6%)을 그대로 사용.

실주문 없음(백테스트/페이퍼 모드) — 바이낸스 공개 시세 API만으로 가상 포지션·손익을
추적한다. API 키 불필요, 실계좌 리스크 전혀 없음. 나중에 실거래로 전환하려면 이 루프의
판단 로직은 그대로 두고 주문 실행부만 추가하면 된다(kr/us_swing_loop과 동일 원칙).
"""
from __future__ import annotations

import math
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import ccxt
import pandas as pd

from app.ccxt_retry import retry_read
from app.futures_data import fetch_perp_ohlcv
from app.momentum_state import load_state, log_event, now_iso, save_state
from app.trading_control import read_command
from app.watchdog import run_with_timeout

BOT_ID = "momentum-rotation"

# TON, MKR는 2026-09-23 확인 결과 바이낸스 선물에서 상장폐지(active=False) 상태라 뺐다 —
# 가격이 상폐 시점에 얼어붙어(거래량 0) 모멘텀이 항상 0%에 가깝게 나오고, 이 구간 나머지
# 종목 대부분이 양의 모멘텀이라 거의 매번 하위 12개(숏 타겟)로 뽑혔다가 실주문 단계에서
# "시세없음"으로 스킵됨 — 실측 4회 리밸런스 전부 재현, 매번 숏 12자리 중 2자리가 이 때문에
# 영구 손실되어 롱/숏 포지션 개수가 구조적으로 어긋났다(체감 "롱 편향"의 절반 원인).
UNIVERSE = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "JUP", "ARB", "FIL", "VET",
    "CAKE", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]

LOOKBACK_DAYS = int(os.environ.get("MOMENTUM_ROTATION_LOOKBACK_DAYS", "14"))
REBALANCE_EVERY_DAYS = int(os.environ.get("MOMENTUM_ROTATION_REBALANCE_DAYS", "3"))
TOP_K = int(os.environ.get("MOMENTUM_ROTATION_TOP_K", "8"))
COMMISSION_PCT = 0.04  # 편도, 리밸런스 회전분에만 적용(백테스트와 동일 가정)
START_CAPITAL_USDT = float(os.environ.get("MOMENTUM_ROTATION_START_CAPITAL_USDT", "10000"))
CHECK_INTERVAL_SECONDS = int(os.environ.get("MOMENTUM_ROTATION_CHECK_INTERVAL_SECONDS", "120"))
CYCLE_TIMEOUT_SECONDS = int(os.environ.get("MOMENTUM_ROTATION_CYCLE_TIMEOUT_SECONDS", "300"))
# equity_history 표본 간격 — CHECK_INTERVAL_SECONDS(현재 15초, 순수 표시 새로고침용)와 분리.
# 둘을 안 나누면 대시보드/표시 주기를 올릴 때마다 history 표본도 같이 촘촘해져서, 개수 상한에
# 금방 도달해 오래된 표본이 밀려나고 "일간/주간/전체" 차트가 전부 최근 몇 시간 창으로
# 수렴해버린다(2026-09-25, 사용자가 세 기간 차트가 똑같아 보인다고 제보해서 발견 — CHECK_INTERVAL
# 15초 x 2000개 = 최대 8.3시간치 밖에 안 남아있었음).
EQUITY_HISTORY_SAMPLE_SECONDS = int(os.environ.get("MOMENTUM_ROTATION_EQUITY_HISTORY_SAMPLE_SECONDS", "300"))
# 표본 개수 상한 — 위 간격 5분 기준 25920개 = 90일치 보존(2026-09-26, 상한을 2000개로 둔 채라
# 5분 간격이어도 최대 6.9일치밖에 못 담아 "월간/전체"가 계속 같은 그래프로 보이는 걸 재발견해서
# 올림). 점 1개 ~70바이트라 90일치도 상태파일 기준 2MB 안팎 — 90일보다 더 긴 진짜 장기(연 단위)
# 보관은 이 flat cap 방식 자체의 한계라 별도로 일별 롤업 구조가 필요하다.
EQUITY_HISTORY_MAX_POINTS = int(os.environ.get("MOMENTUM_ROTATION_EQUITY_HISTORY_MAX_POINTS", "25920"))
# 수동 제어(즉시 매도/진입) 명령 폴링 주기 — 무거운 사이클과 분리해 거의 틱단위로 반응한다.
CONTROL_POLL_SECONDS = int(os.environ.get("MOMENTUM_ROTATION_CONTROL_POLL_SECONDS", "5"))
SINCE_DAYS_FOR_MOMENTUM = LOOKBACK_DAYS + 10

# --- 실거래 설정 ---
LIVE = os.environ.get("MOMENTUM_ROTATION_LIVE", "false").lower() == "true"
EXCHANGE_MODE = os.environ.get("MOMENTUM_ROTATION_EXCHANGE", "testnet")  # testnet | mainnet
LEVERAGE = int(os.environ.get("MOMENTUM_ROTATION_LEVERAGE", "1"))
# 안전 상한(절대 USDT, 선택): 선물지갑에 이보다 많이 들어있어도 이 금액까지만 굴린다(0 = 비활성).
MAX_DEPLOY_USDT = float(os.environ.get("MOMENTUM_ROTATION_MAX_DEPLOY_USDT", "0"))
# 배치 비율(선택): equity 의 이 비율까지만 굴린다(0 = 비활성, 1.0 = 전액). MAX_DEPLOY_USDT 와 같이
# 켜져 있으면 둘 다 적용해 더 작은 쪽을 쓴다 — 잔고가 늘어나도 절대 상한을 넘지 않게 하는 이중 안전장치.
DEPLOY_PCT = float(os.environ.get("MOMENTUM_ROTATION_DEPLOY_PCT", "0"))
DELEVER_DD = float(os.environ.get("MOMENTUM_ROTATION_DELEVER_DD", "1.0"))
KILL_DD = float(os.environ.get("MOMENTUM_ROTATION_KILL_DD", "0.35"))
RESET_HALT = os.environ.get("MOMENTUM_ROTATION_RESET_HALT", "false").lower() == "true"

CRASH_FILTER = os.environ.get("MOMENTUM_ROTATION_CRASH_FILTER", "true").lower() == "true"
CRASH_THRESHOLD = float(os.environ.get("MOMENTUM_ROTATION_CRASH_THRESHOLD", "-0.10"))
CRASH_LOOKBACK_DAYS = int(os.environ.get("MOMENTUM_ROTATION_CRASH_LOOKBACK_DAYS", "14"))
KILL_COOLDOWN_DAYS = int(os.environ.get("MOMENTUM_ROTATION_KILL_COOLDOWN_DAYS", "14"))
PROFIT_LOCK = os.environ.get("MOMENTUM_ROTATION_PROFIT_LOCK", "false").lower() == "true"
PROFIT_LOCK_ACTIVATION = float(os.environ.get("MOMENTUM_ROTATION_PROFIT_LOCK_ACTIVATION", "0.20"))
PROFIT_LOCK_TRAIL = float(os.environ.get("MOMENTUM_ROTATION_PROFIT_LOCK_TRAIL", "0.25"))
PROFIT_LOCK_COOLDOWN_DAYS = int(os.environ.get("MOMENTUM_ROTATION_PROFIT_LOCK_COOLDOWN_DAYS", "3"))
MIN_K = 3
MIN_COST_DEFAULT = 5.0
MIN_COST_MULT = 1.25
MIN_POSITION_NOTIONAL_FLOOR = 6.25


def profit_lock_eval(state, equity, now):
    """UTC 날짜 첫 표본만 평가; orig 기준은 이체 조정 inception으로 고정한다."""
    if not PROFIT_LOCK:
        return None
    defaults = dict(profit_lock_enabled=True, profit_lock_active=False,
                    profit_lock_until=None, profit_peak_equity_usdt=equity,
                    profit_lock_armed=False, profit_lock_trigger_ts=None,
                    profit_lock_trigger_count=0, profit_lock_trigger_equity_usdt=None,
                    profit_lock_drop_pct=0.0, profit_lock_flatten_pending=False,
                    profit_lock_last_eval_date=None)
    for key, value in defaults.items():
        state.setdefault(key, value)
    state["profit_lock_enabled"] = True
    today = now.astimezone(timezone.utc).date().isoformat()
    peak = float(state["profit_peak_equity_usdt"])
    state["profit_lock_drop_pct"] = 1 - equity / peak if peak > 0 else 0.0
    if state["profit_lock_active"]:
        if now < datetime.fromisoformat(state["profit_lock_until"]):
            return None
        state.update(profit_lock_active=False, profit_lock_until=None,
                     profit_peak_equity_usdt=equity, hwm_usdt=equity, drawdown=0.0,
                     profit_lock_armed=equity >= state["inception_equity_usdt"] * (1 + PROFIT_LOCK_ACTIVATION),
                     profit_lock_drop_pct=0.0, profit_lock_last_eval_date=today,
                     last_rebalance_ts=None)
        return "expire"
    if state["profit_lock_last_eval_date"] == today:
        return None
    peak = max(peak, equity)
    armed = peak >= state["inception_equity_usdt"] * (1 + PROFIT_LOCK_ACTIVATION)
    state.update(profit_peak_equity_usdt=peak, profit_lock_armed=armed,
                 profit_lock_drop_pct=1 - equity / peak if peak > 0 else 0.0,
                 profit_lock_last_eval_date=today)
    if armed and equity <= peak * (1 - PROFIT_LOCK_TRAIL):
        state.update(profit_lock_active=True,
                     profit_lock_until=(now + timedelta(days=PROFIT_LOCK_COOLDOWN_DAYS)).isoformat(),
                     profit_lock_trigger_ts=now.isoformat(), profit_lock_trigger_equity_usdt=equity,
                     profit_lock_trigger_count=state["profit_lock_trigger_count"] + 1,
                     profit_lock_flatten_pending=True)
        return "trigger"
    return None


def _profit_lock_flatten(state, client, owned, trigger=False):
    from app.momentum_rotation_exec import flatten_all, sync_positions

    owned |= set(state.get("profit_lock_flatten_owned", []))
    state["profit_lock_flatten_owned"] = sorted(owned)
    if trigger or (state.get("profit_lock_flatten_pending") and owned & set(sync_positions(client))):
        flatten_all(client, lambda message: log_event(state, message), owned=owned, tag="PROFIT")
    positions = {b: p for b, p in sync_positions(client).items() if b in owned}
    state["profit_lock_flatten_pending"] = bool(positions)
    if not positions:
        state["profit_lock_flatten_owned"] = []
    state["positions"] = {}
    state["unrealized_pnl_usdt"] = sum(p["unrealized_pnl"] for p in positions.values())
    return bool(positions)


def _profit_lock_cycle(state, client, owned, equity, now):
    if not PROFIT_LOCK:
        return False
    event = profit_lock_eval(state, equity, now)
    if event == "trigger":
        log_event(state, f"[LIVE] PROFIT 발동 — equity {equity:.2f}, "
                         f"peak {state['profit_peak_equity_usdt']:.2f}, "
                         f"drop {state['profit_lock_drop_pct']:.2%}")
    pending = False
    if state.get("profit_lock_active") or state.get("profit_lock_flatten_pending"):
        pending = _profit_lock_flatten(state, client, owned, event == "trigger")
    if event == "expire":
        log_event(state, f"[LIVE] PROFIT 재무장 — peak/hwm {equity:.2f}, 최초 기준 유지")
    if state.get("profit_lock_active") or pending:
        update_crash_flag(state, _fetch_btc_daily_closes, now)
        today = now.astimezone(timezone.utc).date().isoformat()
        if state.get("profit_lock_status_date") != today:
            state["profit_lock_status_date"] = today
            log_event(state, f"[LIVE] PROFIT flat 유지 — until {state['profit_lock_until']}, "
                             f"청산 대기 {pending}")
        return True
    return False


def _effective_leverage(dd):
    return 1 if DELEVER_DD < 1.0 and dd >= DELEVER_DD and LEVERAGE > 1 else LEVERAGE


def compute_sizing(equity, leverage, deploy_pct, max_deploy, top_k,
                   exchange_min_cost=MIN_COST_DEFAULT):
    deploy = min(equity, equity * deploy_pct) if deploy_pct > 0 else equity
    if max_deploy > 0:
        deploy = min(deploy, max_deploy)
    gross = deploy * leverage
    minimum = max(exchange_min_cost * MIN_COST_MULT, MIN_POSITION_NOTIONAL_FLOOR)
    capacity = math.floor(gross / (2 * minimum) + 1e-9)
    flat = capacity < MIN_K
    k = 0 if flat else max(MIN_K, min(top_k, capacity))
    return dict(deploy=deploy, gross=gross, k_eff=k,
                notional_per_pos=gross / (2 * k) if k else 0.0,
                gross_multiple=gross / equity if equity > 0 else 0.0,
                margin_use=deploy / equity if equity > 0 else 0.0,
                min_notional=minimum, shrunk=k < top_k, flat=flat)


def select_targets(ranked, k, notional, min_notional_fn):
    longs, shorts, skipped = [], [], []
    for side, candidates, chosen in (("long", ranked.index, longs),
                                     ("short", ranked.index[::-1], shorts)):
        for base in candidates:
            if len(chosen) >= k:
                break
            if base in longs or base in shorts:
                continue
            minimum = min_notional_fn(base)
            if minimum > notional + 1e-9:
                skipped.append(f"{base}({side}, 필요 ${minimum:g} > 명목 ${notional:g})")
                continue
            chosen.append(base)
    count = min(len(longs), len(shorts))
    if count < MIN_K:
        return {}, {}, skipped
    targets = {b: "long" for b in longs[:count]}
    targets.update({b: "short" for b in shorts[:count]})
    return targets, {b: float(ranked[b]) for b in targets}, skipped


def btc_crash_signal(daily_closes, now, lookback, threshold):
    date = pd.Timestamp(now).tz_convert("UTC").normalize()
    closed = daily_closes.loc[daily_closes.index < date].sort_index()
    if len(closed) < lookback + 1:
        return None
    ret = float(closed.iloc[-1] / closed.iloc[-1-lookback] - 1)
    return dict(ret=ret, asof=closed.index[-1].date().isoformat(), crash=ret < threshold)


def update_crash_flag(state, daily_closes_fn, now):
    today = pd.Timestamp(now).tz_convert("UTC").date().isoformat()
    if not CRASH_FILTER:
        # 필터를 끈 상태에서 이전에 켜진 플래그가 남아 있으면 영구 flat 이 되므로 해제한다.
        if state.get("crash_flat"):
            state["crash_flat"] = False
            log_event(state, "[LIVE] BTC 급락필터 비활성 — 기존 플래그 해제")
            return "exit"
        return None
    if state.get("crash_check_date") == today:
        return None
    try:
        signal = btc_crash_signal(daily_closes_fn(), now, CRASH_LOOKBACK_DAYS, CRASH_THRESHOLD)
    except Exception as exc:  # noqa: BLE001
        print(f"  BTC 일봉 조회 실패, 급락필터 다음 사이클 재시도 ({exc})", flush=True)
        return None
    if signal is None:
        return None
    previous = state.get("crash_flat", False)
    state.update(crash_check_date=today, crash_ret=signal["ret"], crash_flat=signal["crash"])
    if previous == signal["crash"]:
        return None
    event = "enter" if signal["crash"] else "exit"
    log_event(state, f"[LIVE] BTC 급락필터 {event} — {today}, 수익률 {signal['ret']:.2%}, 기준 {CRASH_THRESHOLD:.2%}")
    return event


def _fetch_btc_daily_closes():
    since = datetime.now(timezone.utc) - timedelta(days=CRASH_LOOKBACK_DAYS + 10)
    return fetch_perp_ohlcv("BTC/USDT:USDT", "1d", since_iso=since.isoformat())["Close"]


def _symbol_min_notional(client, base, price):
    try:
        limits = client.market(_perp_symbol(base)).get("limits") or {}
        return max(float((limits.get("cost") or {}).get("min") or MIN_COST_DEFAULT),
                   float((limits.get("amount") or {}).get("min") or 0) * price)
    except Exception:
        return MIN_COST_DEFAULT


def _perp_symbol(base: str) -> str:
    return f"{base}/USDT:USDT"


def _should_sample_equity_history(state: dict) -> bool:
    """직전 표본 이후 EQUITY_HISTORY_SAMPLE_SECONDS 이상 지났을 때만 True — CHECK_INTERVAL_SECONDS
    가 아무리 짧아져도 history 표본 밀도는 이 간격으로 고정된다."""
    history = state.get("equity_history") or []
    if not history:
        return True
    last_ts = history[-1].get("ts")
    if not last_ts:
        return True
    try:
        last = datetime.fromisoformat(last_ts)
    except ValueError:
        return True
    return (datetime.now(timezone.utc) - last).total_seconds() >= EQUITY_HISTORY_SAMPLE_SECONDS


# 일별 롤업 — equity_history(고밀도, 상한 있음)와 별도로 날짜가 바뀔 때마다 그 날짜의 마지막
# 값을 하나씩만 쌓는다. 하루 1개라 상한을 넉넉히(3650 = 10년) 둬도 상태파일에 부담이 거의 없고
# (점 하나 ~30바이트, 10년치도 100KB 안팎), fine 배열의 보존기간(봇마다 다르지만 현재 수 주~90일)을
# 넘어서도 "월간/전체" 차트가 실제 장기 추세를 보여줄 수 있다(2026-09-26, EQUITY_HISTORY_MAX_POINTS
# 를 올려도 결국 flat cap이라 진짜 장기(연 단위)는 못 담는다는 한계를 메우려고 추가).
# momentum_rotation_loop/coin_swing6_trade/stock_rotation_loop가 전부 이 함수를 공유한다 —
# 값의 의미(usdt/krw)는 봇마다 다르지만 저장 형태는 {"ts": "YYYY-MM-DD", "value": <숫자>}로 통일해
# 프런트가 봇별 필드명을 몰라도 그대로 병합해 쓸 수 있게 한다.
EQUITY_HISTORY_DAILY_MAX_POINTS = 3650


def _rollup_daily_history(state: dict, value: float) -> None:
    daily = state.setdefault("equity_history_daily", [])
    today = datetime.now(timezone.utc).date().isoformat()
    if daily and daily[-1]["ts"] == today:
        daily[-1]["value"] = value
    else:
        daily.append({"ts": today, "value": value})
        if len(daily) > EQUITY_HISTORY_DAILY_MAX_POINTS:
            state["equity_history_daily"] = daily[-EQUITY_HISTORY_DAILY_MAX_POINTS:]


_PRICE_CLIENT_TIMEOUT_MS = 15000
_MARKETS_REFRESH_SECONDS = 24 * 3600
_price_client = None
_price_client_loaded_at = 0.0
_price_client_lock = threading.Lock()


def _get_price_client():
    """공개 시세 전용 ccxt 클라이언트 — 15초 사이클마다 새로 만들지 않고 재사용한다.
    마켓 정보(exchangeInfo)는 최초 1회 로드하고 하루에 한 번만 갱신."""
    global _price_client, _price_client_loaded_at
    with _price_client_lock:
        if _price_client is None:
            _price_client = ccxt.binance({
                "enableRateLimit": True, "timeout": _PRICE_CLIENT_TIMEOUT_MS,
                "options": {"defaultType": "future"},
            })
            _price_client_loaded_at = 0.0
        if time.monotonic() - _price_client_loaded_at >= _MARKETS_REFRESH_SECONDS or not _price_client.markets:
            retry_read(_price_client.load_markets, True)
            _price_client_loaded_at = time.monotonic()
        return _price_client


def _fetch_current_prices() -> dict[str, float]:
    prices = {}
    want = {_perp_symbol(b): b for b in UNIVERSE}
    try:
        exchange = _get_price_client()
        # 47종목을 개별 fetch_ticker 로 부르면 IP 밴(-1003) 위험 — 한 번에 받는다.
        tickers = retry_read(exchange.fetch_tickers, list(want))
        for symbol, base in want.items():
            last = (tickers.get(symbol) or {}).get("last")
            if last:
                prices[base] = last
    except Exception as exc:  # noqa: BLE001
        print(f"  일괄 시세조회 실패, 개별 폴백 ({exc})", flush=True)
        try:
            exchange = _get_price_client()
        except Exception as exc2:  # noqa: BLE001
            print(f"  시세 클라이언트 초기화 실패 ({exc2})", flush=True)
            return prices
        for symbol, base in want.items():
            try:
                prices[base] = exchange.fetch_ticker(symbol)["last"]
            except Exception as exc2:  # noqa: BLE001
                print(f"  {base}: 시세조회 실패 ({exc2})", flush=True)
    return prices


def _price_gap_blocks_rebalance(prices: dict[str, float], held, ranked_all) -> list[str]:
    """부분 시세 실패 시 리밸런스를 막아야 하는 누락 종목 목록(없으면 빈 리스트).

    시세 없는 종목은 랭킹에서 빠지고(타겟 대체) 보유 종목이면 타겟에 못 들어가 apply_targets 가
    멀쩡한 보유분을 청산해버린다. 보유 종목 또는 상/하위 TOP_K 후보에 시세가 없으면 막는다.
    (상폐 등으로 영구 누락된 중하위 종목 때문에 리밸런스가 영구 정지되지 않게 그 외는 무시.)"""
    critical = set(held) | set(ranked_all.index[:TOP_K]) | set(ranked_all.index[-TOP_K:])
    return sorted(b for b in critical if not prices.get(b))


def _fetch_momentum_ranking() -> pd.Series:
    since_iso = (datetime.now(timezone.utc) - timedelta(days=SINCE_DAYS_FOR_MOMENTUM)).isoformat()
    momentum = {}
    for base in UNIVERSE:
        try:
            frame = fetch_perp_ohlcv(_perp_symbol(base), "1d", since_iso, None)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base}: 일봉 조회 실패 ({exc})", flush=True)
            continue
        if len(frame) < LOOKBACK_DAYS + 1:
            continue
        closes = frame["Close"]
        momentum[base] = closes.iloc[-1] / closes.iloc[-1 - LOOKBACK_DAYS] - 1
    return pd.Series(momentum)


def _mark_to_market(state: dict, prices: dict[str, float]) -> float:
    """직전 리밸런스 이후 보유 포지션의 미실현손익 합계를 계산한다(자본 자체는 건드리지 않음)."""
    total = 0.0
    for symbol, pos in state["positions"].items():
        price = prices.get(symbol)
        if price is None or not pos.get("entry_price"):
            continue
        side_sign = 1.0 if pos["side"] == "long" else -1.0
        pnl = pos["notional_usdt"] * side_sign * (price / pos["entry_price"] - 1)
        pos["unrealized_pnl_usdt"] = pnl
        total += pnl
    return total


def _rebalance(state: dict, prices: dict[str, float]) -> None:
    momentum = _fetch_momentum_ranking()
    momentum = momentum[momentum.index.isin(prices.keys())]
    if len(momentum) < TOP_K * 2:
        log_event(state, f"모멘텀 데이터 부족({len(momentum)}종목) — 이번 리밸런스 건너뜀")
        return

    # 직전 사이클 미실현손익을 실현손익으로 확정하고 자본에 반영
    unrealized = sum(p.get("unrealized_pnl_usdt", 0.0) for p in state["positions"].values())
    state["cumulative_realized_pnl_usdt"] = state.get("cumulative_realized_pnl_usdt", 0.0) + unrealized
    capital_before = START_CAPITAL_USDT + state["cumulative_realized_pnl_usdt"] - state.get("cumulative_fee_usdt", 0.0)

    ranked = momentum.sort_values(ascending=False)
    longs = list(ranked.index[:TOP_K])
    shorts = list(ranked.index[-TOP_K:])
    weight_each = 0.5 / TOP_K

    old_symbols = set(state["positions"].keys())
    new_symbols = set(longs) | set(shorts)
    turnover_legs = len(old_symbols.symmetric_difference(new_symbols)) + len(old_symbols & new_symbols)
    # 회전(포지션이 바뀌거나 유지되며 재설정되는 경우 전부)에 왕복 아닌 편도 수수료를 적용 —
    # 백테스트(futures_momentum_rotation_probe.py)의 turnover 가정과 동일한 근사치.
    fee = abs(capital_before) * COMMISSION_PCT / 100 * (turnover_legs / max(len(new_symbols), 1))
    state["cumulative_fee_usdt"] = state.get("cumulative_fee_usdt", 0.0) + fee

    capital_after_fee = capital_before - fee
    new_positions = {}
    for symbol in longs:
        new_positions[symbol] = {
            "side": "long", "entry_price": prices[symbol],
            "notional_usdt": capital_after_fee * weight_each, "unrealized_pnl_usdt": 0.0,
        }
    for symbol in shorts:
        new_positions[symbol] = {
            "side": "short", "entry_price": prices[symbol],
            "notional_usdt": capital_after_fee * weight_each, "unrealized_pnl_usdt": 0.0,
        }
    state["positions"] = new_positions
    state["last_rebalance_ts"] = now_iso()
    state["equity_usdt"] = capital_after_fee

    log_event(
        state,
        f"리밸런스 완료 — 자본 {capital_after_fee:,.2f} USDT (직전 미실현 {unrealized:+,.2f} 실현반영, 수수료 -{fee:.2f}) "
        f"롱: {','.join(longs)} / 숏: {','.join(shorts)}",
    )


def _ranked_momentum():
    return _fetch_momentum_ranking().sort_values(ascending=False)


def _target_sides():
    """기존 라이브 점검 스크립트 호환."""
    ranked = _ranked_momentum()
    if len(ranked) < TOP_K * 2:
        return None
    targets = {b: "long" for b in ranked.index[:TOP_K]}
    targets.update({b: "short" for b in ranked.index[-TOP_K:]})
    return targets, {b: float(ranked[b]) for b in targets}


def _rebalance_live(state: dict, prices: dict[str, float], eff_lev: int) -> bool:
    """리밸런스를 실행했으면 True, 건너뛰었으면 False."""
    from app.momentum_rotation_exec import account_equity_usdt, apply_targets, exec_client, sync_positions

    client = exec_client(EXCHANGE_MODE)
    equity = account_equity_usdt(client)
    sizing = compute_sizing(equity, eff_lev, DEPLOY_PCT, MAX_DEPLOY_USDT, TOP_K)
    ranked = _ranked_momentum()
    if len(ranked) < TOP_K * 2:
        log_event(state, "모멘텀 데이터 부족 — 이번 리밸런스 건너뜀")
        return False
    gap = _price_gap_blocks_rebalance(prices, state.get("positions", {}), ranked)
    if gap:
        log_event(state, f"[LIVE] 시세 누락 {gap} — 보유/상하위 후보 시세가 없어 이번 리밸런스 건너뜀(다음 사이클 재시도, 주문 없음)")
        return False
    ranked = ranked.loc[[b for b in ranked.index if prices.get(b)]]
    targets, scores, skipped = ({}, {}, []) if sizing["flat"] else select_targets(
        ranked, sizing["k_eff"], sizing["notional_per_pos"],
        lambda b: _symbol_min_notional(client, b, prices[b]))
    if not targets:
        log_event(state, "[LIVE] 최소명목 불가 — flat")
    effective_k = len(targets) // 2
    notional_per_pos = sizing["notional_per_pos"]
    state["effective_k"] = effective_k
    state["gross_multiple_target"] = sizing["gross_multiple"] if targets else 0.0
    shrink = f" ({TOP_K} -> {effective_k})" if effective_k < TOP_K else ""
    log_event(state, f"[LIVE:{EXCHANGE_MODE}] 리밸런스 시작 — equity {equity:.2f} / 운용 {sizing['deploy']:.2f} USDT, "
                     f"배율 {eff_lev}x, 유효 K {effective_k}{shrink}, 포지션당 명목 {notional_per_pos:.2f} USDT, "
                     f"목표 총명목배율 {state['gross_multiple_target']:.6f}, 마진사용 {sizing['margin_use']:.2%}")
    for item in skipped:
        log_event(state, f"[LIVE] 최소명목 제외·후순위 대체: {item}")

    owned = set(state.get("positions", {}))
    result = apply_targets(client, prices, targets, notional_per_pos, eff_lev,
                           lambda m: log_event(state, m), owned=owned)

    all_positions = sync_positions(client)
    managed = set(targets) | owned
    positions = {b: p for b, p in all_positions.items() if b in managed}
    state["positions"] = {
        b: {"side": p["side"], "entry_price": p["entry_price"], "mark_price": p["mark_price"],
            "notional_usdt": p["notional"], "unrealized_pnl_usdt": p["unrealized_pnl"]}
        for b, p in positions.items()
    }
    state["gross_multiple_realized"] = sum(p["notional"] for p in positions.values()) / equity if equity > 0 else 0.0
    log_event(state, f"[LIVE] 실현 총명목배율 {state['gross_multiple_realized']:.6f}")
    state["last_rebalance_ts"] = now_iso()
    state["equity_usdt"] = equity
    # 이 함수는 정기(2~3일) 자동 리밸런스와 수동 "지금 진입" 양쪽에서 공통으로 호출되는 유일한 진입점이다
    # — 트리거가 뭐였든 여기서 세션(마지막 리밸런스 이후 손익)을 항상 새로 시작한다.
    state["session_start_equity_usdt"] = equity
    state["session_start_ts"] = state["last_rebalance_ts"]

    # 진입 시점 모멘텀 점수를 남겨둔다 — 지금 당장 선정 로직을 바꾸진 않지만(하루치로는 과최적화),
    # 나중에 바이낸스 실현손익 이력(심볼+시각으로 대조 가능)과 합쳐서 "점수 높을수록 실제 수익도
    # 컸는가"를 진짜 데이터로 검증할 근거가 쌓인다. 무한정 커지지 않게 최근 4000건만 유지한다
    # (2일 주기 리밸런스 기준 대략 몇 년치 분량).
    entry_log = state.setdefault("entry_log", [])
    for b, p in state["positions"].items():
        entry_log.append({
            "ts": state["last_rebalance_ts"], "symbol": b, "side": p["side"],
            "momentum_score": scores.get(b), "entry_price": p["entry_price"],
            "notional_usdt": p["notional_usdt"],
        })
    if len(entry_log) > 4000:
        state["entry_log"] = entry_log[-4000:]
    log_event(state, f"[LIVE:{EXCHANGE_MODE}] 리밸런스 완료 — 진입 {result['opened']}, 청산 {result['closed']}, "
                     f"스킵 {result['skipped']}, 오류 {result['errors']} / 실보유 {len(positions)}종목")
    return True


def _apply_external_transfers(state: dict, client) -> None:
    """스팟↔선물 지갑 이체(입출금)는 매매손익이 아니다 — 그런데 이걸 구분 안 하면 equity 가 그만큼
    뛰거나 떨어질 때 전부 "수익"·"손실"로 잡혀버린다(실제로 2026-09-16 겪은 버그: 74 USDT 이체를
    +100%대 수익률로 표시). 바이낸스 선물 income 이력의 incomeType=TRANSFER 가 곧 입출금 기록이라,
    매 사이클 마지막 확인 이후 새로 생긴 이체를 찾아 inception/session 베이스라인과 hwm 을 그만큼
    같이 밀어준다 — 그러면 이후 계산되는 수익률은 순수하게 매매 성과만 반영한다.
    """
    last_ms = int(state.get("last_transfer_check_ms") or 0)
    try:
        rows = client.fapiPrivateGetIncome({"incomeType": "TRANSFER", "startTime": last_ms + 1, "limit": 1000})
    except Exception as exc:  # noqa: BLE001
        log_event(state, f"[LIVE] 입출금 이력 조회 실패(다음 사이클 재시도): {exc}")
        return
    if not rows:
        return
    state["last_transfer_check_ms"] = max(int(r["time"]) for r in rows)
    net = sum(float(r["income"]) for r in rows)
    if net == 0:
        return
    for key in ("inception_equity_usdt", "session_start_equity_usdt", "hwm_usdt",
                "profit_peak_equity_usdt"):
        if state.get(key) is not None:
            state[key] = float(state[key]) + net
    log_event(state, f"[LIVE] 지갑 이체 감지: {net:+.2f} USDT — 입출금은 손익이 아니라서 수익률 베이스라인을 그만큼 같이 옮김")


def _run_cycle_live(state: dict, prices: dict[str, float]) -> None:
    from app.momentum_rotation_exec import account_equity_usdt, exec_client, flatten_all, sync_positions

    client = exec_client(EXCHANGE_MODE)
    equity = account_equity_usdt(client)

    if state.get("inception_ts") is None:
        state["inception_ts"] = now_iso()
        state["hwm_usdt"] = equity
        state["inception_equity_usdt"] = equity
        # 이 시점 이전 이체는 이미 관측된 inception 잔고에 녹아있으니 재적용하면 안 된다 — 지금부터만 추적.
        state["last_transfer_check_ms"] = int(time.time() * 1000)
        log_event(state, f"[LIVE:{EXCHANGE_MODE}] 실거래 루프 시작 — equity {equity:.2f} USDT, 기준배율 {LEVERAGE}x")

    # 순서: 이체 → RESET_HALT/손실 쿨다운 → hwm/dd → 손실 halt 반환 →
    # LOSS KILL(최우선) → PROFIT LOCK → BTC 급락필터 → 디레버/리밸런스.
    # PROFIT 재무장 시에만 hwm을 리셋하며, 같은 사이클 손실 kill이면 보호 평가를 하지 않는다.
    _apply_external_transfers(state, client)
    now = datetime.now(timezone.utc)

    if RESET_HALT and state.get("halted"):
        state["halted"] = False
        state["hwm_usdt"] = equity
        state["kill_ts"] = None
        log_event(state, "[LIVE] halt 수동 해제 — hwm 재설정")

    remaining = None
    if state.get("halted") and KILL_COOLDOWN_DAYS > 0:
        if not state.get("kill_ts"):
            state["kill_ts"] = now.isoformat()
            log_event(state, "[LIVE] 기존 halt 상태 — 킬 쿨다운을 지금부터 시작")
        elapsed = now - datetime.fromisoformat(state["kill_ts"])
        remaining = max(0.0, KILL_COOLDOWN_DAYS - elapsed.total_seconds() / 86400)
        if elapsed >= timedelta(days=KILL_COOLDOWN_DAYS):
            state.update(halted=False, hwm_usdt=equity, kill_ts=None)
            log_event(state, f"[LIVE] 킬 쿨다운 {KILL_COOLDOWN_DAYS}일 경과 — hwm 재설정, 다음 리밸런스에서 재진입")

    hwm = max(float(state.get("hwm_usdt") or equity), equity)
    state["hwm_usdt"] = hwm
    dd = 1.0 - equity / hwm if hwm > 0 else 0.0
    state["drawdown"] = dd
    state["equity_usdt"] = equity

    if state.get("halted"):
        cooldown = f"쿨다운 잔여 {remaining:.2f}일" if remaining is not None else "자동 쿨다운 해제 꺼짐"
        log_event(state, f"[LIVE] halt 상태 — 거래 중단 중 (dd {dd*100:.1f}%). "
                         f"{cooldown}. MOMENTUM_ROTATION_RESET_HALT=true 로 수동 해제")
        return

    owned = set(state.get("positions", {}))
    all_positions = sync_positions(client)
    unmanaged = set(all_positions) - owned - set(UNIVERSE)
    if unmanaged:
        log_event(state, f"[LIVE] 경고: 이 전략이 모르는 선물 포지션 {sorted(unmanaged)} — "
                         f"다른 전략과 지갑을 공유 중이면 equity/드로다운 계산이 오염됨. 전용 지갑 권장.")

    if dd >= KILL_DD:
        log_event(state, f"[LIVE] 킬 스위치 발동 — dd {dd*100:.1f}% >= {KILL_DD*100:.0f}%. 전량 청산 후 정지.")
        flatten_all(client, lambda m: log_event(state, m), owned=owned)
        state["halted"] = True
        state["kill_ts"] = now_iso()
        state["positions"] = {}
        return

    if _profit_lock_cycle(state, client, owned, equity, now):
        return
    dd = state["drawdown"]  # PROFIT 만료는 hwm/dd를 현재 equity로 재설정한다.

    event = update_crash_flag(state, _fetch_btc_daily_closes, now)
    if event == "enter":
        state["crash_flatten_owned"] = sorted(owned)
        flatten_all(client, lambda m: log_event(state, m), owned=owned, tag="CRASH")
        state["positions"] = {}
        state["crash_flatten_pending"] = True
    if state.get("crash_flat"):
        owned |= set(state.get("crash_flatten_owned", [])) if state.get("crash_flatten_pending") else set()
        all_positions = sync_positions(client)
        if state.get("crash_flatten_pending"):
            if owned & set(all_positions):
                flatten_all(client, lambda m: log_event(state, m), owned=owned, tag="CRASH")
                all_positions = sync_positions(client)
            if not owned & set(all_positions):
                state["crash_flatten_pending"] = False
                state["crash_flatten_owned"] = []
        positions = {b: p for b, p in all_positions.items() if b in owned}
        state["positions"] = {
            b: {"side": p["side"], "entry_price": p["entry_price"], "mark_price": p["mark_price"],
                "notional_usdt": p["notional"], "unrealized_pnl_usdt": p["unrealized_pnl"]}
            for b, p in positions.items()
        }
        state["unrealized_pnl_usdt"] = sum(p["unrealized_pnl"] for p in positions.values())
        return
    if event == "exit":
        log_event(state, "[LIVE] BTC 급락필터 해제 — 새 랭킹으로 재진입")
        state.update(last_rebalance_ts=None, manual_flat=False, crash_flatten_pending=False)
        state["crash_flatten_owned"] = []

    eff_lev = _effective_leverage(dd)
    if eff_lev != LEVERAGE:
        log_event(state, f"[LIVE] 디레버 발동 — dd {dd*100:.1f}% >= {DELEVER_DD*100:.0f}%, 배율 {LEVERAGE}x → {eff_lev}x")

    due = state.get("last_rebalance_ts") is None
    if not due:
        last = datetime.fromisoformat(state["last_rebalance_ts"])
        due = datetime.now(timezone.utc) - last >= timedelta(days=REBALANCE_EVERY_DAYS)

    # 수동 정지(즉시 매도) 중이면 flat 유지 — 자동 재진입은 정기 리밸런스 시각에만.
    if state.get("manual_flat"):
        if due:
            log_event(state, "[LIVE] 수동 정지 중 정기 리밸런스 시각 도달 — 자동 재진입")
            state["manual_flat"] = False
            state["manual_flat_ts"] = None
        else:
            state["positions"] = {}
            state["unrealized_pnl_usdt"] = 0.0
            return

    if due:
        _rebalance_live(state, prices, eff_lev)
    else:
        positions = {b: p for b, p in all_positions.items() if b in owned}
        state["positions"] = {
            b: {"side": p["side"], "entry_price": p["entry_price"], "mark_price": p["mark_price"],
                "notional_usdt": p["notional"], "unrealized_pnl_usdt": p["unrealized_pnl"]}
            for b, p in positions.items()
        }
        state["unrealized_pnl_usdt"] = sum(p["unrealized_pnl"] for p in positions.values())


def _manual_flatten(state: dict) -> None:
    """즉시 전량 청산 → flat 정지. 자동 재진입은 진입 버튼 또는 다음 정기 리밸런스 시각까지 안 함."""
    if LIVE:
        from app.momentum_rotation_exec import account_equity_usdt, exec_client, flatten_all
        client = exec_client(EXCHANGE_MODE)
        owned = set(state.get("positions", {}))
        flatten_all(client, lambda m: log_event(state, m), owned=owned, tag="수동청산")
        equity = account_equity_usdt(client)
        state["equity_usdt"] = equity
    else:
        unrealized = sum(p.get("unrealized_pnl_usdt", 0.0) for p in state.get("positions", {}).values())
        state["cumulative_realized_pnl_usdt"] = state.get("cumulative_realized_pnl_usdt", 0.0) + unrealized
        equity = (START_CAPITAL_USDT + state["cumulative_realized_pnl_usdt"]
                  - state.get("cumulative_fee_usdt", 0.0))
        state["equity_usdt"] = equity

    state["positions"] = {}
    state["unrealized_pnl_usdt"] = 0.0
    state["manual_flat"] = True
    state["manual_flat_ts"] = now_iso()
    state["manual_flat_equity_usdt"] = equity
    log_event(state, f"[수동] 즉시 전량 청산 — equity {equity:,.2f} USDT. 자동 재진입 정지 "
                     f"(진입 버튼 또는 다음 리밸런스 시각까지 flat).")


def _manual_enter(state: dict, prices: dict[str, float]) -> None:
    """즉시 진입 — 현 시점 모멘텀 랭킹으로 롱숏 재구성. 리밸런스 타이머는 지금부터 다시 센다."""
    if LIVE:
        from app.momentum_rotation_exec import account_equity_usdt, exec_client
        if state.get("halted"):
            log_event(state, "[수동] 진입 거부 — halted 상태. MOMENTUM_ROTATION_RESET_HALT=true 로 재기동 필요.")
            return
        if PROFIT_LOCK and (state.get("profit_lock_active") or state.get("profit_lock_flatten_pending")):
            log_event(state, "[수동] 진입 거부 — PROFIT 보호 정지/청산 대기 상태.")
            return
        client = exec_client(EXCHANGE_MODE)
        equity = account_equity_usdt(client)
        hwm = max(float(state.get("hwm_usdt") or equity), equity)
        dd = 1.0 - equity / hwm if hwm > 0 else 0.0
        eff_lev = _effective_leverage(dd)
        if state.get("crash_flat"):
            state["crash_flatten_pending"] = False
        if not _rebalance_live(state, prices, eff_lev):
            log_event(state, "[수동] 진입 보류 — 리밸런스가 건너뛰어져 flat 상태 유지(다시 시도하세요)")
            return
    else:
        _rebalance(state, prices)

    state["manual_flat"] = False
    state["manual_flat_ts"] = None
    log_event(state, "[수동] 즉시 진입 실행 — 현 시점 랭킹으로 롱숏 재구성, 리밸런스 타이머 리셋.")


def handle_control(cmd: dict) -> bool:
    """제어 명령 1건 처리. 처리(성공/실패 확정)했으면 True, 나중에 재시도할 거면 False."""
    state = load_state()
    if state.get("consumed_control_nonce") == cmd["nonce"]:
        return True
    try:
        if cmd["cmd"] == "flatten":
            _manual_flatten(state)
        elif cmd["cmd"] == "enter":
            prices = _fetch_current_prices()
            if not prices:
                log_event(state, "[수동] 진입 명령 — 시세 조회 실패, 다음 틱에 재시도")
                save_state(state)
                return False
            _manual_enter(state, prices)
    except Exception as exc:  # noqa: BLE001
        import traceback
        log_event(state, f"[수동] 명령 '{cmd['cmd']}' 실행 실패: {exc}")
        traceback.print_exc()
        # 실패해도 nonce 소비 — 무한 재시도 방지. 사용자가 다시 누르면 새 nonce.
    state["consumed_control_nonce"] = cmd["nonce"]
    _stamp_rebalance_schedule(state)
    save_state(state)
    return True


def _stamp_rebalance_schedule(state: dict) -> None:
    """대시보드 카운트다운용 — 리밸런스 주기와 다음 예정 시각을 상태에 박아둔다.
    실제 리밸런스는 사이클(CHECK_INTERVAL_SECONDS)마다 due 여부를 재확인하므로,
    next_rebalance_ts 는 '이 시각 이후 첫 사이클에 리밸런스'라는 하한선이다."""
    state["rebalance_every_days"] = REBALANCE_EVERY_DAYS
    last_rb = state.get("last_rebalance_ts")
    state["next_rebalance_ts"] = (
        (datetime.fromisoformat(last_rb) + timedelta(days=REBALANCE_EVERY_DAYS)).isoformat()
        if last_rb else None
    )


CYCLE_FAILURE_ALERT_THRESHOLD = 3
_consecutive_cycle_failures = 0


def _note_cycle_failure(exc: BaseException) -> None:
    """LIVE 사이클 연속 실패 카운터. 실패 중엔 킬스위치(-35%) 등 보호 점검이 못 돌고 있다는 뜻이라
    임계치 이상이면 눈에 띄는 로그를 남긴다(레포에 별도 알림 채널 없음 — docker logs 로 확인)."""
    global _consecutive_cycle_failures
    _consecutive_cycle_failures += 1
    n = _consecutive_cycle_failures
    if n >= CYCLE_FAILURE_ALERT_THRESHOLD:
        print(f"[!!! 경고] LIVE 사이클 연속 {n}회 실패 — 킬스위치/보호 점검 불가 상태. 원인: {exc!r}", flush=True)
    else:
        print(f"[경고] LIVE 사이클 실패 {n}회 연속: {exc!r}", flush=True)


def _note_cycle_success() -> None:
    global _consecutive_cycle_failures
    if _consecutive_cycle_failures >= CYCLE_FAILURE_ALERT_THRESHOLD:
        print(f"[복구] LIVE 사이클 정상 복귀 (직전 연속 실패 {_consecutive_cycle_failures}회)", flush=True)
    _consecutive_cycle_failures = 0


def run_cycle() -> None:
    state = load_state()
    _stamp_rebalance_schedule(state)

    prices = _fetch_current_prices()
    if not prices and not LIVE:
        log_event(state, "시세 조회 전체 실패 — 이번 사이클 건너뜀")
        save_state(state)
        return
    if not prices:
        # LIVE: 킬스위치(-35%)/급락필터/손절성 점검은 시세가 아니라 계좌 equity·포지션만 필요하다.
        # 시세 실패로 이걸 통째로 건너뛰면 안 되므로 계속 진행 — 리밸런스는 시세 누락 가드가 막는다.
        log_event(state, "[LIVE] 시세 조회 전체 실패 — 킬스위치 점검은 계속, 리밸런스는 건너뜀")

    if LIVE:
        try:
            _run_cycle_live(state, prices)
        except Exception as exc:  # noqa: BLE001
            _note_cycle_failure(exc)
            raise
        _note_cycle_success()
        inception_equity = float(state.get("inception_equity_usdt") or state["equity_usdt"])
        total_pnl = state["equity_usdt"] - inception_equity
        gross_notional = sum(abs(p.get("notional_usdt", 0.0)) for p in state.get("positions", {}).values())
        # "세션수익" = "미실현손익". 무조건 같다(2026-09-24, 사용자 명시 요구) — 지금 안 판
        # 포지션들이 벌고/잃은 돈이라는 같은 뜻이니 숫자도 같아야 맞다. 예전엔 "마지막 리밸런스
        # 시점 equity"를 별도 기준선으로 잡아 거기서부터 지금까지 equity 변화량으로 세션수익을
        # 따로 계산했는데, 리밸런스 함수는 실제로 방향이 안 바뀐 기존 포지션은 건드리지 않고도
        # 그 기준선을 매번 "지금"으로 리셋해버려서(momentum_rotation_exec.apply_targets가 스킵한
        # 포지션도 포함) 세션수익이 "며칠간 쌓인 미실현손익"과 다른, 사실상 "리밸런스 이후 몇 분/
        # 몇 시간 동안의 가격 변동분"만 보여주는 별개 숫자가 됐었다 — 실제로 사용자가 겪은 계산
        # 실수. 지금 살아있는 포지션 전부의 미실현손익 합 하나로 통일해서 이 괴리 자체를 없앤다.
        unrealized_total = sum(p.get("unrealized_pnl_usdt", 0.0) for p in state.get("positions", {}).values())
        state["unrealized_pnl_usdt"] = unrealized_total
        equity_now = float(state.get("equity_usdt", 0.0))
        session_pnl = unrealized_total
        if state.get("session_start_ts") is None:
            state["session_start_ts"] = state.get("last_rebalance_ts") or state.get("inception_ts")
        # 대시보드용 브로커 스냅샷 — equity/positions 는 이미 바이낸스 API(totalMarginBalance,
        # fetch_positions) 값이라 자체 계산 아님. 여기서 한 블록으로 모아둔다.
        state["broker"] = {
            "queried_ts": now_iso(),
            "exchange": EXCHANGE_MODE,
            "equity_usdt": state.get("equity_usdt", 0.0),
            "inception_equity_usdt": inception_equity,
            "gross_notional_usdt": gross_notional,
            "return_pct": (total_pnl / inception_equity * 100) if inception_equity > 0 else 0.0,
            # 더 이상 세션수익 계산엔 안 쓰지만(위 주석 참고), 백엔드 레코드가 이 필드를 원시
            # double로 기대해서 빼면 역직렬화가 깨진다 — "이 보유 구간이 얼마 자본으로
            # 시작됐는지" 참고용 표시값으로만 남겨둔다.
            "session_start_equity_usdt": float(state.get("session_start_equity_usdt") or inception_equity),
            "session_start_ts": state.get("session_start_ts") or state.get("inception_ts"),
            "session_pnl_usdt": session_pnl,
            "session_return_pct": (session_pnl / equity_now * 100) if equity_now > 0 else 0.0,
            "unrealized_pnl_usdt": unrealized_total,
            "drawdown": state.get("drawdown", 0.0),
            "hwm_usdt": state.get("hwm_usdt", 0.0),
            "leverage": LEVERAGE,
            "halted": bool(state.get("halted", False)),
            "manual_flat": bool(state.get("manual_flat", False)),
            "manual_flat_ts": state.get("manual_flat_ts"),
            "positions": state.get("positions", {}),
        }
        state["mode"] = "live"
        if _should_sample_equity_history(state):
            state["equity_history"] = (state.get("equity_history", []) + [
                {"ts": now_iso(), "total_pnl_usdt": total_pnl, "equity_usdt": state["equity_usdt"],
                 "drawdown": state.get("drawdown", 0.0)}
            ])[-EQUITY_HISTORY_MAX_POINTS:]
            _rollup_daily_history(state, total_pnl)
        _stamp_rebalance_schedule(state)
        save_state(state)
        return

    if state.get("inception_ts") is None:
        state["inception_ts"] = now_iso()
        log_event(state, f"모멘텀 로테이션 백테스트(페이퍼) 루프 시작 — 가상자본 {START_CAPITAL_USDT:,.0f} USDT, "
                          f"{len(UNIVERSE)}종목, lookback {LOOKBACK_DAYS}일/리밸런스 {REBALANCE_EVERY_DAYS}일마다/상위·하위 {TOP_K}개")

    due = state.get("last_rebalance_ts") is None
    if not due:
        last = datetime.fromisoformat(state["last_rebalance_ts"])
        due = datetime.now(timezone.utc) - last >= timedelta(days=REBALANCE_EVERY_DAYS)

    if state.get("manual_flat"):
        if due:
            log_event(state, "수동 정지 중 정기 리밸런스 시각 도달 — 자동 재진입")
            state["manual_flat"] = False
            state["manual_flat_ts"] = None
        else:
            due = False  # flat 유지

    if state.get("manual_flat"):
        state["positions"] = {}
        state["unrealized_pnl_usdt"] = 0.0
        state["equity_usdt"] = (
            START_CAPITAL_USDT + state.get("cumulative_realized_pnl_usdt", 0.0)
            - state.get("cumulative_fee_usdt", 0.0)
        )
    elif due:
        _rebalance(state, prices)
    else:
        unrealized = _mark_to_market(state, prices)
        state["unrealized_pnl_usdt"] = unrealized
        state["equity_usdt"] = (
            START_CAPITAL_USDT + state.get("cumulative_realized_pnl_usdt", 0.0)
            - state.get("cumulative_fee_usdt", 0.0) + unrealized
        )

    total_pnl = state["equity_usdt"] - START_CAPITAL_USDT
    sample_now = _should_sample_equity_history(state)
    if sample_now:
        state["equity_history"] = (state.get("equity_history", []) + [
            {"ts": now_iso(), "total_pnl_usdt": total_pnl}
        ])[-EQUITY_HISTORY_MAX_POINTS:]
        _rollup_daily_history(state, total_pnl)

    # 종목별 차트용 — 이미 조회한 가격을 그대로 기록만 한다(추가 API 호출 없음). 지금 보유중인
    # 롱/숏 종목만 남긴다(47종목 전체를 다 남기면 상태파일이 불필요하게 커짐). equity_history와
    # 같은 표본 간격을 써서 서로 다른 기간 필터끼리 어긋나지 않게 맞춘다.
    if sample_now:
        symbol_history = state.setdefault("position_history", {})
        for symbol, pos in state["positions"].items():
            price = prices.get(symbol)
            if price is None:
                continue
            history = symbol_history.setdefault(symbol, [])
            history.append({"ts": now_iso(), "price": price, "unrealized_pnl_usdt": pos.get("unrealized_pnl_usdt", 0.0)})
            symbol_history[symbol] = history[-EQUITY_HISTORY_MAX_POINTS:]

    _stamp_rebalance_schedule(state)
    save_state(state)


def main() -> None:
    _mode = f"실거래:{EXCHANGE_MODE} {LEVERAGE}x" if LIVE else "페이퍼(백테스트)"
    print(f"모멘텀 로테이션 루프 시작 [{_mode}] — 룩백 {LOOKBACK_DAYS}일/리밸런스 {REBALANCE_EVERY_DAYS}일/"
          f"상하위 {TOP_K}개, 모니터링 {CHECK_INTERVAL_SECONDS}초/제어폴링 {CONTROL_POLL_SECONDS}초", flush=True)
    last_full = 0.0
    while True:
        try:
            # 1) 빠른 폴링: 수동 제어 명령(즉시 매도/진입)
            cmd = read_command(BOT_ID)
            if cmd:
                state = load_state()
                already = state.get("consumed_control_nonce") == cmd["nonce"]
                del state
                if not already and handle_control(cmd):
                    last_full = 0.0  # 즉시 전체 사이클 1회 → 대시보드 스냅샷 갱신

            # 2) 주기 실행: 무거운 모니터링/리밸런스 사이클
            if time.monotonic() - last_full >= CHECK_INTERVAL_SECONDS:
                run_with_timeout(
                    run_cycle, CYCLE_TIMEOUT_SECONDS,
                    on_timeout=lambda: print(
                        f"사이클이 {CYCLE_TIMEOUT_SECONDS}초 넘게 안 끝나 hang으로 보고 포기, 다음 사이클로 넘어감", flush=True,
                    ),
                )
                last_full = time.monotonic()
        except Exception:
            import traceback
            print("루프 사이클 중 오류 발생:", flush=True)
            traceback.print_exc()
        time.sleep(CONTROL_POLL_SECONDS)


if __name__ == "__main__":
    main()
