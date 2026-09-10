"""코인간 상대모멘텀 로테이션(선물 롱숏) 라이브 루프 — 백테스트에서 검증된 설정
(lookback 14일 / 3일마다 리밸런스 / 상위·하위 8개, 연환산 29.16%, MDD 18.6%)을 그대로 사용.

실주문 없음(백테스트/페이퍼 모드) — 바이낸스 공개 시세 API만으로 가상 포지션·손익을
추적한다. API 키 불필요, 실계좌 리스크 전혀 없음. 나중에 실거래로 전환하려면 이 루프의
판단 로직은 그대로 두고 주문 실행부만 추가하면 된다(kr/us_swing_loop과 동일 원칙).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import ccxt
import pandas as pd

from app.crypto_tick_state import load_state as load_tick_state
from app.futures_data import fetch_perp_ohlcv
from app.momentum_state import load_state, log_event, now_iso, save_state
from app.trading_control import read_command
from app.watchdog import run_with_timeout

BOT_ID = "momentum-rotation"

# crypto_tick_stream.py가 이 시간 안에 갱신한 선물 체결틱이 있으면 REST fetch_ticker 대신 씀.
_TICK_STALE_SECONDS = 90


def _tick_price(tick_state: dict, base: str) -> float | None:
    points = tick_state.get("perp_ticks", {}).get(base)
    if not points:
        return None
    last = points[-1]
    try:
        ts = datetime.fromisoformat(last["ts"])
    except (KeyError, ValueError):
        return None
    if (datetime.now(timezone.utc) - ts).total_seconds() > _TICK_STALE_SECONDS:
        return None
    try:
        return float(last["price"])
    except (KeyError, ValueError, TypeError):
        return None

UNIVERSE = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "JUP", "ARB", "FIL", "VET",
    "CAKE", "TON", "MKR", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]

LOOKBACK_DAYS = int(os.environ.get("MOMENTUM_ROTATION_LOOKBACK_DAYS", "14"))
REBALANCE_EVERY_DAYS = int(os.environ.get("MOMENTUM_ROTATION_REBALANCE_DAYS", "3"))
TOP_K = int(os.environ.get("MOMENTUM_ROTATION_TOP_K", "8"))
COMMISSION_PCT = 0.04  # 편도, 리밸런스 회전분에만 적용(백테스트와 동일 가정)
START_CAPITAL_USDT = float(os.environ.get("MOMENTUM_ROTATION_START_CAPITAL_USDT", "10000"))
CHECK_INTERVAL_SECONDS = int(os.environ.get("MOMENTUM_ROTATION_CHECK_INTERVAL_SECONDS", "120"))
CYCLE_TIMEOUT_SECONDS = int(os.environ.get("MOMENTUM_ROTATION_CYCLE_TIMEOUT_SECONDS", "300"))
# 수동 제어(즉시 매도/진입) 명령 폴링 주기 — 무거운 사이클과 분리해 거의 틱단위로 반응한다.
CONTROL_POLL_SECONDS = int(os.environ.get("MOMENTUM_ROTATION_CONTROL_POLL_SECONDS", "5"))
SINCE_DAYS_FOR_MOMENTUM = LOOKBACK_DAYS + 10

# --- 실거래 설정 ---
LIVE = os.environ.get("MOMENTUM_ROTATION_LIVE", "false").lower() == "true"
EXCHANGE_MODE = os.environ.get("MOMENTUM_ROTATION_EXCHANGE", "testnet")  # testnet | mainnet
LEVERAGE = int(os.environ.get("MOMENTUM_ROTATION_LEVERAGE", "1"))
# 안전 상한: 선물지갑에 이보다 많이 들어있어도 이 금액까지만 굴린다(0 = 무제한).
MAX_DEPLOY_USDT = float(os.environ.get("MOMENTUM_ROTATION_MAX_DEPLOY_USDT", "0"))
DELEVER_DD = float(os.environ.get("MOMENTUM_ROTATION_DELEVER_DD", "0.20"))
KILL_DD = float(os.environ.get("MOMENTUM_ROTATION_KILL_DD", "0.35"))
RESET_HALT = os.environ.get("MOMENTUM_ROTATION_RESET_HALT", "false").lower() == "true"


def _perp_symbol(base: str) -> str:
    return f"{base}/USDT:USDT"


def _fetch_current_prices() -> dict[str, float]:
    try:
        tick_state = load_tick_state()
    except Exception:  # noqa: BLE001
        tick_state = {}

    prices = {}
    missing = []
    for base in UNIVERSE:
        tick = _tick_price(tick_state, base)
        if tick is not None:
            prices[base] = tick
        else:
            missing.append(base)

    if not missing:
        return prices

    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    want = {_perp_symbol(b): b for b in missing}
    try:
        # 47종목을 개별 fetch_ticker 로 부르면 IP 밴(-1003) 위험 — 한 번에 받는다.
        tickers = exchange.fetch_tickers(list(want))
        for symbol, base in want.items():
            last = (tickers.get(symbol) or {}).get("last")
            if last:
                prices[base] = last
    except Exception as exc:  # noqa: BLE001
        print(f"  일괄 시세조회 실패, 개별 폴백 ({exc})", flush=True)
        for symbol, base in want.items():
            try:
                prices[base] = exchange.fetch_ticker(symbol)["last"]
            except Exception as exc2:  # noqa: BLE001
                print(f"  {base}: 시세조회 실패 ({exc2})", flush=True)
    return prices


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


def _target_sides() -> dict[str, str] | None:
    """모멘텀 랭킹 → {base: 'long'|'short'}. 데이터 부족이면 None."""
    momentum = _fetch_momentum_ranking()
    if len(momentum) < TOP_K * 2:
        return None
    ranked = momentum.sort_values(ascending=False)
    targets = {b: "long" for b in ranked.index[:TOP_K]}
    targets.update({b: "short" for b in ranked.index[-TOP_K:]})
    return targets


def _rebalance_live(state: dict, prices: dict[str, float], eff_lev: int) -> None:
    from app.momentum_rotation_exec import account_equity_usdt, apply_targets, exec_client, sync_positions

    client = exec_client(EXCHANGE_MODE)
    equity = account_equity_usdt(client)
    deploy = min(equity, MAX_DEPLOY_USDT) if MAX_DEPLOY_USDT > 0 else equity
    targets = _target_sides()
    if targets is None:
        log_event(state, "모멘텀 데이터 부족 — 이번 리밸런스 건너뜀")
        return
    targets = {b: s for b, s in targets.items() if prices.get(b)}

    # gross = deploy * eff_lev, 롱/숏 반반, 포지션당 균등
    notional_per_pos = deploy * eff_lev / 2 / TOP_K
    log_event(state, f"[LIVE:{EXCHANGE_MODE}] 리밸런스 시작 — equity {equity:.2f} / 운용 {deploy:.2f} USDT, "
                     f"배율 {eff_lev}x, 포지션당 명목 {notional_per_pos:.2f} USDT")

    owned = set(state.get("positions", {}))
    result = apply_targets(client, prices, targets, notional_per_pos, eff_lev,
                           lambda m: log_event(state, m), owned=owned)

    all_positions = sync_positions(client)
    managed = set(targets) | owned
    positions = {b: p for b, p in all_positions.items() if b in managed}
    state["positions"] = {
        b: {"side": p["side"], "entry_price": p["entry_price"],
            "notional_usdt": p["notional"], "unrealized_pnl_usdt": p["unrealized_pnl"]}
        for b, p in positions.items()
    }
    state["last_rebalance_ts"] = now_iso()
    state["equity_usdt"] = equity
    log_event(state, f"[LIVE:{EXCHANGE_MODE}] 리밸런스 완료 — 진입 {result['opened']}, 청산 {result['closed']}, "
                     f"스킵 {result['skipped']}, 오류 {result['errors']} / 실보유 {len(positions)}종목")


def _run_cycle_live(state: dict, prices: dict[str, float]) -> None:
    from app.momentum_rotation_exec import account_equity_usdt, exec_client, flatten_all, sync_positions

    client = exec_client(EXCHANGE_MODE)
    equity = account_equity_usdt(client)

    if state.get("inception_ts") is None:
        state["inception_ts"] = now_iso()
        state["hwm_usdt"] = equity
        state["inception_equity_usdt"] = equity
        log_event(state, f"[LIVE:{EXCHANGE_MODE}] 실거래 루프 시작 — equity {equity:.2f} USDT, 기준배율 {LEVERAGE}x")

    if RESET_HALT and state.get("halted"):
        state["halted"] = False
        state["hwm_usdt"] = equity
        log_event(state, "[LIVE] halt 수동 해제 — hwm 재설정")

    hwm = max(float(state.get("hwm_usdt") or equity), equity)
    state["hwm_usdt"] = hwm
    dd = 1.0 - equity / hwm if hwm > 0 else 0.0
    state["drawdown"] = dd
    state["equity_usdt"] = equity

    if state.get("halted"):
        log_event(state, f"[LIVE] halt 상태 — 거래 중단 중 (dd {dd*100:.1f}%). "
                         f"해제하려면 MOMENTUM_ROTATION_RESET_HALT=true 로 재기동")
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
        state["positions"] = {}
        return

    eff_lev = 1 if (dd >= DELEVER_DD and LEVERAGE > 1) else LEVERAGE
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
            b: {"side": p["side"], "entry_price": p["entry_price"],
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
        flatten_all(client, lambda m: log_event(state, m), owned=owned)
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
        client = exec_client(EXCHANGE_MODE)
        equity = account_equity_usdt(client)
        hwm = max(float(state.get("hwm_usdt") or equity), equity)
        dd = 1.0 - equity / hwm if hwm > 0 else 0.0
        eff_lev = 1 if (dd >= DELEVER_DD and LEVERAGE > 1) else LEVERAGE
        _rebalance_live(state, prices, eff_lev)
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


def run_cycle() -> None:
    state = load_state()
    _stamp_rebalance_schedule(state)

    prices = _fetch_current_prices()
    if not prices:
        log_event(state, "시세 조회 전체 실패 — 이번 사이클 건너뜀")
        save_state(state)
        return

    if LIVE:
        _run_cycle_live(state, prices)
        inception_equity = float(state.get("inception_equity_usdt") or state["equity_usdt"])
        total_pnl = state["equity_usdt"] - inception_equity
        gross_notional = sum(abs(p.get("notional_usdt", 0.0)) for p in state.get("positions", {}).values())
        # 대시보드용 브로커 스냅샷 — equity/positions 는 이미 바이낸스 API(totalMarginBalance,
        # fetch_positions) 값이라 자체 계산 아님. 여기서 한 블록으로 모아둔다.
        state["broker"] = {
            "queried_ts": now_iso(),
            "exchange": EXCHANGE_MODE,
            "equity_usdt": state.get("equity_usdt", 0.0),
            "inception_equity_usdt": inception_equity,
            "gross_notional_usdt": gross_notional,
            "return_pct": (total_pnl / inception_equity * 100) if inception_equity > 0 else 0.0,
            "unrealized_pnl_usdt": state.get("unrealized_pnl_usdt", 0.0),
            "drawdown": state.get("drawdown", 0.0),
            "hwm_usdt": state.get("hwm_usdt", 0.0),
            "leverage": LEVERAGE,
            "halted": bool(state.get("halted", False)),
            "manual_flat": bool(state.get("manual_flat", False)),
            "manual_flat_ts": state.get("manual_flat_ts"),
            "positions": state.get("positions", {}),
        }
        state["mode"] = "live"
        state["equity_history"] = (state.get("equity_history", []) + [
            {"ts": now_iso(), "total_pnl_usdt": total_pnl, "equity_usdt": state["equity_usdt"],
             "drawdown": state.get("drawdown", 0.0)}
        ])[-2000:]
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
    state["equity_history"] = (state.get("equity_history", []) + [
        {"ts": now_iso(), "total_pnl_usdt": total_pnl}
    ])[-2000:]

    # 종목별 차트용 — 이미 조회한 가격을 그대로 기록만 한다(추가 API 호출 없음). 지금 보유중인
    # 롱/숏 종목만 남긴다(47종목 전체를 다 남기면 상태파일이 불필요하게 커짐).
    symbol_history = state.setdefault("position_history", {})
    for symbol, pos in state["positions"].items():
        price = prices.get(symbol)
        if price is None:
            continue
        history = symbol_history.setdefault(symbol, [])
        history.append({"ts": now_iso(), "price": price, "unrealized_pnl_usdt": pos.get("unrealized_pnl_usdt", 0.0)})
        symbol_history[symbol] = history[-2000:]

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
