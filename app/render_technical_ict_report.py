"""Render complete Korean section 13 from the committed execution artifact."""
import json
import re
from pathlib import Path
from app.technical_signal_common import NAMES, LABELS

ROOT=Path(__file__).resolve().parents[1]
DEFINITIONS=[
    '종가 5% 반전으로 확정한 ZigZag 저·고·저·고·저 5점에서 파동2 저점 상승, 파동3>파동1, 파동4 23.6~61.8% 되돌림·파동1 비침범을 만족한 확정일을 파동5 진입 신호로 사용.',
    'RSI(14)가 전일 30 미만에서 당일 30 이상으로 복귀하면 롱 신호.',
    'EMA9가 EMA21을 상향 교차하고 종가가 SMA200 위에 있을 때 롱 신호; 기존 EMA 지표 정의 재사용.',
    '재귀적으로 계산한 HA_Open에 대해 HA_Close가 음봉에서 양봉으로 전환하면 롱 신호.',
    '확정 ZigZag 저→고 임펄스의 종가 되돌림이 0.5~0.618 구간을 밟은 뒤 0.5 위로 복귀하면 롱 신호; 0.786 아래 종가에서는 패턴 폐기.',
    '전형가격×거래량의 20일 롤링 VWAP 아래였던 종가가 위로 복귀하면 롱 신호.',
    '2봉 전 고가<현재 저가의 불리시 FVG를 확정한 뒤 후속 봉이 갭 범위와 겹치면 롱 신호; 갭 하단 종가 이탈·60일 경과 시 폐기, 첫 유효 태핑 후 소모.',
    '직전 60일 전형가격을 24개 가격 bin으로 나눠 거래량 합계 최대 bin을 POC로 정의; POC 아래에서 최대 bin 거래량의 절반 미만인 양의 거래량 bin을 LVN으로 정의하고, LVN~POC 사이 전일 종가가 POC 위로 돌파하면 롱 신호.',
    '양봉 몸통>전일 ATR14×1.5 및 종가>전일 고가의 임펄스 직전 5봉 내 마지막 음봉의 고저를 OB로 확정; 후속 봉이 구간을 밟고 종가가 상단 위로 복귀하면 롱 신호, 60일 만료·하단 이탈·첫 반응 후 폐기.',
    '직전 20일 저점을 0~5% 하향 침범하고 당일 종가가 회복하거나, 스윕 당일 미회복 뒤 다음날 종가가 그 기준 저점 위로 복귀하면 롱 신호.',
]
RANKINGS=['파동3/파동1 길이','100−RSI14','EMA9/EMA21−1','HA 양봉 몸통/ATR14','임펄스 폭/ATR14','전일 VWAP 이탈폭/ATR14','갭 폭/ATR14','POC 거래량/LVN 거래량','OB 폭/ATR14','실제 스윕봉의 기준저점 침범폭/신호일 ATR14']


def config_text(config):
    timing={'next_open':'다음날 시가','confirm_open':'1봉 상승확인 후 시가'}
    stop={'none':'없음','pct10':'10%','pct5':'5%','atr1':'ATR1','atr2':'ATR2','structure':'구조저점'}
    tp={'none':'없음','pct20':'20%','pct30':'30%'}
    return f"{timing[config['timing']]} / SL {stop[config['stop']]} / TP {tp[config['tp']]} / {config['hold_days']}일 / {config['selection']}"


