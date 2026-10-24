"""모멘텀 로테이션 실주문 실행부.

판단(모멘텀 랭킹·리밸런스 타이밍)은 momentum_rotation_loop.py 에 그대로 두고, 여기서는
주문·잔고·포지션 동기화만 담당한다. 시세(일봉/현재가)는 항상 메인넷 공개 API를 쓰고,
여기 클라이언트는 주문/계좌 조회 전용 — testnet / mainnet 스위칭도 이 클라이언트만 바뀐다.

거래소의 실제 포지션이 항상 진실이다. state 파일은 기록/표시용이며, 매 사이클
sync_positions() 로 거래소에서 재동기화한다(리밸런스 도중 죽어도 다음 사이클에 이어감).

원웨이 모드 + 크로스 마진(바이낸스 기본) 전제. 청산 주문은 reduceOnly 로 넣어 방향 반전 방지.
"""
from __future__ import annotations

import os
from functools import lru_cache

import ccxt

from app.ccxt_retry import retry_read


@lru_cache(maxsize=2)
def exec_client(mode: str) -> ccxt.binance:
    """mode: 'testnet' | 'mainnet'. 주문/잔고/포지션 전용."""
    if mode == "testnet":
        key = os.environ["BINANCE_FUTURE_TESTNET_API_KEY"]
        secret = os.environ["BINANCE_FUTURE_TESTNET_SECRET_KEY"]
    elif mode == "mainnet":
        key = os.environ["BINANCE_API_KEY"]
        secret = os.environ["BINANCE_SECRET_KEY"]
    else:
        raise ValueError(f"알 수 없는 거래소 모드: {mode!r} (testnet|mainnet)")

    client = ccxt.binance({
        "apiKey": key,
        "secret": secret,
        "enableRateLimit": True,
        "timeout": 15000,
        "options": {"defaultType": "future", "adjustForTimeDifference": True},
    })
    if mode == "testnet":
        client.set_sandbox_mode(True)
    client.load_markets()
    return client


def perp_symbol(base: str) -> str:
    return f"{base}/USDT:USDT"


def account_equity_usdt(client) -> float:
    """USDT 마진잔고(= 지갑잔고 + 전 포지션 미실현손익). 이게 전략의 equity."""
    balance = retry_read(client.fetch_balance)
    info = balance.get("info", {}) or {}
    try:
        return float(info["totalMarginBalance"])
    except (KeyError, TypeError, ValueError):
        pass
    usdt = balance.get("USDT", {}) or {}
    wallet = float(usdt.get("total") or 0.0)
    # 포지션 조회 실패 시 upnl=0 으로 조용히 넘어가면 equity 가 과소평가돼 가짜 드로다운(킬 오발동)·
    # 사이징 오류가 난다 — 값을 지어내지 않고 예외로 올려 이번 사이클을 중단시킨다.
    upnl = sum(float(p.get("unrealizedPnl") or 0.0) for p in retry_read(client.fetch_positions))
    return wallet + upnl


def sync_positions(client) -> dict:
    """거래소 실포지션. base -> {side, contracts, notional, entry_price, unrealized_pnl}."""
    out: dict[str, dict] = {}
    for pos in retry_read(client.fetch_positions):
        contracts = float(pos.get("contracts") or 0.0)
        if contracts == 0:
            continue
        symbol = pos.get("symbol", "")
        if "/" not in symbol:
            continue
        base = symbol.split("/")[0]
        out[base] = {
            "side": pos.get("side"),
            "contracts": contracts,
            "notional": abs(float(pos.get("notional") or 0.0)),
            "entry_price": float(pos.get("entryPrice") or 0.0),
            "mark_price": float(pos.get("markPrice") or 0.0),
            "unrealized_pnl": float(pos.get("unrealizedPnl") or 0.0),
        }
    return out


def _close_one(client, symbol: str, pos: dict) -> None:
    amount = pos["contracts"]
    params = {"reduceOnly": True}
    if pos["side"] == "long":
        client.create_market_sell_order(symbol, amount, params)
    else:
        client.create_market_buy_order(symbol, amount, params)


