"""국장/미장 top-N 상대모멘텀 로테이션 페이퍼봇 (KIS 모의투자).

코인 momentum_rotation_loop 과 같은 논리: 매 리밸런스에 최근 L일 수익률 상위 K종목
등가중 보유, 나머지 처분. 개인 공매도가 막혀 있으니 롱온리. (옵션) 등가중 유니버스
지수가 자기 200일선 아래면 전액 현금.

KIS 모의는 장마감 직후 주문을 거부하므로(40580000 실측), kr_swing 과 같은 2단계 방식:
  1) 장마감 후 하루 1회: 목표 바스켓 계산 → pending_sells/pending_buys 큐 적재 (plan)
  2) 다음 장중: 큐를 시장가(국내)/마켓터블리밋(해외)로 소비 (consume)

일봉 시세는 app/kis_ohlcv_cache.py 로컬 CSV 캐시(볼륨) 재사용 — 매 리밸런스마다 마지막
봉 5일치만 증분 조회. 실제 보유/현금은 KIS 잔고조회가 진실 소스.

env:
  ROTATION_MARKET      KR | US
  ROTATION_LOOKBACK    모멘텀 룩백일 (KR 기본 20, US 기본 120)
  ROTATION_REBAL_DAYS  리밸런스 간격일 (기본 10 / US 20)
  ROTATION_TOP_K       보유 종목 수 (기본 8)
  ROTATION_REGIME      none | ew_sma200 (기본 ew_sma200)
  ROTATION_BUDGET      운용 예산 (KR KRW, US USD). 미지정 시 watchlist 기본예산.
  ROTATION_STATE_PATH  상태파일 경로
"""
from __future__ import annotations

import datetime as dt
import os
import time
from zoneinfo import ZoneInfo

import pandas as pd

from app.kis_auth import issue_token
from app.kis_ohlcv_cache import cached_ohlcv
from app.stock_rotation_state import load_state, log_event, now_iso, save_state
from app.trading_control import read_command

MARKET = os.environ.get("ROTATION_MARKET", "KR").upper()
BOT_ID = "kr-rotation" if MARKET == "KR" else "us-rotation"
TOP_K = int(os.environ.get("ROTATION_TOP_K", "8"))
REGIME = os.environ.get("ROTATION_REGIME", "ew_sma200")
LOOP_SLEEP_SECONDS = int(os.environ.get("ROTATION_LOOP_SLEEP_SECONDS", "10"))
TOKEN_TTL_SECONDS = 12 * 3600
HISTORY_SINCE = "2018-01-01"

if MARKET == "KR":
    LOOKBACK = int(os.environ.get("ROTATION_LOOKBACK", "20"))
    REBAL_DAYS = int(os.environ.get("ROTATION_REBAL_DAYS", "10"))
    TZ = ZoneInfo("Asia/Seoul")
    ORDER_WINDOW = (dt.time(9, 5), dt.time(15, 15))
    PLAN_AFTER = dt.time(15, 40)
else:
    LOOKBACK = int(os.environ.get("ROTATION_LOOKBACK", "120"))
    REBAL_DAYS = int(os.environ.get("ROTATION_REBAL_DAYS", "20"))
    TZ = ZoneInfo("America/New_York")
    ORDER_WINDOW = (dt.time(9, 40), dt.time(15, 50))
    PLAN_AFTER = dt.time(16, 5)


# ----- 시장별 어댑터 -------------------------------------------------------------

def _universe() -> list[tuple[str, str, str]]:
    """[(symbol, name, excd)] — 국내는 excd="" ."""
    if MARKET == "KR":
        from app.ema_cross_watchlist import STOCK_UNIVERSE
        return [(code, name, "") for code, name in STOCK_UNIVERSE]
    from app.us_swing_search import STOCK_UNIVERSE
    return [(sym, name, excd) for sym, excd, name in STOCK_UNIVERSE]


def _default_budget() -> float:
    if MARKET == "KR":
        from app.kr_watchlist import CAPITAL_BUDGET_KRW
        return CAPITAL_BUDGET_KRW
    from app.us_watchlist import CAPITAL_BUDGET_USD
    return CAPITAL_BUDGET_USD


