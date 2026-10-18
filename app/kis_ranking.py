"""한국투자증권 국내주식 등락률 순위 조회 (순위분석[v1_국내주식-088], TR FHPST01700000).

개장 직후 급등주 갭업 진입 전략을 백테스트하려면 "그 순간 시장에서 뭐가 오르고 있었는지"가
필요한데, KIS 분봉 조회는 보통 당일치만 주고 과거 날짜를 재현 못 한다(실측 필요 —
app/kis_data.py 일봉 조회처럼 페이지네이션되는 건 확인했지만 분봉은 아직 안 써봄).
그래서 개장 시간대에 실시간으로 스냅샷을 떠서 쌓아두는 것 말고는 사후 재현 방법이 없다.

이 TR은 계좌 조회가 아니라 시세 조회라 CANO/ACNT_PRDT_CD가 필요 없고, TR ID가 "F"로
시작해 모의/실전 구분 없이 같은 TR ID를 그대로 쓴다(app/kis_order.py 류의 계좌 TR과 다름).

파라미터 이름과 TR ID는 한국투자증권 공식 예제로 확인함
(koreainvestment/open-trading-api: examples_llm/domestic_stock/fluctuation/fluctuation.py).
다만 fid_rank_sort_cls_code · fid_trgt_cls_code · fid_trgt_exls_cls_code 세 개는 예제 저장소
안에서도 문서 docstring과 실행 스크립트 예시값이 서로 달라(문서는 "0000", 실행 예시는 "0")
정확한 열거값을 못 정했다 — 장이 열리는 평일 최초 실행 때 rt_cd 로 검증 필요.
"""
from __future__ import annotations

from app.kis_auth import VTS_BASE_URL, app_credentials, throttled_request

TR_ID = "FHPST01700000"
API_PATH = "/uapi/domestic-stock/v1/ranking/fluctuation"


def fetch_fluctuation_ranking(token: str, rising_only: bool = True, max_pages: int = 5) -> list[dict]:
    """등락률 순위 스냅샷(output 배열)을 그대로 반환한다 — 필드 해석은 호출부/사후 분석
    몫으로 남긴다(응답 필드명을 미리 확정 못 했으므로 원본 그대로 보존하는 쪽이 안전).

    한 페이지가 몇 종목인지 공식 예제로도 못 정했지만(보통 20~30건대로 알려짐), 이 랭킹은
    이미 등락률순 정렬이라 "오늘 뜨는 종목"은 앞쪽 몇 페이지에 다 들어있다 — 순위 900번대
    까지 긁는 건 이 전략엔 의미가 없고 페이지당 최소 호출간격(throttled_request 안에서
    ~1초) 때문에 스냅샷 하나가 그만큼 느려지기만 한다. 기본 5페이지로 제한.
    """
    app_key, app_secret = app_credentials()
    base_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": TR_ID,
        "custtype": "P",
    }
    params = {
        "fid_cond_mrkt_div_code": "J",       # KRX
        "fid_cond_scr_div_code": "20170",    # 등락률 순위 화면 — 고정값(다른 값이면 API가 거부)
        "fid_input_iscd": "0000",            # 전종목
        "fid_rank_sort_cls_code": "0" if rising_only else "1",  # 0:상승률순 1:하락률순 (추정 — 확인 필요)
        "fid_input_cnt_1": "0",              # 전체 반환
        "fid_prc_cls_code": "0",             # 가격 필터 없음
        "fid_input_price_1": "",
        "fid_input_price_2": "",
        "fid_vol_cnt": "",
        "fid_trgt_cls_code": "0",
        "fid_trgt_exls_cls_code": "0",
        "fid_div_cls_code": "0",
        "fid_rsfl_rate1": "",
        "fid_rsfl_rate2": "",
    }
    rows: list[dict] = []
    tr_cont = ""
    for _ in range(max_pages):
        headers = {**base_headers, "tr_cont": tr_cont}
        resp = throttled_request("GET", f"{VTS_BASE_URL}{API_PATH}", headers=headers, params=params)
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(f"등락률순위 조회 실패: {body.get('msg_cd')} {body.get('msg1')}")
        rows.extend(body.get("output", []))
        tr_cont = resp.headers.get("tr_cont", "")
        if tr_cont != "M":  # "M" = 다음 페이지 있음(공식 예제 기준), 그 외면 마지막 페이지
            break
    return rows
