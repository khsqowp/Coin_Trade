"""KIS 웹소켓 실시간(0분지연) 체결가 수신 — 국장(H0STCNT0)+미장(HDFSCNT0) 단일 세션 동시구독.

공개 시세 채널(체결가)은 평문 파이프(|)/캐럿(^) 구분 텍스트라 AES 복호화가 필요없다(계좌 전용
체결통보 채널만 암호화 대상). REST 액세스토큰과 별개로 접속키(approval_key)를 발급받아 쓴다.

구독 대상은 kr_swing_state.json/us_swing_state.json을 읽어 "보유중+매매대기" 종목을 최우선,
나머지는 daily_scan이 매일 갱신하는 tick_rank(EMA9/21 근접도 랭킹) 순서로 채운다. 워치리스트
전체(국장45+미장38=83종목) 구독을 시도하다가 KIS가 한도초과로 거부하면 그 지점에서 멈춘다
(정확한 세션당 동시구독 한도가 공식문서에 없어 실측으로 확인). tick_rank는 daily_scan 주기와
동일하게 하루 1번만 바뀌므로, 날짜가 바뀌면 재접속해서 구독종목을 그 날 랭킹으로 리밸런싱한다.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import time
from zoneinfo import ZoneInfo

import requests
import websockets

from app.kis_auth import VTS_BASE_URL, app_credentials
from app.kr_state import load_state as load_kr_state
from app.tick_archive import append_batches
from app.tick_state import load_state, log_event, now_iso, save_state
from app.us_state import load_state as load_us_state
from app.us_watchlist import STOCK_UNIVERSE as US_UNIVERSE

WS_URL = "ws://ops.koreainvestment.com:31000"  # 모의투자 전용 도메인(kis_auth.py와 동일 이유)
KR_TR_ID = "H0STCNT0"
US_TR_ID = "HDFSCNT0"
KR_SYMBOL_IDX, KR_PRICE_IDX = 0, 2   # MKSC_SHRN_ISCD, STCK_PRPR
US_SYMBOL_IDX, US_PRICE_IDX = 1, 11  # 종목코드, 현재가
_US_EXCD_PREFIX = {"NAS": "DNAS", "NYS": "DNYS"}
_US_EXCD_BY_SYMBOL = {symbol: excd for symbol, excd, _ in US_UNIVERSE}

MAX_TICKS_PER_SYMBOL = 500
FLUSH_INTERVAL_SECONDS = 30
SUBSCRIBE_ACK_TIMEOUT_SECONDS = 5
KST = ZoneInfo("Asia/Seoul")


def _issue_approval_key() -> str:
    app_key, app_secret = app_credentials()
    resp = requests.post(
        f"{VTS_BASE_URL}/oauth2/Approval",
        json={"grant_type": "client_credentials", "appkey": app_key, "secretkey": app_secret},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["approval_key"]


def _kr_candidates() -> list[str]:
    kr = load_kr_state()
    priority = list(dict.fromkeys(
        list(kr.get("entry_cost", {})) + kr.get("pending_entries", []) + kr.get("pending_exits", [])
    ))
    rank = [s for s in kr.get("tick_rank", []) if s not in priority]
    return priority + rank


def _us_candidates() -> list[tuple[str, str]]:
    """(symbol, excd) — tr_key 접두어 계산에 거래소코드 필요."""
    us = load_us_state()
    priority = list(dict.fromkeys(
        list(us.get("entry_cost", {})) + us.get("pending_entries", []) + us.get("pending_exits", [])
    ))
    rank = [s for s in us.get("tick_rank", []) if s not in priority]
    ordered = priority + rank
    return [(s, _US_EXCD_BY_SYMBOL[s]) for s in ordered if s in _US_EXCD_BY_SYMBOL]


def _build_candidates() -> list[tuple[str, str, str]]:
    """(market, tr_id, tr_key) 리스트 — market은 로그/집계용."""
    messages = [("KR", KR_TR_ID, symbol) for symbol in _kr_candidates()]
    for symbol, excd in _us_candidates():
        prefix = _US_EXCD_PREFIX.get(excd)
        if prefix is None:
            continue
        messages.append(("US", US_TR_ID, f"{prefix}{symbol}"))
    return messages


def _subscribe_payload(approval_key: str, tr_type: str, tr_id: str, tr_key: str) -> str:
    return json.dumps({
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": tr_type,
            "content-type": "utf-8",
        },
        "body": {"input": {"tr_id": tr_id, "tr_key": tr_key}},
    })


def _ingest_tick(raw: str, buffer: dict[str, list[dict]]) -> None:
    parts = raw.split("|")
    if len(parts) < 4:
        return
    tr_id, count_str, data_blob = parts[1], parts[2], parts[3]
    if tr_id == KR_TR_ID:
        symbol_idx, price_idx, market = KR_SYMBOL_IDX, KR_PRICE_IDX, "KR"
    elif tr_id == US_TR_ID:
        symbol_idx, price_idx, market = US_SYMBOL_IDX, US_PRICE_IDX, "US"
    else:
        return

    fields = data_blob.split("^")
    try:
        count = int(count_str)
    except ValueError:
        count = 1
    if count <= 0 or len(fields) % count != 0:
        count = 1
    per_record = len(fields) // count

    ts = now_iso()
    for i in range(count):
        record = fields[i * per_record:(i + 1) * per_record]
        if len(record) <= max(symbol_idx, price_idx):
            continue
        symbol = record[symbol_idx]
        try:
            price = float(record[price_idx])
        except ValueError:
            continue
        buffer.setdefault(symbol, []).append({"ts": ts, "price": price, "market": market})


def _flush_ticks(
    buffer: dict[str, list[dict]], pending_archive: dict[str, list[dict]]
) -> None:
    if buffer:
        state = load_state()
        ticks = state.setdefault("ticks", {})
        batches: dict[str, list[dict]] = {"kr": [], "us": []}
        for symbol, points in buffer.items():
            history = ticks.setdefault(symbol, [])
            history.extend(points)
            ticks[symbol] = history[-MAX_TICKS_PER_SYMBOL:]
            for market, category in (("KR", "kr"), ("US", "us")):
                batches[category].extend(
                    {"symbol": symbol, "ts": p["ts"], "price": p["price"]}
                    for p in points if p.get("market") == market
                )
        save_state(state)
        for category, records in batches.items():
            pending_archive.setdefault(category, []).extend(records)
        buffer.clear()

    if pending_archive:
        append_batches(pending_archive)
        pending_archive.clear()


async def _next_non_ping(ws: websockets.ClientConnection, buffer: dict[str, list[dict]]) -> dict:
    """PINGPONG은 즉시 에코 응답하고, 데이터 push는 버퍼링만 하며 흘려보내고, 그 다음 JSON
    시스템응답(구독 성공/실패 ack)을 반환한다."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=SUBSCRIBE_ACK_TIMEOUT_SECONDS)
        if raw[:1] in ("0", "1"):
            _ingest_tick(raw, buffer)
            continue
        msg = json.loads(raw)
        if msg.get("header", {}).get("tr_id") == "PINGPONG":
            await ws.send(raw)
            continue
        return msg