BUDGET = float(os.environ.get("ROTATION_BUDGET", "0")) or _default_budget()
_EXCD = {s: e for s, _, e in _universe()}
_NAMES = {s: n for s, n, _ in _universe()}


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def broker_snapshot(token: str) -> dict:
    """KIS 잔고 API 한 번으로 실보유/평가/현금을 그대로 가져온다(자체 계산 아님).

    반환:
      positions   {symbol: {qty, price, eval_amt, purchase_amt, pnl, pnl_pct}}  (통화: KR=KRW, US=USD)
      held        {symbol: qty}
      unrealized  평가손익 합계 (API 제공값 합)
      pos_eval    평가금액 합
      account_cash_krw / account_total_krw   계좌 전체(국장/미장 공용) — KIS 국내잔고 API 제공값
      queried_ts
    """
    positions: dict[str, dict] = {}
    account_cash_krw = 0.0
    account_total_krw = 0.0

    if MARKET == "KR":
        from app.kis_order import inquire_balance
        from app.kr_watchlist import ACNT_PRDT_CD, CANO
        body = inquire_balance(token, CANO, ACNT_PRDT_CD)
        if body.get("rt_cd") != "0":
            raise RuntimeError(f"잔고조회 실패: {body.get('msg_cd')} {body.get('msg1')}")
        for r in body.get("output1", []):
            qty = int(_f(r.get("hldg_qty")))
            if qty <= 0:
                continue
            positions[r["pdno"]] = {
                "qty": qty, "price": _f(r.get("prpr")),
                "eval_amt": _f(r.get("evlu_amt")), "purchase_amt": _f(r.get("pchs_amt")),
                "pnl": _f(r.get("evlu_pfls_amt")), "pnl_pct": _f(r.get("evlu_pfls_rt")),
            }
        o2 = (body.get("output2") or [{}])[0]
        account_cash_krw = _f(o2.get("dnca_tot_amt"))
        account_total_krw = _f(o2.get("tot_evlu_amt"))
    else:
        from app.kis_order import inquire_balance as inquire_balance_krw
        from app.kis_overseas_order import inquire_balance
        from app.us_watchlist import ACNT_PRDT_CD, CANO
        for excd in ("NASD", "NYSE"):
            body = inquire_balance(token, CANO, ACNT_PRDT_CD, excd)
            if body.get("rt_cd") != "0":
                raise RuntimeError(f"해외잔고조회 실패({excd}): {body.get('msg_cd')} {body.get('msg1')}")
            for r in body.get("output1", []):
                qty = int(_f(r.get("ovrs_cblc_qty")))
                if qty <= 0:
                    continue
                positions[r["ovrs_pdno"]] = {
                    "qty": qty, "price": _f(r.get("now_pric2")),
                    "eval_amt": _f(r.get("ovrs_stck_evlu_amt")), "purchase_amt": _f(r.get("frcr_pchs_amt1")),
                    "pnl": _f(r.get("frcr_evlu_pfls_amt")), "pnl_pct": _f(r.get("evlu_pfls_rt")),
                }
        try:
            kb = inquire_balance_krw(token, CANO, ACNT_PRDT_CD)
            ko2 = (kb.get("output2") or [{}])[0]
            account_cash_krw = _f(ko2.get("dnca_tot_amt"))
            account_total_krw = _f(ko2.get("tot_evlu_amt"))
        except Exception:  # noqa: BLE001
            pass

    # 이 전략 유니버스 종목만
    positions = {s: p for s, p in positions.items() if s in _NAMES}
    pos_eval = sum(p["eval_amt"] for p in positions.values())
    unrealized = sum(p["pnl"] for p in positions.values())
    return {
        "positions": positions,
        "held": {s: p["qty"] for s, p in positions.items()},
        "unrealized": unrealized,
        "pos_eval": pos_eval,
        "account_cash_krw": account_cash_krw,
        "account_total_krw": account_total_krw,
        "queried_ts": now_iso(),
    }


