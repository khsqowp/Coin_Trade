"""모멘텀 로테이션 실거래 경로 점검 스크립트.

읽기 전용 점검(1~7)은 항상 수행. 실주문 점검(8)은 LIVETEST_EXECUTE=true 일 때만:
  테스트넷에서 종목 1개 롱 진입 → 포지션 확인 → 즉시 청산.

실행:
  docker run --rm --entrypoint python --env-file .env -v .../trading/app:/app/app \
    -e MOMENTUM_ROTATION_EXCHANGE=testnet ochestration-trading-momentum-rotation \
    -m app.momentum_rotation_livetest
"""
from __future__ import annotations

import os
import time

from app.momentum_rotation_exec import (
    account_equity_usdt, apply_targets, exec_client, flatten_all, perp_symbol, sync_positions,
)
from app.momentum_rotation_loop import (
    LEVERAGE, TOP_K, _fetch_current_prices, _target_sides,
)

MODE = os.environ.get("MOMENTUM_ROTATION_EXCHANGE", "testnet")
NOTIONAL = float(os.environ.get("MOMENTUM_ROTATION_START_CAPITAL_USDT", "70"))
EXECUTE = os.environ.get("LIVETEST_EXECUTE", "false").lower() == "true"


def _ok(msg):
    print(f"  [OK] {msg}", flush=True)


def _fail(msg):
    print(f"  [FAIL] {msg}", flush=True)


def run() -> None:
    print(f"=== 모멘텀 로테이션 실거래 점검 (거래소: {MODE}, 실주문: {EXECUTE}) ===\n")

    print("[1] 인증 클라이언트 연결 + load_markets")
    try:
        client = exec_client(MODE)
        _ok(f"연결됨, 마켓 {len(client.markets)}개")
    except Exception as exc:  # noqa: BLE001
        _fail(f"연결 실패: {exc}")
        return

    print("[2] 계좌 잔고/equity 조회")
    try:
        equity = account_equity_usdt(client)
        _ok(f"equity {equity:.2f} USDT")
    except Exception as exc:  # noqa: BLE001
        _fail(f"잔고 조회 실패: {exc}")
        return

    print("[3] 현재 포지션 동기화")
    try:
        positions = sync_positions(client)
        _ok(f"보유 {len(positions)}종목: {list(positions)}")
    except Exception as exc:  # noqa: BLE001
        _fail(f"포지션 조회 실패: {exc}")
        return

    print("[4] 현재가 조회 (메인넷 공개 API)")
    prices = _fetch_current_prices()
    if not prices:
        _fail("시세 전체 실패")
        return
    _ok(f"{len(prices)}종목 시세 확보 (예: BTC {prices.get('BTC')}, SOL {prices.get('SOL')})")

    print("[5] 모멘텀 랭킹 계산")
    targets = _target_sides()
    if targets is None:
        _fail("모멘텀 데이터 부족")
        return
    longs = [b for b, s in targets.items() if s == "long"]
    shorts = [b for b, s in targets.items() if s == "short"]
    _ok(f"롱 {longs}")
    _ok(f"숏 {shorts}")

    print("[6] 최소주문 체크 (포지션당 명목가 산정)")
    notional_per_pos = equity * LEVERAGE / 2 / TOP_K if equity > 0 else NOTIONAL * LEVERAGE / 2 / TOP_K
    print(f"  기준: equity {equity:.2f} x {LEVERAGE}배 / 2 / {TOP_K} = 포지션당 {notional_per_pos:.2f} USDT")
    skipped, tradable = [], []
    for base in list(targets):
        if not prices.get(base):
            skipped.append(f"{base}(시세없음)")
            continue
        try:
            market = client.market(perp_symbol(base))
        except Exception:  # noqa: BLE001
            skipped.append(f"{base}(마켓없음)")
            continue
        limits = market.get("limits", {}) or {}
        min_cost = (limits.get("cost", {}) or {}).get("min") or 5.0
        min_amt = (limits.get("amount", {}) or {}).get("min") or 0.0
        amt = notional_per_pos / prices[base]
        if notional_per_pos < min_cost or amt < min_amt:
            skipped.append(f"{base}(<${min_cost} 또는 수량<{min_amt})")
        else:
            tradable.append(base)
    _ok(f"거래가능 {len(tradable)}/{len(targets)}종목: {tradable}")
    if skipped:
        print(f"  [스킵예정] {skipped}")

    print("[7] set_leverage 시험 (첫 거래가능 종목)")
    if tradable:
        sym = perp_symbol(tradable[0])
        try:
            client.set_leverage(LEVERAGE, sym)
            _ok(f"{tradable[0]} 레버리지 {LEVERAGE}x 설정 성공")
        except Exception as exc:  # noqa: BLE001
            print(f"  [경고] set_leverage: {exc}")

    if not EXECUTE:
        print("\n실주문 점검은 건너뜀 (LIVETEST_EXECUTE=true 로 실행 시 수행).")
        print("읽기 전용 점검 완료.")
        return

    print("\n[8] 실주문 왕복 (테스트넷) — 첫 거래가능 종목 롱 진입 후 즉시 청산")
    if MODE != "testnet":
        _fail("MODE 가 testnet 이 아님 — 실주문 점검 거부")
        return
    if not tradable:
        _fail("거래가능 종목 없음")
        return
    base = tradable[0]
    one = {base: "long"}
    res = apply_targets(client, prices, one, notional_per_pos, LEVERAGE, print)
    print(f"  진입 결과: {res}")
    time.sleep(2)
    pos = sync_positions(client)
    _ok(f"진입 후 포지션: {pos}")
    time.sleep(1)
    flatten_all(client, print)
    time.sleep(2)
    pos = sync_positions(client)
    if pos:
        _fail(f"청산 후에도 포지션 남음: {pos}")
    else:
        _ok("청산 확인 — 포지션 없음")
    print("\n실주문 왕복 점검 완료.")


if __name__ == "__main__":
    run()
