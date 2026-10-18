"""한국투자증권 국내주식 모의투자 주문/잔고/현재가 API 래퍼.

kis_order_test.py / kis_balance_retry.py로 실측 검증된 요청 형식 그대로 사용:
  - 매수 TR VTTC0012U, 매도 TR VTTC0011U (order-cash, POST)
  - 잔고 TR VTTC8434R (inquire-balance, GET)
  - 현재가 TR FHKST01010100 (inquire-price, GET)
"""
from __future__ import annotations

import json

from app.kis_auth import VTS_BASE_URL, app_credentials, throttled_request

BUY_TR_ID = "VTTC0012U"
SELL_TR_ID = "VTTC0011U"
BALANCE_TR_ID = "VTTC8434R"
PRICE_TR_ID = "FHKST01010100"


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


def place_order(token: str, cano: str, acnt_prdt_cd: str, symbol: str, side: str,
                 qty: int, price: int | None = None) -> dict:
    """side: 'buy' 또는 'sell'. price=None이면 시장가(01), 지정하면 지정가(00)."""
    tr_id = BUY_TR_ID if side == "buy" else SELL_TR_ID
    ord_dvsn = "00" if price else "01"
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "PDNO": symbol,
        "ORD_DVSN": ord_dvsn,
        "ORD_QTY": str(qty),
        "ORD_UNPR": str(price) if price else "0",
        "EXCG_ID_DVSN_CD": "KRX",
    }
    resp = throttled_request(
        "POST",
        f"{VTS_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash",
        headers=_headers(token, tr_id),
        data=json.dumps(body),
    )
    return resp.json()


def inquire_balance(token: str, cano: str, acnt_prdt_cd: str) -> dict:
    headers = _headers(token, BALANCE_TR_ID)
    headers["tr_cont"] = ""
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    resp = throttled_request(
        "GET",
        f"{VTS_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
        headers=headers,
        params=params,
    )
    return resp.json()


def inquire_price(token: str, symbol: str) -> float:
    """현재가(종가/실시간가) 반환. 실패 시 예외."""
    resp = throttled_request(
        "GET",
        f"{VTS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
        headers=_headers(token, PRICE_TR_ID),
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
    )
    body = resp.json()
    if body.get("rt_cd") != "0":
        raise RuntimeError(f"{symbol} 현재가 조회 실패: {body.get('msg_cd')} {body.get('msg1')}")
    return float(body["output"]["stck_prpr"])
