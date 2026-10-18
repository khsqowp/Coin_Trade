"""바이낸스 실계좌 스팟/선물 클라이언트 팩토리.

스팟과 USDⓈ-M 선물 모두 하나의 API 키 쌍(BINANCE_API_KEY/BINANCE_SECRET_KEY)을 공유한다 —
테스트넷과 달리 실계좌는 스팟/선물 거래 권한을 같은 키에 함께 부여하기 때문이다.

spot_client()/futures_client()는 프로세스당 인스턴스를 하나만 만들어 재사용한다(lru_cache) —
ccxt는 클라이언트를 처음 쓸 때 load_markets()/fetchCurrencies()를 자동 호출해 마켓·통화
메타데이터를 인스턴스에 캐싱하는데, 호출부가 매 사이클(60초)마다 새 클라이언트를 만들면 이
무거운 부트스트랩(공개 exchangeInfo + 서명이 필요한 sapi/v1/capital/config/getall)이 매번
반복되어 API 부하만 늘고 간헐적 타임아웃/-1021 recvWindow 오류의 표면적을 키웠다.
adjustForTimeDifference는 그 recvWindow 오류에 대한 추가 방어막이다.
"""
from __future__ import annotations

import os
from functools import lru_cache

import ccxt


@lru_cache(maxsize=1)
def spot_client() -> ccxt.binance:
    return ccxt.binance({
        "apiKey": os.environ["BINANCE_API_KEY"],
        "secret": os.environ["BINANCE_SECRET_KEY"],
        "enableRateLimit": True,
        "timeout": 15000,
        "options": {"defaultType": "spot", "adjustForTimeDifference": True},
    })


@lru_cache(maxsize=1)
def futures_client() -> ccxt.binance:
    return ccxt.binance({
        "apiKey": os.environ["BINANCE_API_KEY"],
        "secret": os.environ["BINANCE_SECRET_KEY"],
        "enableRateLimit": True,
        "timeout": 15000,
        "options": {"defaultType": "future", "adjustForTimeDifference": True},
    })
