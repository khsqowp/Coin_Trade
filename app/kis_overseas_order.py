"""한국투자증권 해외주식(미국) 모의투자 주문/잔고/현재가 API 래퍼.

실측 확인된 요청 형식 (koreainvestment/open-trading-api 공식 예제 기준, 이 세션에서
직접 실주문 테스트는 아직 안 해봄 — us_swing_loop 첫 실행에서 실제 체결 확인 필요):
  - 매수 TR VTTT1002U(모의), 매도 TR VTTT1001U(모의) — POST /uapi/overseas-stock/v1/trading/order
  - 모의투자는 지정가(ORD_DVSN "00")만 허용 — 시장가 불가. 즉시체결 유도를 위해 매수는 현재가+1%,
    매도는 현재가-1%로 지정가를 잡는다("마켓터블 리밋" 방식).
  - 잔고 TR VTTS3012R — GET /uapi/overseas-stock/v1/trading/inquire-balance
  - 현재가 TR HHDFS00000300 — GET /uapi/overseas-price/v1/quotations/price

주문 API의 거래소코드(OVRS_EXCG_CD)는 "NASD"/"NYSE" 등 긴 코드를 쓰는데, 시세/일봉 API의
EXCD("NAS"/"NYS")와 다르므로 _ORDER_EXCG_MAP으로 변환한다.
"""
from __future__ import annotations

import json

from app.kis_auth import VTS_BASE_URL, app_credentials, throttled_request

BUY_TR_ID = "VTTT1002U"
SELL_TR_ID = "VTTT1001U"
BALANCE_TR_ID = "VTTS3012R"
PRICE_TR_ID = "HHDFS00000300"
PSAMOUNT_TR_ID = "VTTS3007R"  # 모의투자 해외주식 매수가능금액조회 [v1_해외주식-014]

_ORDER_EXCG_MAP = {"NAS": "NASD", "NYS": "NYSE"}
MARKETABLE_LIMIT_BUFFER = 0.01  # 즉시체결 유도용 지정가 버퍼(매수 +1%, 매도 -1%)


def _headers(token: str, tr_id: str) -> dict:
    app_key, app_secret = app_credentials()
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "custtype": "P",
    }


def inquire_price(token: str, symbol: str, excd: str) -> float:
    resp = throttled_request(
        "GET",
        f"{VTS_BASE_URL}/uapi/overseas-price/v1/quotations/price",
        headers=_headers(token, PRICE_TR_ID),
        params={"AUTH": "", "EXCD": excd, "SYMB": symbol},
    )
    body = resp.json()
    if body.get("rt_cd") != "0" or not body.get("output", {}).get("last"):
        raise RuntimeError(f"{symbol} 현재가 조회 실패: {body.get('msg_cd')} {body.get('msg1')}")
    return float(body["output"]["last"])


def place_order(token: str, cano: str, acnt_prdt_cd: str, symbol: str, excd: str, side: str,
                 qty: int, limit_price: float) -> dict:
    """side: 'buy' 또는 'sell'. 모의투자는 지정가만 되므로 limit_price를 그대로 낸다
    (마켓터블 리밋 가격 계산은 호출부 책임)."""
    tr_id = BUY_TR_ID if side == "buy" else SELL_TR_ID
    ovrs_excg_cd = _ORDER_EXCG_MAP[excd]
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": ovrs_excg_cd,
        "PDNO": symbol,
        "ORD_QTY": str(qty),
        "OVRS_ORD_UNPR": f"{limit_price:.2f}",
        "CTAC_TLNO": "",
        "MGCO_APTM_ODNO": "",
        "SLL_TYPE": "00" if side == "sell" else "",
        "ORD_SVR_DVSN_CD": "0",
        "ORD_DVSN": "00",
    }
    resp = throttled_request(
        "POST",
        f"{VTS_BASE_URL}/uapi/overseas-stock/v1/trading/order",
        headers=_headers(token, tr_id),
        data=json.dumps(body),
    )
    return resp.json()


def inquire_psamount(token: str, cano: str, acnt_prdt_cd: str, excd: str, symbol: str,
                      unit_price: float) -> dict:
    """계좌 KRW예수금/환율 근사치가 아니라 KIS가 실제로 인정하는 주문가능금액을 직접 조회한다
    (모의투자 계좌는 별도 USD 잔고가 없어 근사치와 실제 심사 기준이 어긋나 매수가 '주문가능금액
    부족'으로 거부되는 문제 때문 — output.max_ord_psbl_qty가 그 주문의 진짜 최대체결가능수량)."""
    ovrs_excg_cd = _ORDER_EXCG_MAP[excd]
    resp = throttled_request(
        "GET",
        f"{VTS_BASE_URL}/uapi/overseas-stock/v1/trading/inquire-psamount",
        headers=_headers(token, PSAMOUNT_TR_ID),
        params={
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "OVRS_EXCG_CD": ovrs_excg_cd,
            "OVRS_ORD_UNPR": f"{unit_price:.2f}",
            "ITEM_CD": symbol,
        },
    )
    return resp.json()


def inquire_balance(token: str, cano: str, acnt_prdt_cd: str, excd: str) -> dict:
    headers = _headers(token, BALANCE_TR_ID)
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": excd,
        "TR_CRCY_CD": "USD",
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": "",
    }
    resp = throttled_request(
        "GET",
        f"{VTS_BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance",
        headers=headers,
        params=params,
    )
    return resp.json()