def _held(token: str) -> dict[str, int]:
    return broker_snapshot(token)["held"]


def _price(token: str, symbol: str) -> float:
    if MARKET == "KR":
        from app.kis_order import inquire_price
        return inquire_price(token, symbol)
    from app.kis_overseas_order import inquire_price
    return inquire_price(token, symbol, _EXCD[symbol])


def _cap_qty(token: str, symbol: str, qty: int, price: float) -> int:
    """해외는 모의계좌 주문가능금액 심사가 근사예산과 어긋나 거부되므로 실제 한도로 클램프."""
    if MARKET == "KR" or qty < 1:
        return qty
    from app.kis_overseas_order import MARKETABLE_LIMIT_BUFFER, inquire_psamount
    from app.us_watchlist import ACNT_PRDT_CD, CANO
    limit = round(price * (1 + MARKETABLE_LIMIT_BUFFER), 2)
    try:
        body = inquire_psamount(token, CANO, ACNT_PRDT_CD, _EXCD[symbol], symbol, limit)
        allowed = int(float(body.get("output", {}).get("max_ord_psbl_qty", "0")))
    except Exception:  # noqa: BLE001
        return qty
    return max(0, min(qty, allowed))


def _buy(token: str, symbol: str, qty: int, price: float) -> dict:
    if MARKET == "KR":
        from app.kis_order import place_order
        from app.kr_watchlist import ACNT_PRDT_CD, CANO
        return place_order(token, CANO, ACNT_PRDT_CD, symbol, "buy", qty)
    from app.kis_overseas_order import MARKETABLE_LIMIT_BUFFER, place_order
    from app.us_watchlist import ACNT_PRDT_CD, CANO
    limit = round(price * (1 + MARKETABLE_LIMIT_BUFFER), 2)
    return place_order(token, CANO, ACNT_PRDT_CD, symbol, _EXCD[symbol], "buy", qty, limit)


def _sell(token: str, symbol: str, qty: int, price: float) -> dict:
    if MARKET == "KR":
        from app.kis_order import place_order
        from app.kr_watchlist import ACNT_PRDT_CD, CANO
        return place_order(token, CANO, ACNT_PRDT_CD, symbol, "sell", qty)
    from app.kis_overseas_order import MARKETABLE_LIMIT_BUFFER, place_order
    from app.us_watchlist import ACNT_PRDT_CD, CANO
    limit = round(price * (1 - MARKETABLE_LIMIT_BUFFER), 2)
    return place_order(token, CANO, ACNT_PRDT_CD, symbol, _EXCD[symbol], "sell", qty, limit)


# ----- 전략 --------------------------------------------------------------------

def _load_closes(token: str) -> pd.DataFrame:
    series = {}
    for symbol, _, excd in _universe():
        try:
            df = cached_ohlcv("KR" if MARKET == "KR" else "US", symbol, token,
                              HISTORY_SINCE, excd=excd or "NAS")
        except Exception as exc:  # noqa: BLE001
            print(f"  {symbol} 캐시조회 실패: {exc}", flush=True)
            continue
        if not df.empty:
            series[symbol] = df["Close"]
    closes = pd.DataFrame(series).sort_index()
    return closes[closes.notna().mean(axis=1) >= 0.6]


def _target_basket(closes: pd.DataFrame) -> tuple[list[str], bool]:
    """반환: (상위 K 종목, 레짐이 전액현금인지)."""
    if len(closes) < max(LOOKBACK + 1, 200):
        return [], False
    rets = closes.pct_change()
    ew_index = (1 + rets.mean(axis=1).fillna(0.0)).cumprod()
    cash = REGIME == "ew_sma200" and ew_index.iloc[-1] < ew_index.rolling(200).mean().iloc[-1]
    if cash:
        return [], True
    mom = closes.iloc[-1] / closes.iloc[-1 - LOOKBACK] - 1
    mom = mom.dropna()
    mom = mom[closes.iloc[-1].notna()]
    if len(mom) < TOP_K:
        return [], False
    return list(mom.sort_values(ascending=False).index[:TOP_K]), False


