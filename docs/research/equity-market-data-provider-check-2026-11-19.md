# KR/US 주식·ETF 데이터 공급자 공개자료 확인 — 2026-11-19

## 범위와 결정

공급자 공식 공개 페이지와 약관만 확인했다. 계정 생성, 인증키 신청, 체험판 등록, 샘플 데이터 다운로드, 업체 문의, 구매, 성과 백테스트는 하지 않았다. 이전 승인 범위는 공개 샘플 범위·가격 조회까지이며 계정 생성·구매 승인은 포함하지 않는다.

**현재 판정:** 미국은 Norgate와 Databento를 데이터 적격성 후보로 비교한다. Databento 공개 샘플은 500개 종목 CSV가 안내되지만 상폐/PIT 표본인지와 로컬+Linux 장기 보관 권리는 미확인이라 현재 사용은 NO-GO다. 한국 KRX도 상폐/PIT 완전성, 총수익 조정, 로컬+Linux 보관 권리가 확인되지 않아 NO-GO다. 어느 시장도 적격 데이터가 검증되지 않았으므로 전략 성과 백테스트는 열지 않는다.

## 한국 — KRX OPEN API

- 공식 서비스 목록은 유가증권, 코스닥, 코넥스 일별매매정보와 ETF 일별매매정보를 제공한다고 적고, 유가증권·코스닥·ETF의 시작일을 2010-01-04로 안내한다. 코넥스는 2013-07-01부터다. 이는 서비스 카탈로그상 기간이지 상장폐지 종목을 포함한 생존편향 없는 완전 유니버스라는 보증이 아니다. [KRX API 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)
- 이용은 회원 가입, 인증키 신청, 관리자 승인, 개별 API 활용 신청·승인 절차를 거친다. 이용약관은 API 사용 목적을 비상업으로 제한하고, 제공 데이터를 제3자에게 제공하지 못하게 하며, 이용 계약 종료 후 데이터 사용을 금지한다. 키당 하루 10,000회 제한이 있다. [KRX 이용방법](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp), [KRX 이용약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp)
- 서비스 상세 화면은 1·3·6·12개월 선택란을 보여주지만 공개 페이지에는 API 사용료가 표시되지 않는다. 상세 출력 필드, 과거 상장폐지 종목 포함 범위, 장기 캐시 보관, 개인 소유 원격 서버에 로컬 복제하는 권리도 공개 페이지만으로 확정되지 않았다. 샘플 테스트는 인증키·API 신청 단계 뒤에 제공되는 흐름으로 안내된다.
- 따라서 KRX를 무료라고 단정하지 않는다. 공개 자료로 확인된 것은 기간·서비스 목록·사용 절차뿐이며, 비용 및 개인 로컬/서버 저장 권리는 미확인이다.

## 미국 — Norgate Data