def flatten_all(client, log, owned: set | None = None, tag: str = "KILL") -> None:
    """전량 청산. 킬 스위치(자동, dd 초과)와 수동 즉시매도 둘 다 이 함수를 쓴다 — tag 로 구분해서 로그에
    찍는다(둘 다 무조건 "[KILL]"로 찍으면 사용자가 직접 판 것도 킬 스위치가 발동한 것처럼 보여 혼란을
    준다 — 실제로 겪은 문제). owned 지정 시 그 종목만."""
    for base, pos in sync_positions(client).items():
        if owned is not None and base not in owned:
            continue
        try:
            _close_one(client, perp_symbol(base), pos)
            log(f"[{tag}] {base} {pos['side']} {pos['contracts']} 청산")
        except Exception as exc:  # noqa: BLE001
            log(f"[{tag}] {base} 청산 실패: {exc}")


def _resize_tolerance() -> float:
    try:
        return max(0.0, float(os.environ.get("MOMENTUM_ROTATION_RESIZE_TOLERANCE", "0.15")))
    except ValueError:
        return 0.15


def _market_mins(client, symbol: str):
    limits = client.market(symbol).get("limits", {}) or {}
    min_cost = (limits.get("cost", {}) or {}).get("min") or 5.0
    min_amount = (limits.get("amount", {}) or {}).get("min") or 0.0
    return min_cost, min_amount


def _place_market(client, symbol: str, side: str, amount: float, reduce_only: bool = False) -> None:
    """side: 'long'=매수, 'short'=매도 주문 방향. 진입/증액/감액 공통 주문 헬퍼."""
    params = {"reduceOnly": True} if reduce_only else None
    fn = client.create_market_buy_order if side == "long" else client.create_market_sell_order
    if params:
        fn(symbol, amount, params)
    else:
        fn(symbol, amount)


def _available_margin(client) -> float | None:
    balance = retry_read(client.fetch_balance)
    info = balance.get("info", {}) or {}
    try:
        return float(info["availableBalance"])
    except (KeyError, TypeError, ValueError):
        pass
    free = (balance.get("USDT", {}) or {}).get("free")
    return float(free) if free is not None else None


def _plan_resize(client, base: str, pos: dict, price, notional_per_pos: float, tol: float, result: dict):
    """유지 포지션의 증감 계획. (kind, amount, delta_notional) 또는 None(허용오차 내/스킵)."""
    mark = pos.get("mark_price") or price
    if not mark or notional_per_pos <= 0:
        return None
    current_notional = pos["contracts"] * mark
    delta = notional_per_pos - current_notional
    if abs(delta) / notional_per_pos <= tol:
        return None
    symbol = perp_symbol(base)
    try:
        min_cost, min_amount = _market_mins(client, symbol)
        amount = abs(delta) / mark
        kind = "up" if delta > 0 else "down"
        if kind == "down":
            amount = min(amount, pos["contracts"])
        amount = float(client.amount_to_precision(symbol, amount))
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"{base} 리사이즈 계획: {exc}")
        return None
    if amount <= 0 or abs(delta) < min_cost or amount < min_amount:
        result["skipped"].append(f"{base}(리사이즈 델타 ${abs(delta):.2f} 최소 미달)")
        return None
    if kind == "down" and amount >= pos["contracts"]:
        result["skipped"].append(f"{base}(감액이 전량 청산 수준 — 스킵)")
        return None
    return kind, amount, abs(delta)


def _exec_resize(client, base: str, pos: dict, plan, leverage: int, log, result: dict) -> None:
    kind, amount, delta = plan
    symbol = perp_symbol(base)
    side = pos["side"]
    try:
        if kind == "up":
            avail = _available_margin(client)
            need = delta / max(leverage, 1)
            if avail is None or need > avail * 0.9:
                msg = f"{base}(증액 마진부족: 필요 ${need:.2f} / 가용 {avail})"
                result["skipped"].append(msg)
                log(f"[RESIZE] {msg}")
                return
            try:
                client.set_leverage(leverage, symbol)
            except Exception as exc:  # noqa: BLE001
                log(f"{base}: set_leverage 경고 ({exc})")
            _place_market(client, symbol, side, amount)
        else:
            order_side = "short" if side == "long" else "long"
            _place_market(client, symbol, order_side, amount, reduce_only=True)
        result["resized"].append(f"{base}/{side} {'+' if kind == 'up' else '-'}{amount:g} (${delta:.2f})")
        log(f"[RESIZE] {base} {side} {'증액' if kind == 'up' else '감액'} {amount:g} (델타 ${delta:.2f})")
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"{base} 리사이즈: {exc}")


