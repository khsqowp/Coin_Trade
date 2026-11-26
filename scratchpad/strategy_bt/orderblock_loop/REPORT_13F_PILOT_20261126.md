# SEC 13F 파일럿 보고서 (2026-11-26)

## 결론

수집 파일럿은 데이터 0행으로 끝났다. SEC EDGAR 쪽에서 HTTP 403으로 요청을 거부해 안내 페이지도, zip 링크도 받지 못했다. 13F 파이프라인 코드와 네트워크 없는 유닛 테스트는 준비됐고, 코드 자체의 오류 처리는 정상 동작을 확인했다(크래시 없이 종료 코드 2로 멈춤).

## 파일럿 결과 (실제 네트워크 접근: 오케스트레이션 세션에서 직접 실행)

Codex(`codex exec`)의 작업 샌드박스는 네트워크가 완전히 차단돼 있어(DNS 조회 자체가 실패) Codex 안에서의 시도는 SEC 서버에 도달조차 못 했다. 그래서 실제 인터넷 접근이 되는 오케스트레이션 세션에서 같은 스크립트를 다시 직접 실행해 진짜 결과를 확인했다.

- 실행 명령: `TRADING_DATA_DIR=/Users/user/CODE/Coin_Trade/trading_data python data_sources/disclosures/fetch_13f.py --pilot` (저장소 안 기존 가상환경 `trading_data/cache/disclosures/venv` 사용).
- 결과: `SEC 요청 실패: HTTP 403`, 종료 코드 2. 코드가 예외를 명시적으로 잡아 깨끗하게 멈췄다(요청대로 추측 URL 강행이나 재시도 폭주 없음).
- 같은 URL(`https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets`)을 `curl -A "Coin_Trade Research kknd03255@naver.com"`로 별도 확인 — 응답 `server: AkamaiGHost`, 본문 제목 `SEC.gov | Request Rate Threshold Exceeded`.
- 이 결과는 이번 세션 시작 시 확인한 선행 관측(아래)과 일치한다: `https://www.sec.gov/`, `/cgi-bin/browse-edgar`, `data.sec.gov/submissions/...`, `/robots.txt`, `/Archives/edgar/full-index/...`, `efts.sec.gov/...` 전부 HTTP 403, 두 가지 문구(`SEC.gov | Request Rate Threshold Exceeded` / `SEC.gov | Your Request Originates from an Undeclared Automated Tool`)가 번갈아 나타났다. 대조군 `https://example.com`, `https://api.github.com`은 200으로 정상이었고, 현재 송신 IP는 한국 SK Broadband(AS9318, Seoul) 주거용 대역이다(ipinfo.io 확인).
- User-Agent를 정확한 "조직명 연락이메일" 형식(`Coin_Trade Research kknd03255@naver.com`)으로 보내도 결과가 바뀌지 않았다. 즉 이번 차단은 UA 형식 문제가 아니라 SEC의 Akamai 봇 방어가 이 IP/네트워크 자체를 선제적으로 막고 있는 것으로 보인다.
- **차단을 우회하는 시도는 하지 않았다**: 프록시/VPN/다른 송신 IP, 헤더·TLS 핑거프린트 위장, 헤드리스 브라우저 등은 전혀 쓰지 않았다. 실제 수집 시도는 진단용 수회 + 코드 실행 1회로 소규모였고, 403이 반복돼 더 밀어붙이지 않고 멈췄다.
- ZIP 링크 확인: 0개. 원본 ZIP/TSV/제출 헤더 파일: 0개. parquet 행: 0. SHA-256 데이터 manifest: 생성되지 않음.
- 분기별 ZIP URL 패턴은 안내 페이지를 받지 못해 **확인 안 됨**이다(코드 안 주석에 "추정"이라고만 표시돼 있고, 이 추정 URL로 다운로드를 강행하지 않았다).

### Codex 샌드박스 안에서의 시도 (참고, 비교용)
- Codex의 `codex exec` 작업 샌드박스에서 같은 요청을 2회 시도했으나 모두 DNS 이름 조회 자체가 실패했다(이 네트워크 격리는 Codex 샌드박스 자체 정책이며 SEC 응답이 아니다). HTTP 상태 코드 없음, 응답 본문 없음.
- 이 시도 중 첫 번째는 `sec_common.SEC_USER_AGENT` 공통 설정이 만들어지기 전 임시 UA 값으로 이뤄졌다(요청된 "UA는 한 곳에서만 관리" 규칙을 일시적으로 벗어난 시도). 다만 DNS 실패로 어차피 SEC 서버에 요청이 도달하지 않았으므로 실질적 영향은 없다.

## 구현 및 PIT 시점