- US Platinum은 일봉 이력을 1990년까지, 선택된 상장폐지 종목, 과거 지수 구성원을 제공한다고 안내한다. 공개 가격표의 현 가격은 6개월 USD 346.50, 12개월 USD 630이다. 구독은 월 단위가 아니며 기간 중 취소 환불을 기대할 수 없다. [US 주식 가격표](https://norgatedata.com/stockmarketpackages.php), [구독·접근 안내](https://norgatedata.com/)
- 무료 체험은 3주, Platinum 수준이지만 과거 이력은 2년으로 제한된다. 추가 기간이나 맞춤 샘플은 제공하지 않는다고 FAQ가 명시한다. 2년 체험은 데이터 형식·접속·조정 선택 확인에는 쓸 수 있어도, 이 저장소의 504일 학습/252일 테스트 창 5개를 충족하는 성과 검증 데이터로 보기에는 부족하다. [체험 안내](https://norgatedata.com/freetrial.php), [Norgate 데이터 FAQ](https://norgatedata.com/data-package-faq.php)
- 공식 내용표는 US 상장 데이터에 ETF·ETN 등 ETP를 포함하고 US 상장폐지 데이터의 포함 유형에도 ETF·ETN을 열거한다. 다만 공급자는 상장폐지 데이터가 완전하다고 보증하지 않는다고 명시하며, 상장폐지 포함 범위도 주요 거래소에서 거래된 뒤 거래 불가능해진 특정 유형에 한정된다. 공급자 FAQ는 US listed/delisted의 포함 유형이 1992년 말 이후 대체로 완전하다고 표현하고 ETF 이력은 도입 시점인 1993년부터라고 안내한다. 실제 ETF·비활성 상품 샘플과 편입·퇴출 이력은 체험 환경에서 검증해야 한다. [Norgate 내용표](https://norgatedata.com/data-content-tables.php), [Norgate 데이터 FAQ](https://norgatedata.com/data-package-faq.php)
- 가격 조정은 원시값, 자본변동 조정, 자본변동+특별분배 조정, 일반분배까지 반영한 총수익 조정 중에서 선택할 수 있다. 역사 수정·기업행동 조정은 구독 중 계속 반영되지만 데이터 버전 이력은 제공되지 않는다고 FAQ가 명시한다. 매 실행 시 원본 스냅샷·설정·파일 해시를 고정하지 않으면 같은 전략 연구를 재현하기 어렵다. [Norgate 조정·수정 안내](https://norgatedata.com/data-package-faq.php)
- 데이터는 Windows의 Norgate Data Updater에서 제공된다. CSV/ASCII 내보내기는 가능하지만 역사 가격·거래량에 제한되며 과거 지수 구성원과 일부 부가정보는 지원되는 Python/플랫폼 통합이 필요하다. Windows에서 추출한 데이터를 개인 목적으로 Mac/Linux·원격 서버·클라우드에서 처리하는 것은 활성 구독 기간에 허용된다고 FAQ/EULA가 설명한다.
- 중요한 제한: 구독 만료 후 원자료·내보낸 파일·정규화 행·메타데이터·백업을 로컬, 서버, 클라우드 모두에서 삭제해야 한다. 결과 통계와 알고리즘 등 실제 파생정보는 보유 가능하다고 적혀 있다. 따라서 “로컬과 서버에 장기 중복 보관”하려면 지속적인 활성 구독이 필요하며, 구독이 끝나면 원자료 백업을 유지할 수 없다. [Norgate 라이선스 FAQ](https://norgatedata.com/faq.php), [Norgate EULA](https://norgatedata.com/subscribe/eula.php)

## 미국 — EODHD 저비용 S&P 후보 (공식 페이지 재확인)

- 개인용 EOD Historical All-World는 현재 공개 가격표에 월 USD 19.99로 표시된다. 별도 `Indices Historical Constituents Data API` 상품은 월 USD 29.99로 표시되며, S&P 500·400·600의 특정일 구성 스냅샷은 2022-11-22부터, S&P index additions/removals 이력은 2012년부터라고 설명한다. 두 표시 가격을 단순 합산하면 월 USD 49.98이지만, 별도 API 상품의 실제 구독 요건·세금·전체 접근권은 가입 없이 확인하지 않았다. 따라서 이는 구매 견적이나 확정 총액이 아니다. [EODHD 가격표](https://eodhd.com/pricing), [지수 구성원 API와 가격](https://eodhd.com/marketplace/unicornbay/spglobal)
- 제공자가 말하는 구성 이력은 시점별 모집단을 연구할 수 있는 유망한 S&P 주식 후보지만, 2012년 이전에 이미 편입돼 있던 종목은 편입일이 없을 수 있고 일별 구성 스냅샷 API도 2022년 11월부터다. ETF 전 종목을 포함하는 이력으로 보지 않는다. 해당 표본의 상장폐지 가격·식별자 연결·조정 이력까지 데이터 스냅샷에서 독립 검증하지 않았으므로 PIT 게이트 통과로 간주하지 않는다.
- EODHD는 OHLC 원시값과 split/dividend-adjusted close를 구분하고, 과거 조정값이 새 기업행위나 수정으로 다시 계산될 수 있으며 과거 빈티지는 제공하지 않는다고 밝힌다. 연구 재현에는 받은 응답의 날짜·심볼·필드·해시를 보존해야 한다. [EODHD 조정·수정 정책](https://eodhd.com/help/methodology)
- 개인 요금제는 본인만의 사적 리서치·백테스트·페이퍼 트레이딩을 허용하지만, 원자료·차트·결과를 타인에게 제공하거나 조직/사업을 위해 쓰는 것은 허용하지 않는다고 안내한다. 본인 소유 Linux 서버의 장기 보관·복제와 다른 에이전트에 원자료를 전달할 권리는 별도로 확인되지 않았다. 공개 대시보드/텔레그램 배포 및 Git 저장소에 원자료를 올리는 용도로 사용하면 안 된다. [EODHD 개인 사용 범위](https://eodhd.com/help/personal-use), [상업 이용 범위](https://eodhd.com/help/commercial)
- **결정:** EODHD는 개인 전용 S&P 주식 연구의 가장 낮은 표시 가격 후보로 추가한다. 그러나 sample/권리/PIT/상폐/조정/보관을 실제 검증하지 않았으므로 현재는 문서상 후보일 뿐이며, Norgate보다 적격하다고 판정하지 않는다.

## 추가 공개 샘플·저장권 확인 — 2026-11-19

### 한국 — KRX

- 공식 API 카탈로그는 유가증권·코스닥·ETF 일별매매정보를 2010-01-04부터 제공한다고 안내한다. 이는 서비스 시작일 안내이지 상장폐지 종목의 전체 생애나 당시 투자 가능 유니버스가 복구된다는 보증이 아니다. [KRX 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)
- API 샘플 테스트는 인증키가 필요하며, 회원가입·키 승인·API별 활용 신청 절차가 있다. 인증 없는 KRX 화면에서 일부 상장폐지 현황·시세는 조회할 수 있지만, 화면 범위로 PIT 유니버스·조정 OHLC·ETF 분배금 포함 총수익을 검증할 수 없다. [주식 API 상세](https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES002_S2.cmd?BO_ID=JvJFzlAENzZlPBDNGAWC), [ETF API 상세](https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES003_S2.cmd?BO_ID=nrEpCLaZpoLCTzPUMxuF)
- 공개 약관만으로는 로컬 Mac과 본인 소유 Linux 서버의 장기 저장·복제 및 계약 종료 후 보관 권리를 확정할 수 없다. [KRX API 약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp), [KRX 웹사이트 약관](https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO003.cmd)
- **판정: NO-GO.** 이번 확인은 문서 열람뿐이다. 가입, 키 발급, API 호출, 화면 다운로드, 문의 또는 구매를 하지 않았다.

### 미국 — Databento

- 공식 Security Master 페이지는 미국 주식·ETF 500종목의 CSV 표본을 안내한다. 공개 표본 설명만으로 상장폐지 종목이나 과거 PIT 레코드 포함 여부는 증명되지 않는다. 표본을 내려받거나 열지 않았다. [Security Master 샘플 안내](https://databento.com/security-master)
- Security Master 명세는 PIT 상장·폐지일 및 ETF 분류를, Corporate Actions 명세는 2018-05-01 이후 PIT 이벤트를 설명한다. 미국 주식·ETF 가격 자료는 2018년 이후, 과거 데이터 시작 가격은 USD 0.40/GB로 안내되지만 실제 시세·참조데이터 견적은 별도 요청 구성에 달려 있다. [Security Master 명세](https://databento.com/docs/datasets/security-master), [Corporate Actions 명세](https://databento.com/docs/datasets/corporate-actions), [미국 주식 가격 안내](https://databento.com/equities), [청구 안내](https://databento.com/docs/portal/billing)
- 공개 가격·약관은 개인용 라이선스만으로 동일한 원자료를 Mac과 Linux 서버에 영구 보관·복제할 수 있다고 명확히 허가하지 않는다. 제3자 데이터셋별 별도 약관도 적용된다. [Databento 이용약관](https://databento.com/legal/terms-of-use), [가격·라이선스](https://databento.com/pricing)
- **판정: 지속 보관 백테스트는 NO-GO.** 공개 샘플은 적격성 검토 대상일 뿐이고 PIT/상폐 표본이나 두 장치 보관권을 증명하지 않는다. 포털/API 인증, 계정 생성, 표본 다운로드, 연락, 구매는 하지 않았다.

## 다음 단계와 진입 기준

1. **계정·결제 없이 가능한 단계는 여기까지다.** 이전 승인 범위대로 공개 사양과 가격만 확인했고, 인증키·계정·체험판을 만들지 않았다.
2. 한국은 KRX로부터 공개 샘플/명세만으로 답이 나오지 않는 항목을 확인해야 한다: 일별매매정보가 비활성·상장폐지 종목까지 제공하는지, 과거 수정·분배금 데이터 항목, 개인 연구용으로 로컬 및 본인 소유 Linux 서버에 저장·백업해도 되는지, API 사용료와 이용 만료 후 보관 규칙.
3. 미국은 EODHD의 S&P 구성원 및 상장폐지/기업행위 표본을 비성과 메타데이터 검사로 확인하는 경로와, Norgate 2년 체험에서 Windows 실행·CSV/조정·ETF/상장폐지 ETF·과거 구성원 인터페이스를 확인하는 경로를 구분한다. 두 경로 모두 계정·체험·샘플 취득 전 별도 승인이 필요하다. Norgate를 선택하면 구독 종료 때 원자료·백업 삭제 조건을 감당할 수 있어야 한다.
4. 데이터 샘플에서 필드·기업행동·PIT 유니버스·사용권·로컬/서버 보관 권리를 모두 통과한 뒤에만 시장별로 전략을 사전등록하고 성과 데이터를 연다. 그때도 KR·US 각각 순비용 CAGR ≥20%, MDD ≤30%, Sharpe ≥1, OOS 왕복 거래 ≥200 기준은 바꾸지 않는다.

## 이번 검토에서 하지 않은 일

계정/인증키 발급, 무료 체험 등록, KRX·Norgate·CRSP 업체 연락, 샘플 다운로드, 결제, 원자료 적재, 미래 결과 열람, 백테스트, 주문 또는 배포는 수행하지 않았다.

## 저장소에 이미 있는 국장·미장 전략 결과와 중복 방지

이번 저장소 조사에서 과거 실험 자료를 확인했다. 아래 결과는 추가 백테스트가 아니며, 서로 다른 데이터·기간·평가 설계의 기존 실험이다. 특히 현재 워치리스트·현재 지수 구성 종목으로 만든 자료는 과거 투자 가능 유니버스를 증명하지 않으므로 새 전략의 통과 근거로 사용하지 않는다.

- **미장 US-18 momentum-leader dip:** 당시 고정 holdout에서는 410건, 거래당 순수익 +1.984%, 승률 70%, N=10 포트폴리오 Sharpe 2.01, MDD -12.8%로 사전 기준을 통과했다고 기록됐다. 그러나 후속 survivorship 진단에서 현재 S&P 구성원 표본의 편향이 확인됐다. membership-date 유니버스에서 개발 평균은 +0.52%에서 +0.42%로 축소되고 2019년 이후 +0.20%(t=1.16, 2배 비용 후 -0.21%), 2022년 -0.65%였다. MEM·F14·F18의 엄격한 교차 게이트를 통과한 사양은 없었고, US-18 holdout의 성과는 생존편향/레짐 효과로 취급됐다. 기록된 누적 시도는 149회이며 추가 holdout 조회는 금지됐다고 명시돼 있다. 따라서 재탐색하거나 기존 holdout을 다시 열지 않는다. 근거: `docs/archive/salvage_2026-11-15/linuxserver_research/linuxserver_research/stock_loop/results/US_FINAL.md`.
- **국장·미장 Larry Williams 변동성 돌파 0.5:** 생존자 워치리스트 92종목씩을 쓴 단일 하룻밤 보유 탐색 결과다. 기본 비용 포트폴리오 CAGR/Sharpe/MDD는 국장 -9.45%/-1.062/41.57%, 미장 -11.88%/-1.327/48.82%였다. 스트레스 비용에서는 국장 -27.47%/-2.425/70.00%, 미장 -100%/-9.785/344.80%로 기록됐다. 생존편향 코호트이고 봉인 OOS 검증이 아니므로 탈락한 탐색 결과로 보관한다. 근거: `docs/kr-us-equity-trader/vol_breakout_0.5_rule_report.md`.
- **국장·미장 5분 볼린저밴드 BB-01:** 현재 상장 종목의 60세션 스크린이며 거래비용이 왕복 0.37~0.40%로 추정 gross 움직임보다 컸다. 32셀×2 체결 가정×3 필터에서 순수익 양수 셀이 0개였고, 무작위 진입 대조와 구별되는 엣지도 확인되지 않았다. 표본이 짧고 생존편향이 있어 새 검증으로 승격하지 않지만, 같은 규칙·짧은 구간의 재실행은 중복이므로 하지 않는다. 근거: `docs/archive/salvage_2026-11-15/linuxserver_research/linuxserver_research/stock_loop/bb/report.md`.

**통합 판정:** 현재 보유 자료에서는 국장·미장 어느 쪽도 사용자가 고정한 순비용 CAGR ≥20%, MDD ≤30%, Sharpe ≥1.0, OOS 왕복 거래 ≥200 기준을 생존편향을 통제한 데이터로 충족했다고 입증하지 못했다. 다음 주식 전략 연구의 선행조건은 전략 아이디어가 아니라 과거 시점 유니버스·상폐 종목·기업행동·보관권을 입증할 수 있는 데이터다. 그 게이트가 닫히기 전에는 현재 생존자 자료로 후보를 추가 선별하지 않는다.

## Addendum — 공급자 기간·권리·공개 저장소 재확인 (2026-11-19)

### Norgate: 장기 데이터는 적합 후보, 체험판은 OOS에 부적합

- 공식 가격표상 US Platinum은 6개월 USD 346.50, 12개월 USD 630이며 상장폐지 종목과 과거 지수 구성원 접근을 포함한다. 이는 공개 게시 가격이지 별도 견적이나 구매 승인이 아니다. [US 패키지·가격](https://norgatedata.com/stockmarketpackages.php)
- 무료 체험은 3주지만 과거 2년 이력으로 제한된다. 이 기간은 이미 결과가 열린 US-18 holdout(2024-11-12~2026-11-11)과 대부분 겹쳐 신규 전략의 블라인드 과거 OOS가 아니다. [체험판 범위](https://norgatedata.com/data-package-faq.php)
- Norgate의 S&P 500 과거 구성원 기록은 1957-03부터 제공된다고 안내되지만, 2000-03 전 구성 변경은 월말 기준 합성 재구성이다. US Platinum 상폐 종목 데이터는 1990년부터 안내되며, 상폐 후 OTC에서 계속 거래되는 종목과 완전히 거래 불가가 된 종목의 범위 구분을 적용해야 한다. [구성원·상폐 범위](https://norgatedata.com/data-content-tables.php)
- Norgate Data Updater는 Windows 전용이다. EULA는 개인 연구 목적일 때 다른 OS·서버 처리 환경에서 데이터 처리하는 것을 허용하지만, 원자료를 공개/공유 환경에 두는 것은 금지한다. [설치 FAQ](https://norgatedata.com/ndu-faq.php), [EULA](https://norgatedata.com/subscribe/eula.php)
- GitHub API로 확인한 `khsqowp/Coin_Trade` 저장소 visibility는 **public**이다. EULA는 백테스트·통계·개발된 전략을 Derived Data 예시로 정의하지만, 공개 GitHub 게시 권한은 명시적으로 확인되지 않았다. 원자료와 복원 가능한 변환본은 공개 저장소에 넣지 않는다. 상세 파생 결과의 공개 범위도 공급자 서면 확인 전까지 미확정으로 둔다.
- 구독 종료 시 원자료·추출 Content·백업은 삭제 대상이며 Derived Data는 보유할 수 있다. 파일 경로와 Git 관리에서 이 두 범주를 분리해야 한다. 계정이나 체험판은 만들지 않았다.

### KRX: 공개 일봉 API는 부분 해법, 적격 유니버스는 미확인

- KRX OPEN API 서비스 목록은 유가증권·코스닥 주식 및 ETF의 일별 정보를 2010-01-04부터, 코넥스는 2013-07-01부터 제공한다고 안내한다. API 문구는 상장폐지 종목의 완전 포함이나 과거 시점 투자 가능 유니버스 복원을 보증하지 않는다. [서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)
- KRX Data Marketplace에는 상장폐지 종목의 OHLCV·거래대금·시가총액 조회 화면이 있다. 화면 존재만으로 전체 상폐 이력 일괄 취득, 기업행동 조정, Mac+Linux 장기 저장권을 입증하지 않는다. 데이터 상품의 기간·샘플·가격은 로그인 뒤 확인하며, 결제 및 용도 심사 뒤 제공하는 절차다. [상폐종목 시세 화면](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp), [구매 안내](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA001.jsp)
- 코스콤 DataMall은 국내 수정주가(CA 반영)와 ETF 분배금 상품을 목록에 표시하지만, 공식 DataMall은 운영 잠정 중단을 공지한다. 현재 활성 견적/표본 경로로 간주하지 않는다. [DataMall](https://datamall.koscom.co.kr/kor/main.do), [중단 안내](https://datamall.koscom.co.kr/indexKor.jsp)

### 실행 판정

계정·인증키·체험판·구매 승인은 기존 공개 사양·샘플 범위·가격 조회 허가에 포함되지 않으므로 진행하지 않았다. Norgate 체험은 기술 적합성 확인에는 쓸 수 있지만 새 OOS 성과 검증에는 부적합하다. 유료 Norgate 자료는 미국 장기 PIT/상폐 연구의 가장 명확한 후보이나, 공개 GitHub에 게시할 파생 결과의 범위와 구독 종료 시 삭제 절차를 구매 전에 확정해야 한다. 한국은 일괄 상폐·기업행동 이력과 개인용 로컬·서버 보관권을 확인하기 전까지 NO-GO다.

## Addendum — Kibot 공개 샘플 및 보관권 확인 (2026-11-19)

- Kibot은 미국 주식·ETF 일별 EOD 표본을 공개하며 무료 샘플 페이지는 가입·이메일·결제 없이 이용 가능하다고 명시한다. 일별 형식은 날짜, OHLC, 거래량 6열이며 조정 기본값과 `unadjusted=1` 선택을 안내한다. 표본은 파서와 단일 시계열의 형식 확인에는 쓸 수 있지만 과거 투자 가능 유니버스나 성과 검증에는 충분하지 않다. [공개 샘플 페이지](https://www.kibot.com/free-historical-intraday-data.html), [가격·패키지](https://www.kibot.com/buy.html)
- 공급자는 전체 묶음에 미국 주식 18,000개 이상, ETF 6,900개 이상 및 28년 이력을 표시하고, All Stocks & ETFs 일회 구매 가격을 USD 990으로 게시한다. 이는 공급자 주장과 표시 가격이지 독립된 커버리지 감사나 결제 총액이 아니다. [Kibot 카탈로그](https://www.kibot.com/buy.html)
- 라이선스는 구매 데이터의 영구 보관을 허용하고, 개인 사용자의 내부 사용·통상 접근하는 두 컴퓨터 및 백업 사본을 허용한다. AI 도구로 개인 데이터 사본을 처리하는 것도 허용한다고 적혀 있다. 다만 “두 컴퓨터” 조항이 사용자의 개인 Linux 서버와 Mac 복제 구성을 명시적으로 포함하는지는 공개 문구만으로 확정할 수 없다. [Kibot 라이선스](https://www.kibot.com/license.html)
- 공급자의 종목 변경 문서는 티커 재사용, 과거 이력의 심볼 간 이동, 일부 구상장폐지·기업 이력 구간 누락 가능성을 직접 명시한다. 별도 영구 ID와 완전한 상장폐지 종목 모집단을 확인하지 못했다. [티커·상폐 처리](https://www.kibot.com/datasets/ticker-changes-and-delistings.html)
- **판정: no-account 샘플 포맷 점검 후보일 뿐, PIT 적격 데이터는 아니다.** 샘플 접근은 허가된 범위지만 이 작업에서는 파일을 내려받지 않았고, 계정·구매·문의·성과시험도 하지 않았다. 공개 문서만으로 전략 백테스트 적격성을 주장하지 않는다.