def _market_today() -> dt.date:
    return dt.datetime.now(TZ).date()


def plan_rebalance(token: str, state: dict, force: bool = False) -> None:
    today = _market_today().isoformat()
    if not force and state.get("last_plan_date") == today:
        return

    last_rb = state.get("last_rebalance_date")
    if not force and last_rb:
        gap = (_market_today() - dt.date.fromisoformat(last_rb)).days
        if gap < REBAL_DAYS:
            state["last_plan_date"] = today
            save_state(state)
            return

    log_event(state, f"[{MARKET}] 리밸런스 계획{' (수동)' if force else ''} — 룩백 {LOOKBACK}일, top {TOP_K}, 레짐 {REGIME}")
    closes = _load_closes(token)
    if closes.empty:
        log_event(state, f"[{MARKET}] 시세 캐시 비어 계획 보류")
        return
    target, regime_cash = _target_basket(closes)
    if not target and not regime_cash:
        log_event(state, f"[{MARKET}] 데이터 부족 — 계획 보류 ({closes.shape})")
        return

    held = set(_held(token))
    tgt = set(target)
    state["pending_sells"] = sorted(held - tgt)
    state["pending_buys"] = [s for s in target if s not in held]
    state["target_basket"] = target
    state["regime_cash"] = regime_cash
    state["last_plan_date"] = today
    state["symbol_names"] = _NAMES
    # 새 계획이 섰으면 수동 정지 해제 — 큐 소비하며 재진입한다.
    state["manual_flat"] = False
    state["manual_flat_pending"] = False
    state["manual_flat_ts"] = None
    log_event(state, f"[{MARKET}] 계획 완료 — 목표 {target or '전액현금'} / "
                     f"매도 {state['pending_sells']} / 매수 {state['pending_buys']}")
    save_state(state)


def _record_equity(token: str, state: dict, snap: dict | None = None) -> None:
    """잔고 API 스냅샷을 그대로 state["broker"]에 박고, 평가·손익도 API 제공값을 쓴다."""
    if snap is None:
        snap = broker_snapshot(token)

    unrealized = snap["unrealized"]              # API 평가손익 합
    realized = state.get("realized_pnl", 0.0)    # 체결 원장(브로커가 전략별 태깅 불가)
    total = realized + unrealized
    strategy_equity = BUDGET + total             # 배정예산 기준 전략 equity
    deployed = snap["pos_eval"]                  # API 평가금액(현재금액) 합
    entry_value = sum(p["purchase_amt"] for p in snap["positions"].values())  # 매입금액(진입금액) 합

    state["broker"] = {
        "queried_ts": snap["queried_ts"],
        "positions": snap["positions"],
        "positions_eval": deployed,
        "positions_entry": entry_value,
        "positions_unrealized_pnl": unrealized,
        "account_cash_krw": snap["account_cash_krw"],
        "account_total_krw": snap["account_total_krw"],
    }
    state["broker"]["manual_flat"] = bool(state.get("manual_flat", False))
    state["broker"]["manual_flat_pending"] = bool(state.get("manual_flat_pending", False))
    state["broker"]["manual_flat_ts"] = state.get("manual_flat_ts")
    state["held_symbols"] = sorted(snap["held"])
    state["unrealized_pnl"] = unrealized
    state["equity"] = strategy_equity
    state["budget"] = BUDGET
    state["entry_value"] = entry_value
    state["deployed_value"] = deployed
    state["return_pct"] = (total / BUDGET * 100) if BUDGET > 0 else 0.0

    hist = state.setdefault("position_history", {})
    for symbol, p in snap["positions"].items():
        hist.setdefault(symbol, []).append({"ts": now_iso(), "price": p["price"], "unrealized_pnl": p["pnl"]})
        hist[symbol] = hist[symbol][-20000:]
    state["equity_history"] = (state.get("equity_history", []) + [
        {"ts": now_iso(), "total_pnl": total, "equity": strategy_equity, "deployed": deployed}
    ])[-20000:]