- `fetch_13f.py`는 공식 안내 페이지 HTML에서 실제 ZIP 링크만 추출한다. 링크가 없으면 중단하고 추정 링크를 사용하지 않는다.
- 공식 ZIP에서 `SUBMISSION.TSV`, `COVERPAGE.TSV`, `INFOTABLE.TSV`를 읽고 accession 번호로 결합하도록 작성했다. 각 accession의 EDGAR 헤더 텍스트에서 `<ACCEPTANCE-DATETIME>` 14자리 값을 원문 그대로 추출해 `accepted_at`에 저장한다. 이 구현은 시간대 변환을 하지 않으며, 실제 SEC 파일의 시간대 해석은 **확인 안 됨**이다.
- `period_of_report`는 커버페이지의 보고 대상 분기말이며 `accepted_at`과 별도 컬럼이다. 백테스트 체결은 `accepted_at` 기준으로만 해야 하고 `period_of_report`는 참고용이다.
- 네트워크 없는 테스트에서 합성 SGML 헤더의 acceptance 시각 추출, 합성 ZIP의 세 TSV 결합, 두 PIT 컬럼의 분리를 확인했다. 실제 제출의 시각 및 ZIP 열 구조는 이번에 받아 보지 못했으므로 실데이터 호환성은 **확인 안 됨**이다.
- 모든 SEC HTTP 요청은 `sec_common.SEC_USER_AGENT`를 사용하고 연속 요청 사이 최소 1초를 기다리도록 구성했다. 연락처는 `SEC_USER_AGENT` 환경변수 (기본값 있음)로 관리한다.
- 산출 예정 위치는 `TRADING_DATA_DIR/external/disclosures/13f/raw/`, `TRADING_DATA_DIR/external/disclosures/13f/parquet/`, `TRADING_DATA_DIR/external/disclosures/13f/MANIFEST_sha256.csv`다. 파일럿 실패로 이 데이터 산출물은 생성하지 않았다.

## 전체 수집 비용의 거친 추정

SEC 안내 페이지가 열리지 않아 공개된 분기 수치나 ZIP 용량 수치를 확인하지 못했다. 2013년 2분기부터 2026년 3분기까지 달력상 54개 분기라고 놓은 계산이며, 실제 게시 범위는 **확인 안 됨**이다.

요청량을 가늠하기 위해 분기당 제출기관 1천~5천 곳이라는 가정을 두면, 제출 헤더 요청은 약 5만4천~27만 회다. 초당 1회 제한에서는 헤더 요청만 약 15~75시간이 걸린다. 이는 데이터에서 센 제출 건수가 아니라 수천 기관에 분기당 한 번 제출한다고 둔 계획용 범위이며, 실제 제출 수·재제출·네트워크 대기 시간은 다를 수 있다. ZIP·TSV·parquet의 총 용량은 **확인 안 됨**이며, 실제 분기 ZIP 크기를 확인하기 전에는 저장 용량 수치를 제시하지 않는다.

## 변경 파일과 검증

- `data_sources/disclosures/sec_common.py`: 공통 SEC User-Agent 기본 설정과 요청 속도 제한기.
- `data_sources/disclosures/fetch_13f.py`: 안내 링크 검색, TSV 파싱, accession acceptance 시각 수집, zstd parquet 및 manifest 작성.
- `data_sources/disclosures/test_fetch_13f.py`: 합성 입력 기반 오프라인 테스트.
- `data_sources/DISCLOSURE_PLAN.md`: 13F 상태와 2026-11-26 결정 기록 갱신.
- `scratchpad/strategy_bt/orderblock_loop/REPORT_13F_PILOT_20261126.md`: 이번 결과 기록.

테스트 실행: 저장소의 기존 가상환경에서 `python -m unittest discover -s data_sources/disclosures -p 'test_fetch_13f.py' -v`를 실행했다. 통과 7개, 실패 0개다. 최초 `pytest` 실행은 해당 가상환경에 pytest가 없어 실행되지 않았고, 패키지를 추가 설치하지 않고 기존 unittest 방식으로 7개를 실행해 통과를 확인했다.

## 한계 및 규칙

- 실제 네트워크 접근 결과는 HTTP 403(SEC Akamai 봇 방어)이다. 이게 일시적 속도 제한인지, 이 IP 대역에 대한 더 오래가는 차단인지는 **확인 안 됨** — 재시도 간격을 넓혀 다시 테스트하거나 다른 네트워크에서 확인해야 알 수 있다. 사용자의 판단 없이 추가 재시도나 네트워크 변경은 하지 않았다.
- SEC 안내 페이지에서 링크를 검증하지 못했고 실제 ZIP·TSV·제출 헤더·parquet·manifest 생성도 하지 못했다. 현 데이터 행 수는 0이며, 파서가 실제 SEC 파일 구조와 맞는지는 합성 데이터로만 확인했고 실제 SEC 파일 호환성은 확인 안 됨이다.
- Codex 샌드박스 안 시도는 네트워크가 막혀 있어 SEC 응답을 아예 받지 못했다(참고용으로만 기록, 이번 보고서의 결론에는 쓰지 않았다).
- 요청된 저장소 경로 밖의 데이터 경로, `Ochestration`, 실거래·서버, git add/commit/push는 사용하지 않았다. 차단 우회(프록시/VPN/핑거프린트 위장 등)도 시도하지 않았다.