def render():
    result=json.loads((ROOT/'docs/technical-ict-results-2026-10-06.json').read_text())
    verification=(ROOT/'docs/technical-ict-verification-2026-10-06.txt').read_text()
    prefix_checks=int(re.search(r'PASS: (\d+) prefix checks',verification).group(1))
    lines=['## 13. 보조지표 + ICT 전략 10종 종합 검증 (2026-10-06)','',
           '실행: `python3.12 -m app.crypto_technical_ict_research`. 원시 수치는 `docs/technical-ict-results-2026-10-06.json`, 캐시 파일 SHA256·상장별 데이터 시작일도 포함. 검증은 `python3.12 -m app.verify_technical_ict`, 문서 재생성은 `python3.12 -m app.render_technical_ict_report`.','',
           f"- **공통 기간 2019-09-08 ~ 2026-10-05, 45종목 전부 로드, 캐시 누락 {len(result['skipped'])}종목.** 요청 시작은 2019-01-01이나 캐시 내 최초 선물봉은 2019-09-08이다. 상장 전 데이터는 만들지 않고 해당 종목을 매수 후보에서 제외한다. 2026-10-06 미완성 UTC 봉은 제외했다.",
           f"- **BTC buy&hold CAGR {result['btc_cagr']:+.2f}%**: 같은 시작일 시가 매수→종료일 종가 매도, 편도 0.04% 수수료 각각 차감. 판정은 반올림 전 Sharpe≥1.0 AND CAGR>BTC-B&H. Sharpe는 무위험수익률 0, 일수익률 표본표준편차×√365.",
           '- baseline: 롱온리·무배율·TOP_K=8·손절/익절 없음, RSI/VWAP/리퀴디티 10일, 나머지 20일 보유. 진입일 인덱스+보유일의 종가 청산으로 기존 §12 엔진의 일수 규칙을 유지한다. 실제 OHLC로 체결하며 HA 가격으로 체결하지 않는다.',
           '- **fetch_perp_ohlcv에는 실제로 캐시 처리가 없다.** 호출하면 네트워크를 쓰는 코드이므로 러너가 `.screen_cache/binance_usdtm_1d/` CSV를 직접 읽는다. 캐시 누락·부족은 skip 로그에 남기고 네트워크 요청을 하지 않는다. 데이터 fetch 함수와 라이브 루프는 수정하지 않았다.',
           '- **기존 엔진의 당일 종가 기반 시가 배분을 제거했다.** 현재 시가와 이전 평가가격만으로 신규 배분한다. 진입봉 손절·익절도 체크하고, 시가 갭 손절은 시가 체결, 같은 봉 손절·익절 동시 충족은 손절 우선. 일중 청산 현금은 같은 날 시가 진입에 재사용하지 않는다. 마지막 날은 종가 강제청산·수수료 차감. §12와 자본·수수료·보유일은 같지만 체결 수정 및 기간 차이 때문에 수치의 직접 우열은 잠정 비교다.',
           '- 실행 환경 Python 3.12에는 pandas/numpy/ccxt만 있고 pandas_ta가 없다. 설치 환경에서는 `more_indicators.add_ema_cross_indicators`를 재사용하고, 이번 실행은 별도 fallback의 pandas-ta 비TA-Lib 정의(Wilder RMA, SMA 초기화 EMA)를 사용했다. TA-Lib 사용 환경과 세부 수치 차이가 생길 수 있어 동일 환경 재현이 필요하다.',
           '- **TJR 교육 전체 또는 재량 ICT 매매를 복제한 결과가 아니다.** 참고 원본: [Boot Camp Day 14: Fair Value Gaps Pt.1](https://www.youtube.com/watch?v=d0AxLACYaqU), [Day 30: Execution](https://www.youtube.com/watch?v=ESsy0uoFAz4). 원본 페이지는 확인했으나 본문/자막을 확보하지 못해 교육 내용 전부를 검증했다고 주장하지 않는다. 요청한 10개 규칙을 일봉 독립 신호로 수치화했으며 세션·BOS/MSS 결합·kill zone은 이번 범위 밖이다.',
           '- **FRVP는 실제 가격별 체결량이 아닌 일봉 전형가격 히스토그램 근사다.** 일별 앵커 VWAP는 1일봉에서 전형가격 하나로 퇴화하므로 20일 롤링만 사용한다. ZigZag는 종가 기반 5% 반전 확인 방식이며 과거 극값 날짜에 신호를 소급하지 않는다.',
           '- 펀딩비·슬리피지·시장충격·상장폐지 생존편향 미반영. 현재 유니버스를 과거에 적용한 in-sample 연구이며 스윕 승자는 out-of-sample 검증 전 승격 보류.','',
           '스윕 축과 전체 조합:','',
           '| 단계 | 진입 | 손절 | 익절 | 보유 | 후보 선택 | 조합 |',
           '|---|---|---|---|---|---|---|',
           '| 1 | 다음날 시가 / 추가 1봉 종가 상승 확인 후 그 다음날 시가 | 없음 / 10% | 없음 / 20% | 10 / 20일 | rank / all | 2×2×2×2×2=32 |',
           '| 2 | 1단계 최고 Sharpe 조합의 진입 고정 | ATR14×1 / ×2 / 5% / 구조저점 | 없음 / 30% | 5 / 40일 | 1단계 최고 조합 선택모드 고정 | 4×2×2=16 |','',
           '- **미달 전략마다 두 단계 각 Cartesian product를 전부 실행했다(48조합).** 2단계 최고 기준은 Sharpe 우선, 동률 CAGR. 모든 가능한 수치의 무한 탐색을 의미하지 않는다. ATR1.5·R배수·반대신호는 이번 유한 그리드에서 제외했다. 당일 확정 종가 즉시 체결은 신호 확정 후 동일 종가 체결을 보장할 수 없어 제외했다.',
           '- rank: 빈 TOP_K 슬롯에 신호 강도 내림차순, 동률 심볼명 순, 시가 평가자산/8씩 배분. all: 신규 신호 전부에 가용 현금을 균등 분할하고 8종목 상한은 해제, 기존 포지션 유지·레버리지 없음. **두 모드의 차이는 랭킹과 분산·투자비중을 함께 바꾸므로 순수 랭킹 효과로 해석할 수 없다.**',
           '- 구조손절: 엘리엇 파동4 저점, 피보나치 0.786, FVG 갭 하단, OB 하단, 리퀴디티 스윕봉·전일 저가 중 작은 값, 나머지는 직전 20일 저점. 진입 시가보다 높거나 산출 불가능한 손절은 진입 제외. 기준은 신호 확정 시점에서 동결한다.','']
    for index,s in enumerate(result['strategies']):
        b=s['baseline']; cfg=s['baseline_config']
        lines += [f"### 13-{index+1}. {LABELS[index]}",'',DEFINITIONS[index],f"랭킹: {RANKINGS[index]} 내림차순. 총 원시 신호 {s['signal_count']:,}건.",'',
                  '| baseline 보유 | CAGR | MDD | Sharpe | 매매건수 |','|---|---|---|---|---|',
                  f"| {cfg['hold_days']}일 | {b['cagr']:+.2f}% | {b['mdd']:.2f}% | {b['sharpe']:.3f} | {b['trades']:,} |",'',
                  f"기대치: **{'충족 — 스윕 생략' if s['baseline_pass'] else '미달 — 48조합 스윕 실행'}**.",'']
        if s['sweep']:
            lines += ['| 단계-번호 | 진입 | SL | TP | 보유일 | 선택 | CAGR | MDD | Sharpe | 매매 | 충족 |',
                      '|---|---|---|---|---|---|---|---|---|---|---|']
            for j,row in enumerate(s['sweep'],1):
                m=row['metrics']; config=row['config']
                hit=m['sharpe']>=1 and m['cagr']>result['btc_cagr']
                lines.append(f"| {row['stage']}-{j:02} | {config['timing']} | {config['stop']} | {config['tp']} | {config['hold_days']} | {config['selection']} | {m['cagr']:+.2f}% | {m['mdd']:.2f}% | {m['sharpe']:.3f} | {m['trades']} | {'충족' if hit else '미달'} |")
            best=max(s['sweep'],key=lambda row:(row['metrics']['sharpe'],row['metrics']['cagr']))
            m=best['metrics']
            lines += ['',f"베스트(Sharpe 우선): **{config_text(best['config'])}** — CAGR {m['cagr']:+.2f}%, MDD {m['mdd']:.2f}%, Sharpe {m['sharpe']:.3f}, {m['trades']}건.",'']
            if s['winners']:
                lines += [f"- **스윕 {len(s['winners'])}조합 기대치 충족, 실거래 승격 보류.**"]
                for row in s['winners']:
                    m=row['metrics']
                    lines.append(f"- 충족 조합: {config_text(row['config'])}, CAGR {m['cagr']:+.2f}%, MDD {m['mdd']:.2f}%, Sharpe {m['sharpe']:.3f}.")
            else:
                lines += ['- **스윕으로도 기대치 미달 — 이번 독립 신호 정의는 승격 기각.**']
            if s['name']=='fibonacci':
                lines += ['- **Sharpe 1.007만으로는 통과가 아니다.** CAGR +29.11%로 BTC 기준을 밑돌아 두 조건 동시 충족에 실패했다.']
        else:
            lines += ['- **baseline 기대치 충족, 연구 후보 유지·실거래 승격 보류.** 낙폭 70%대라 손절 없는 장기 운용을 바로 승인할 근거는 부족하다.']
        lines += ['- **일봉 독립 규칙의 결과로 보인다.** 재량 타이밍·다른 시간봉·신호 결합의 성과를 이 표에서 추론하지 않는다.','']
    lines += ['### 13종 종합 결론 (이번 검증 10종)','',
              '| 범주 | 전략 / 조합 | CAGR | MDD | Sharpe |','|---|---|---|---|---|',
              '| baseline 최고 CAGR | 하이킨 아시 / rank·20일 | +71.30% | 72.24% | 1.110 |',
              '| baseline 최고 Sharpe | FRVP 근사 / rank·20일 | +67.45% | 73.07% | 1.113 |',
              '| 전체 최고 Sharpe | VWAP / confirm_open·SL10%·TP없음·20일·all | +108.65% | 87.32% | 1.246 |',
              '| 전체 최고 CAGR | VWAP / next_open·SL없음·TP없음·20일·all | +113.02% | 83.87% | 1.229 |',
              '| 기존 §12-3 | 거래량폭증 vol3x/cap5%/hold20d | +66.1% | 53.7% | 1.20 |',
              '| 기존 §12-3 | 거래량폭증 vol3x/cap3%/hold20d | +54.2% | 56.2% | 1.09 |','',
              '- **baseline 통과는 2/10종(하이킨 아시·FRVP), 미달 8종×48=384조합 중 통과 4조합(VWAP 3·FVG 1).** 신호 0건·매매 0건·CAGR 수천% 결과는 없었다. RSI baseline은 +0.00%가 아니라 반올림 전 −0.0053%로 사실상 손익분기다.',
              '- **VWAP는 수치상 §12보다 CAGR·Sharpe 우위지만 낙폭 84~87%로 우월한 운용 전략이라고 볼 수 없다.** 하이킨 아시·FRVP도 최고 거래량폭증 Sharpe 1.20보다 낮고 MDD가 70%대로 더 크다. FVG 통과 조합은 Sharpe 1.051로 §12의 1.09~1.20보다 낮다. 엔진·기간·all 배분 차이까지 있어 공정한 실전 승자 판정은 보류한다.',
              '- **엘리엇·RSI·EMA·피보나치·OB·리퀴디티 스윕은 스윕 후에도 동시 기준 미달.** 개별 규칙만으로 BTC 보유보다 높은 수익과 Sharpe 1 이상을 함께 확보하지 못했다.',
              f'- **미래참조 검사 {prefix_checks}개 prefix 비교와 동작·회계 검사 7개 통과.** prefix 검사는 BTC/ETH/SOL의 여러 길이·실제 신호 절단점에서 SIGNAL/강도/ATR/구조손절 전체 과거값 불변을 확인했다. 회계 검사는 왕복 수수료·진입봉 동시 SL/TP 손절 우선·갭 손절·당일 종가의 배분 불변·all 12종목 진입·추가 확인봉 이후 시가 체결·FVG 생성봉 진입 금지를 확인했다. 검증 로그는 `docs/technical-ict-verification-2026-10-06.txt`.',
              '', '### 다음 (TODO)', '',
              '- VWAP 통과 3조합과 하이킨 아시·FRVP 근사의 워크포워드/연도별 검증. 신호 확정 후 시가·펀딩비·슬리피지 적용, 동일 기간·수정 엔진으로 거래량폭증을 재검증해서 비교.',
              '- all 모드의 과도한 집중과 MDD 84~87%를 점검. 랭킹 효과를 분리하려면 rank/all 자본배분·종목상한을 고정한 추가 실험이 필요하다.',
              '- FRVP는 세부 체결/분봉 거래량으로 실제 volume-at-price 재구성 후 재검증. TJR 원본 자막 확보 후 liquidity→BOS/MSS→FVG/OB의 결합·세션 필터는 별도 연구로 추가.',
              '- pandas_ta/TA-Lib 설치 환경과 fallback 정의의 지표 수치 일치 검증. 현재 결과는 명시한 비TA-Lib fallback 실행 결과다.',
              '- 거래량폭증 계좌단위 서킷브레이커·국장/미장 포트폴리오 로테이션·KIS 캐싱은 기존 미완료 과제로 유지.','', '---','']
    path=ROOT/'docs/전략-백테스트-종합.md'; original=path.read_text()
    if '## 13. 보조지표' in original:
        start=original.index('## 13. 보조지표'); end=original.index('## 결론',start)
        original=original[:start]+original[end:]
    original=original.replace('### 다음 (TODO)\n','### 다음 (TODO, §12 당시 — 최신 우선순위는 §13 참고)\n',1)
    original=original.replace('## 결론', '\n'.join(lines)+'\n## 결론',1)
    path.write_text(original)


if __name__=='__main__':
    render()