def apply_targets(client, prices: dict, targets: dict, notional_per_pos: float,
                  leverage: int, log, owned: set | None = None,
                  resize_tolerance: float | None = None) -> dict:
    """targets: base -> 'long'|'short'. 최소주문 미달은 스킵.

    owned: 이 전략이 직접 연 것으로 아는 base 집합. 지정되면 이 집합 + targets 안의
    종목만 건드린다(같은 선물지갑을 다른 전략이 쓰고 있어도 그 포지션은 안 닫음).

    1) owned 중 타겟에 없거나 방향이 바뀐 포지션 청산
    2) 유지(같은 방향) 포지션 중 목표 명목 초과분 감액(reduceOnly, 마진 확보)
    3) 타겟에 있는데 없는(또는 방향 다른) 포지션 진입
    4) 유지 포지션 중 목표 명목 미달분 증액(마진 가용 확인) — |현재-목표|/목표 > 허용오차(기본 0.15)일 때만
    """
    result = {"opened": [], "closed": [], "skipped": [], "errors": [], "resized": []}
    tol = _resize_tolerance() if resize_tolerance is None else resize_tolerance
    current = sync_positions(client)
    manageable = set(targets) | (owned if owned is not None else set(current))

    for base, pos in current.items():
        if base not in manageable:
            continue  # 다른 전략 소유 — 건드리지 않음
        if targets.get(base) == pos["side"]:
            continue
        try:
            _close_one(client, perp_symbol(base), pos)
            result["closed"].append(base)
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"{base} 청산: {exc}")

    current = sync_positions(client)
    retained = {b: p for b, p in current.items() if b in targets and targets[b] == p["side"]}
    plans = {b: _plan_resize(client, b, p, prices.get(b), notional_per_pos, tol, result)
             for b, p in retained.items()}
    for base, plan in plans.items():
        if plan and plan[0] == "down":
            _exec_resize(client, base, retained[base], plan, leverage, log, result)

    for base, side in targets.items():
        if base in retained:
            continue
        symbol = perp_symbol(base)
        price = prices.get(base)
        if not price:
            result["skipped"].append(f"{base}(시세없음)")
            continue
        try:
            market = client.market(symbol)
        except Exception:  # noqa: BLE001
            result["skipped"].append(f"{base}(마켓없음)")
            continue

        limits = market.get("limits", {}) or {}
        min_cost = (limits.get("cost", {}) or {}).get("min") or 5.0
        min_amount = (limits.get("amount", {}) or {}).get("min") or 0.0
        amount = notional_per_pos / price
        if notional_per_pos < min_cost:
            result["skipped"].append(f"{base}(명목 ${notional_per_pos:.2f} < 최소 ${min_cost})")
            continue
        if amount < min_amount:
            result["skipped"].append(f"{base}(수량 {amount:.6g} < 최소 {min_amount:g}, 명목 ${notional_per_pos:.2f})")
            continue

        try:
            client.set_leverage(leverage, symbol)
        except Exception as exc:  # noqa: BLE001
            # 이미 같은 값이면 바이낸스가 에러를 안 낸다. 다른 에러면 진입 시도는 계속.
            log(f"{base}: set_leverage 경고 ({exc})")

        amount = float(client.amount_to_precision(symbol, amount))
        if amount <= 0:
            result["skipped"].append(f"{base}(수량 반올림 0)")
            continue
        try:
            if side == "long":
                client.create_market_buy_order(symbol, amount)
            else:
                client.create_market_sell_order(symbol, amount)
            result["opened"].append(f"{base}/{side}")
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"{base} 진입: {exc}")

    for base, plan in plans.items():
        if plan and plan[0] == "up":
            _exec_resize(client, base, retained[base], plan, leverage, log, result)

    if result["resized"]:
        final = sync_positions(client)
        longs = sum(p["notional"] for b, p in final.items() if b in targets and p["side"] == "long")
        shorts = sum(p["notional"] for b, p in final.items() if b in targets and p["side"] == "short")
        log(f"[RESIZE] 리사이즈 후 총명목 long ${longs:.2f} / short ${shorts:.2f}")

    return result