async def _subscribe_all(
    ws: websockets.ClientConnection, approval_key: str, candidates: list[tuple[str, str, str]],
    buffer: dict[str, list[dict]],
) -> dict[str, list[str]]:
    subscribed: dict[str, list[str]] = {"kr": [], "us": []}
    state = load_state()
    log_event(state, f"[접속] 구독시도 {len(candidates)}종목 (국장 {sum(1 for m, _, _ in candidates if m == 'KR')} "
                      f"/ 미장 {sum(1 for m, _, _ in candidates if m == 'US')})")
    save_state(state)

    for market, tr_id, tr_key in candidates:
        await ws.send(_subscribe_payload(approval_key, "1", tr_id, tr_key))
        try:
            ack = await _next_non_ping(ws, buffer)
        except asyncio.TimeoutError:
            state = load_state()
            log_event(state, f"[구독중단] {tr_key}: 응답없음 — 여기까지 {sum(len(v) for v in subscribed.values())}종목 구독됨")
            save_state(state)
            break
        rt_cd = (ack.get("body") or {}).get("rt_cd")
        if rt_cd not in (None, "0"):
            state = load_state()
            msg1 = (ack.get("body") or {}).get("msg1")
            log_event(state, f"[구독거부] {tr_key}: {msg1} — 여기까지 {sum(len(v) for v in subscribed.values())}종목 구독됨(한도로 추정)")
            save_state(state)
            break
        subscribed["kr" if market == "KR" else "us"].append(tr_key)
        await asyncio.sleep(0.15)

    return subscribed


async def _session(
    approval_key: str,
    buffer: dict[str, list[dict]],
    pending_archive: dict[str, list[dict]],
) -> None:
    candidates = _build_candidates()

    async with websockets.connect(WS_URL, ping_interval=None) as ws:
        subscribed = await _subscribe_all(ws, approval_key, candidates, buffer)
        state = load_state()
        state["subscribed"] = subscribed
        log_event(state, f"[구독완료] 국장 {len(subscribed['kr'])}종목 / 미장 {len(subscribed['us'])}종목")
        save_state(state)

        last_flush = time.monotonic()
        rebalance_date = dt.datetime.now(KST).date()

        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=120)
            if raw[:1] in ("0", "1"):
                _ingest_tick(raw, buffer)
            else:
                msg = json.loads(raw)
                if msg.get("header", {}).get("tr_id") == "PINGPONG":
                    await ws.send(raw)

            now_mono = time.monotonic()
            if now_mono - last_flush >= FLUSH_INTERVAL_SECONDS:
                try:
                    _flush_ticks(buffer, pending_archive)
                except OSError as exc:
                    state = load_state()
                    log_event(state, f"[틱아카이브 저장실패] 메모리 대기열 유지 후 재시도: {exc}")
                    save_state(state)
                last_flush = now_mono

            if dt.datetime.now(KST).date() != rebalance_date:
                while buffer or pending_archive:
                    try:
                        _flush_ticks(buffer, pending_archive)
                    except OSError as exc:
                        state = load_state()
                        log_event(state, f"[틱아카이브 저장실패] 리밸런싱 전 메모리 대기열 유지 후 재시도: {exc}")
                        save_state(state)
                        await asyncio.sleep(5)
                        continue
                state = load_state()
                log_event(state, "[리밸런싱] 날짜 변경 감지, 재접속해서 구독종목(tick_rank 최신본)으로 갱신")
                save_state(state)
                return


def main() -> None:
    state = load_state()
    log_event(state, "틱 스트림 시작")
    save_state(state)

    buffer: dict[str, list[dict]] = {}
    pending_archive: dict[str, list[dict]] = {}
    while True:
        try:
            approval_key = _issue_approval_key()
            asyncio.run(_session(approval_key, buffer, pending_archive))
        except Exception as exc:  # noqa: BLE001
            state = load_state()
            log_event(state, f"[오류] 세션 종료, 재접속: {exc}")
            save_state(state)
            time.sleep(10)


if __name__ == "__main__":
    main()