def consume_queue(token: str, state: dict) -> None:
    did_something = False
    held = _held(token)

    for symbol in list(state.get("pending_sells", [])):
        if symbol not in held:
            state["pending_sells"].remove(symbol)
            continue
        try:
            price = _price(token, symbol)
        except Exception as exc:  # noqa: BLE001
            log_event(state, f"[{MARKET}] {symbol} 현재가 실패: {exc}")
            continue
        qty = held[symbol]
        res = _sell(token, symbol, qty, price)
        if res.get("rt_cd") == "0":
            cost = state["entry_cost"].pop(symbol, qty * price)
            realized = qty * price - cost
            state["realized_pnl"] = state.get("realized_pnl", 0.0) + realized
            log_event(state, f"[{MARKET} 매도] {symbol} {qty}주 @약{price:,.2f} 실현 {realized:+,.2f} "
                             f"(누적 {state['realized_pnl']:+,.2f})")
            state["pending_sells"].remove(symbol)
            did_something = True
        else:
            log_event(state, f"[{MARKET} 매도실패] {symbol}: {res.get('msg_cd')} {res.get('msg1')}")

    if state.get("pending_sells"):
        save_state(state)
        return  # 매도 체결 반영 후 다음 사이클에 매수

    held = _held(token)
    n_target = max(len(state.get("target_basket", [])), 1)
    per_name = BUDGET / n_target
    for symbol in list(state.get("pending_buys", [])):
        if symbol in held:
            state["pending_buys"].remove(symbol)
            continue
        try:
            price = _price(token, symbol)
        except Exception as exc:  # noqa: BLE001
            log_event(state, f"[{MARKET}] {symbol} 현재가 실패: {exc}")
            continue
        qty = _cap_qty(token, symbol, int(per_name // price), price)
        if qty < 1:
            log_event(state, f"[{MARKET} 매수스킵] {symbol}: 배정 {per_name:,.0f} / 1주 {price:,.2f} — 주문가능수량 0")
            state["pending_buys"].remove(symbol)
            continue
        res = _buy(token, symbol, qty, price)
        if res.get("rt_cd") == "0":
            state["entry_cost"][symbol] = qty * price
            log_event(state, f"[{MARKET} 매수] {symbol} {qty}주 @약{price:,.2f} (배정 {per_name:,.0f})")
            state["pending_buys"].remove(symbol)
            did_something = True
        else:
            log_event(state, f"[{MARKET} 매수실패] {symbol}: {res.get('msg_cd')} {res.get('msg1')}")
            state["pending_buys"].remove(symbol)

    snap = broker_snapshot(token)
    if not state.get("pending_sells") and not state.get("pending_buys"):
        if state.get("last_plan_date") and state.get("last_rebalance_date") != state["last_plan_date"]:
            state["last_rebalance_date"] = state["last_plan_date"]
            log_event(state, f"[{MARKET}] 리밸런스 완료 — 보유 {sorted(snap['held'])}")

    _record_equity(token, state, snap)
    save_state(state)
    _ = did_something


def _in_order_window(now: dt.datetime) -> bool:
    return now.weekday() < 5 and ORDER_WINDOW[0] <= now.time() <= ORDER_WINDOW[1]


def _flatten_now(token: str, state: dict) -> None:
    """보유 전량을 매도 큐에 넣고 즉시 소비한다(장중 전제)."""
    held = _held(token)
    state["pending_buys"] = []
    state["target_basket"] = []
    if not held:
        state["pending_sells"] = []
        return
    state["pending_sells"] = sorted(held)
    log_event(state, f"[{MARKET}] 수동 즉시 매도 — {sorted(held)} 처분")
    consume_queue(token, state)


def _handle_control(token: str, state: dict, cmd: dict, now: dt.datetime) -> None:
    if state.get("consumed_control_nonce") == cmd["nonce"]:
        return
    try:
        if cmd["cmd"] == "flatten":
            state["manual_flat"] = True
            state["manual_flat_ts"] = now_iso()
            if _in_order_window(now):
                _flatten_now(token, state)
                state["manual_flat_pending"] = bool(state.get("pending_sells"))
            else:
                state["manual_flat_pending"] = True
                log_event(state, f"[{MARKET}] 수동 청산 명령 — 장 마감 중, 다음 개장 시 실행 대기")
        elif cmd["cmd"] == "enter":
            plan_rebalance(token, state, force=True)  # state 를 제자리 변경
            state["manual_flat"] = False
            state["manual_flat_pending"] = False
            state["manual_flat_ts"] = None
            log_event(state, f"[{MARKET}] 수동 즉시 진입 — 현 시점 랭킹으로 목표 재계산, 매수 큐 적재 "
                             f"(장중이면 이번 사이클, 장외면 개장 시 체결)")
    except Exception as exc:  # noqa: BLE001
        log_event(state, f"[{MARKET}] 수동 명령 '{cmd['cmd']}' 실패: {exc}")
    state["consumed_control_nonce"] = cmd["nonce"]
    save_state(state)


def main() -> None:
    state = load_state()
    log_event(state, f"[{MARKET}] 로테이션 페이퍼봇 시작 — 룩백 {LOOKBACK}/리밸 {REBAL_DAYS}일/"
                     f"top {TOP_K}/레짐 {REGIME}, 예산 {BUDGET:,.0f}")
    save_state(state)

    token = issue_token()
    token_at = time.monotonic()
    last_snapshot = 0.0

    while True:
        try:
            if time.monotonic() - token_at > TOKEN_TTL_SECONDS:
                token = issue_token()
                token_at = time.monotonic()

            now = dt.datetime.now(TZ)

            # 수동 제어 명령 (즉시 매도 / 즉시 진입)
            cmd = read_command(BOT_ID)
            if cmd:
                state = load_state()
                if state.get("consumed_control_nonce") != cmd["nonce"]:
                    _handle_control(token, state, cmd, now)

            # 장 마감 중 접수한 청산 명령 — 개장하면 실행
            state = load_state()
            if state.get("manual_flat_pending") and _in_order_window(now):
                _flatten_now(token, state)
                if not state.get("pending_sells"):
                    state["manual_flat_pending"] = False
                _record_equity(token, state)
                save_state(state)
                last_snapshot = time.monotonic()

            if now.weekday() < 5:
                if ORDER_WINDOW[0] <= now.time() <= ORDER_WINDOW[1]:
                    state = load_state()
                    if state.get("pending_sells") or state.get("pending_buys"):
                        consume_queue(token, state)
                    else:
                        _record_equity(token, state)
                        save_state(state)
                    last_snapshot = time.monotonic()
                elif now.time() >= PLAN_AFTER:
                    state = load_state()
                    plan_rebalance(token, state)
                    state = load_state()
                    _record_equity(token, state)
                    save_state(state)
                    last_snapshot = time.monotonic()

            # 장 시간 밖이어도 15분마다 잔고 스냅샷은 갱신(대시보드가 최신 잔고를 보게).
            if time.monotonic() - last_snapshot > 900:
                state = load_state()
                _record_equity(token, state)
                save_state(state)
                last_snapshot = time.monotonic()

            if state.get("consecutive_cycle_failures"):
                state["consecutive_cycle_failures"] = 0
                save_state(state)
        except Exception as exc:  # noqa: BLE001
            state = load_state()
            failures = state.get("consecutive_cycle_failures", 0) + 1
            state["consecutive_cycle_failures"] = failures
            state["last_cycle_error"] = str(exc)
            state["last_cycle_error_ts"] = now_iso()
            # 연결 문제가 오래 이어지면(30회 ≈ 5분) 매번 로그를 남겨 노이즈를 만드는 대신
            # 처음 발생 시점과 이후 30회 단위로만 남긴다 — 대시보드 배지가 실시간 카운트를 보여준다.
            if failures == 1 or failures % 30 == 0:
                log_event(state, f"[{MARKET}] 루프 사이클 실패(연속 {failures}회): {exc}")
            save_state(state)

        time.sleep(LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
