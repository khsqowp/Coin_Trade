"""Additional predeclared Round12 combinations after sections39-52."""
import json
from app.crypto_round12_research import PATH, DOC, ROOT, save, execute, verify_and_section, git_section
from app.crypto_technical_ict_research import load_data


def groups():
    return [
        (53, 'BTC추세·역변동성의 위험예산 변경',
         [dict(family=n, btc_trend=True, sizing='inverse_vol', target_vol=v, weight_cap=.25)
          for n in ['mach7', 'donchian', 'gap'] for v in [.8, 1., 1.2]]),
        (54, '완료주봉·자체추세·거래량 지속성',
         [dict(family=n, weekly_trend=True, persistence=True)
          for n in ['mach7', 'donchian', 'gap', 'rebound', 'compression_breakout']]),
        (55, '횡단면 BTC잔차강도 순위',
         [dict(family=n, rank='residual', **x) for n in ['mach7', 'donchian', 'gap', 'compression_breakout']
          for x in [{}, {'btc_trend':True}]]),
        (56, '하방변동성순위·추세·압축',
         [dict(family=n, rank='downside', self_trend=True)
          for n in ['mach7', 'donchian', 'gap', 'rebound', 'compression_breakout']]),
        (57, '새 진입축: 거래량건조·OBV·잔차반등',
         [dict(family=n, **x) for n in ['dry_pullback', 'obv_breakout', 'residual_rebound']
          for x in [{}, {'weekly_trend':True, 'volume_confirm':True}, {'btc_trend':True, 'rank':'residual'}]]),
    ]


def run():
    frames, manifest, skipped = load_data()
    out = json.loads(PATH.read_text())
    assert not skipped and manifest == out['manifest']
    if out['status'] == '복귀조건 A 달성':
        return
    out['status'] = '탐색중'
    save(out)
    for section, title, configs in groups():
        if section in out['sections']:
            continue
        for config in configs:
            execute(out, frames, 2, config)
            if out['status'] == '복귀조건 A 달성':
                break
        rows = [r for r in out['experiments'] if r['phase'] == 2 and r['config'] in configs]
        verify_and_section(out, section, title, rows)
        if out['status'] == '복귀조건 A 달성':
            return
    out['status'] = '복귀조건 미달성, 계속 진행 필요'
    out['next'] = ['완료월봉과 일봉압축 결합', '과거완료거래 승률 축소추정 사이징',
                   'CCI/CMF/Aroon 등 미소진 레포 신호군의 일봉 로테이션',
                   '채널돌파·거래량건조의 변동성 상태별 보유기간 결합']
    save(out)
    if 58 not in out['sections']:
        with DOC.open('a') as f:
            f.write('\n\n## 58. 라운드12 추가탐색 후 재개 지점 (2026-10-07)\n\n')
            f.write(f'- §52를 이어 추가 {sum(len(c) for _, _, c in groups())}개 신규조합 설계·실행. 1단계 {sum(r["phase"] == 1 for r in out["experiments"])}조합, 2단계 {sum(r["phase"] == 2 for r in out["experiments"])}조합, 총 {len(out["experiments"])}조합.\n')
            f.write(f'- 세축우위 {sum(r["dominates"] for r in out["experiments"])}개, 5검증 전부통과 {sum(r.get("robustness", {}).get("verdict") == "통과" for r in out["experiments"])}개. 미비용 챔피언은 그대로 비교기준이며 비용민감성은 §29를 참조한다.\n')
            f.write('- **복귀조건 미달성, 계속 진행 필요.** 최소20개는 탐색량 조건이지 아이디어소진의 증거가 아니다. 아직 '+ ' / '.join(out['next'])+'을 실행하지 않았으므로 B 달성을 선언하지 않는다. §59부터 이어서 실행하며 원시JSON의 정확한 config 중복을 금지한다.\n')
            f.write('- 완료한 조합은 원시JSON, 실행로그, 검증로그에 보존했다. §52는 당시 체크포인트이고 최신집계는 본섹션이다. Git 쓰기제한은 연구실행과 별개다.\n')
        out['sections'].append(58)
        save(out)
        git_section(out, 58)
    print(out['status'], flush=True)


if __name__ == '__main__':
    run()
