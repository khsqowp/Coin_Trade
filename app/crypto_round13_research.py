"""Round13 continuation. Common engine and Round12 artifacts remain immutable."""

import hashlib
import json
import subprocess
import sys
import numpy as np
import pandas as pd
from app import crypto_round12_research as old
from app.round13_signals import find_signals, FAMILIES, hysteresis
from app.technical_portfolio_engine import simulate_portfolio

ROOT, DOC = old.ROOT, old.DOC
PATH = ROOT / "docs/round13-results-2026-10-07.json"
GITLOG = ROOT / "docs/round13-git-2026-10-07.txt"
BASE_BUILD = old.build


def build(frames, config):
    base = {
        k: v
        for k, v in config.items()
        if k not in ["monthly_trend", "btc_hysteresis", "and_family"]
    }
    if base["family"] in FAMILIES:
        base["family"] = "rebound"
    p, kw, state = BASE_BUILD(frames, base)
    for s, f in p.items():
        raw = frames[s]
        if config["family"] in FAMILIES:
            own = find_signals(raw, config["family"])
            # Replace baseline adapter then reproduce the chosen confirmation.
            signal = own.SIGNAL
            if config.get("volume_confirm"):
                signal &= own.VOL_RATIO >= 1.5
            if config.get("weekly_trend"):
                w = raw.Close.resample("W-SUN").last()
                signal &= (
                    (w > w.rolling(10).mean())
                    .reindex(raw.index, method="ffill")
                    .fillna(False)
                )
            f["SIGNAL"] = signal.reindex(f.index, fill_value=False)
        if config.get("and_family"):
            second = find_signals(raw, config["and_family"]).SIGNAL
            # Confirmation may appear on any of last five completed bars.
            f["SIGNAL"] &= (
                second.rolling(5).max().fillna(0).astype(bool).reindex(f.index)
            )
        if config.get("monthly_trend"):
            m = raw.Close.resample("ME").last()
            allowed = m > m.rolling(6).mean()
            f["SIGNAL"] &= (
                allowed.reindex(raw.index, method="ffill")
                .fillna(False)
                .reindex(f.index)
            )
    if config.get("btc_hysteresis"):
        state = hysteresis(frames["BTC"].Close, config["btc_hysteresis"]).astype(int)
        kw["btc_ok"] = state.astype(bool).to_dict()
    return p, kw, state


def save(out):
    PATH.write_text(
        json.dumps(
            out,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            default=lambda x: x.item() if isinstance(x, np.generic) else str(x),
        )
    )


def groups():
    return [
        (
            64,
            "완료월봉 6개월추세·일봉 압축/거래량 진입",
            [
                dict(family=n, monthly_trend=True, **x)
                for n in [
                    "compression_breakout",
                    "obv_breakout",
                    "dry_pullback",
                    "donchian",
                ]
                for x in [{}, {"rank": "residual"}]
            ],
        ),
        (
            65,
            "Aroon·WilliamsR·Ichimoku·PSAR의 신규 결합",
            [
                dict(family=n, **x)
                for n in FAMILIES[:4]
                for x in [
                    {},
                    {"volume_confirm": True},
                    {"weekly_trend": True, "rank": "residual"},
                ]
            ],
        ),
        (
            66,
            "TRIX·Awesome Oscillator·Keltner 신규 결합",
            [
                dict(family=n, **x)
                for n in FAMILIES[4:]
                for x in [
                    {},
                    {"volume_confirm": True},
                    {"weekly_trend": True, "rank": "residual"},
                ]
            ],
        ),
        (
            67,
            "BTC 200일선 히스테리시스·역변동성 위험배분",
            [
                dict(
                    family=n,
                    btc_hysteresis=w,
                    sizing="inverse_vol",
                    target_vol=1.0,
                    weight_cap=0.25,
                )
                for n in ["donchian", "obv_breakout", "compression_breakout"]
                for w in [0.03, 0.07]
            ],
        ),
        (
            68,
            "독립 신규지표 확인창과 기존 진입의 결합",
            [
                dict(family=n, and_family=a, rank="low_vol")
                for n in ["obv_breakout", "donchian", "dry_pullback"]
                for a in ["aroon", "awesome"]
            ],
        ),
    ]


def git_section(out, section):
    files = [
        "app/round13_signals.py",
        "app/crypto_round13_research.py",
        "app/verify_round13.py",
        "app/crypto_round13_extension.py",
        "app/round13_costs.py",
        str(PATH.relative_to(ROOT)),
        str(DOC.relative_to(ROOT)),
        "docs/round13-verification-2026-10-07.txt",
        "docs/round13-execution-2026-10-07.log",
    ]
    files += [
        str(p.relative_to(ROOT))
        for p in sorted((ROOT / "docs").glob("round13-*-regression-2026-10-07.txt"))
    ]
    files += [
        str(p.relative_to(ROOT))
        for p in [GITLOG, ROOT / "docs/round13-regression-summary-2026-10-07.txt"]
        if p.exists()
    ]
    if (ROOT / "app/crypto_round13_final_batch.py").exists():
        files.append("app/crypto_round13_final_batch.py")
    if (ROOT / "app/round13_adaptive.py").exists():
        files.append("app/round13_adaptive.py")
    if (ROOT / "app/crypto_round13_accept.py").exists():
        files.append("app/crypto_round13_accept.py")
    files += [
        str(p.relative_to(ROOT))
        for p in [
            ROOT / "docs/round13-review-2026-10-07.txt",
            ROOT / "docs/round13-replay-2026-10-07.txt",
        ]
        if p.exists()
    ]
    if (ROOT / "app/crypto_round13_report.py").exists():
        files.append("app/crypto_round13_report.py")
    if (ROOT / "docs/round13-static-2026-10-07.txt").exists():
        files.append("docs/round13-static-2026-10-07.txt")
    events, commit, pushed = [], None, False
    for action, cmd in [
        ("add", ["git", "add", *files]),
        (
            "commit",
            ["git", "commit", "-m", f"research: 라운드13 섹션{section} 신규조합 검증"],
        ),
        ("push", ["git", "push", "origin", "main"]),
    ]:
        for attempt in range(3):
            try:
                result = subprocess.run(
                    cmd, cwd=ROOT, capture_output=True, text=True, timeout=50
                )
                code, message = result.returncode, result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                code, message = 124, "50초 제한 초과"
            events.append(
                dict(action=action, attempt=attempt + 1, code=code, output=message)
            )
            if code == 0:
                if action == "commit":
                    commit = subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                    ).strip()
                if action == "push":
                    pushed = True
                break
        if code:
            break
    record = dict(
        section=section,
        hash=commit,
        pushed=pushed,
        status="성공" if pushed else "푸시 보류" if commit else "커밋 보류",
        attempts=events,
    )
    out["git"].append(record)
    save(out)
    with GITLOG.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    with DOC.open("a") as f:
        f.write(
            f'\n- Git §{section}: {record["status"]}, 해시 {commit or "없음"}; 최초+2회 재시도 로그: round13-git-2026-10-07.txt.\n'
        )


def write_section(out, section, title, rows):
    with DOC.open("a") as f:
        f.write(f"\n\n## {section}. {title} (2026-10-07, 라운드13)\n\n")
        f.write(
            "- §63의45종목 캐시와 기간·그로스 기준을 그대로 유지한다. 기본 TOP_K8·20일 보유·다음날 시가·편도수수료0.04%·손절없음. technical_portfolio_engine 변경 없음. 정확한 config는 Round12 127개와 대조하고 중복을 금지했다. 신규 일봉 신호 비교이며 원전략 네이티브 성과 재현이 아니다.\n"
        )
        f.write(
            "- 완료월봉=UTC 월말종가>6개월평균, 월말 이후 forward-fill만 사용. Aroon26봉최고/최저위치(0~25)×4의상향교차·상방70이상; Williams14의−80상향회복; Ichimoku9/26/52·구름26봉후방조회·Tenkan>Kijun·구름상향돌파(Chikou 미사용); PSAR0.02/0.02/0.2 상승전환; TRIX15의3중EMA변화율0상향교차; AO5/34중간가격평균차0상향교차; Keltner EMA20+ATR20×2 상향교차. Ichimoku78봉, 다른 신규지표200봉 워밍업·SMA200상방.\n"
        )
        f.write(
            "- BTC 히스테리시스=200일평균대비 지정폭 상방에서 ON·하방에서 OFF·밴드내 이전상태유지. 결합확인창=두번째신호가 최근5완료봉에 존재. 모든조합에서 전체45종목prefix·미래가격3배/거래량7배변조·실행prefix·전일정보진입 검사. 강건성은 Round12의5검사 전부를 재사용한다.\n\n| config | CAGR | MDD | Sharpe | 거래 | 판정 |\n|---|---:|---:|---:|---:|---|\n"
        )
        for row in rows:
            m = row["metrics"]
            f.write(
                f'| {json.dumps(row["config"],ensure_ascii=False)} | {m["cagr"]:+.6f}% | {m["mdd"]:.6f}% | {m["sharpe"]:.6f} | {m["trades"]} | {row.get("robustness",{}).get("verdict","세축미달 기각")} |\n'
            )
            if row["dominates"]:
                r = row["robustness"]
                f.write(
                    f'\n- 강건성 {row["config"]}: 알파기간 {sum(x["alpha"]>0 for x in r["periods"])}/8·Round4/6 {sum(x["alpha"]>0 for x in r["legacy_periods"])}/8; 상위10건 {r["concentration"]["10"]["net_pct"]:.6f}%·5종목 {r["symbols"]["net_pct"]:.6f}%; 랜덤300회 {r["monte_carlo"]["tests"]}; 20거래블록1000회95%CI {r["bootstrap"]["ci95"]}; 스래싱 {r["thrashing"]["within"]["5"]["pct"] if r["thrashing"] else "전환없음"}; 5검사 {r["votes"]} → {r["verdict"]}. 거래단위CI는 일별NAV Sharpe CI가 아니다.\n'
                )
        f.write(
            f'\n- 신규 {len(rows)}조합; 세축우위 {sum(r["dominates"] for r in rows)}개; 전체통과 {sum(r.get("robustness",{}).get("verdict")=="통과" for r in rows)}개. 저장JSON에 실제수치·원장·표본·신호수·인과검사를 보존했다.\n'
        )
    out["sections"].append(section)
    save(out)
    git_section(out, section)


def required_gates(result):
    """Apply this request's Round4/6 calendar, preserving the extra-calendar vote."""
    result.setdefault(
        "round12_extra_gate",
        dict(votes=list(result["votes"]), verdict=result["verdict"]),
    )
    result["round9_supplemental_positive"] = sum(
        p["alpha"] > 0 for p in result["periods"]
    )
    result["period_criterion"] = (
        "사용자 지정 Round4/6 경계 8구간 중 알파양수 7/8 이상; Round9 별도8구간은 참고"
    )
    result["votes"][0] = sum(p["alpha"] > 0 for p in result["legacy_periods"]) >= 7
    result["verdict"] = "통과" if all(result["votes"]) else "기각"
    return result


def execute(out, frames, config):
    if any(row["config"] == config for row in out["experiments"]):
        return
    p, kw, state = old.build(frames, config)
    full = simulate_portfolio(p, return_trace=True, **kw)
    metrics = old.summary(full)
    assert np.isfinite(list(metrics.values())).all() and 0 <= metrics["mdd"] <= 100
    assert full["start"].startswith("2019-09-08") and full["end"].startswith(
        "2026-10-05"
    )
    baseline = out["baseline"]
    dominates = (
        metrics["cagr"] > baseline["cagr"]
        and metrics["mdd"] < baseline["mdd"]
        and metrics["sharpe"] > baseline["sharpe"]
    )
    row = dict(
        phase=3,
        config=config,
        metrics=metrics,
        dominates=bool(dominates),
        signal_count=sum(int(f.SIGNAL.sum()) for f in p.values()),
        causal_checks=old.audit(frames, config, full),
    )
    if dominates:
        row["robustness"] = required_gates(old.robustness(p, kw, state, full))
        if row["robustness"]["verdict"] == "통과":
            # Preserve the verified winner before cost adapter work.
            out["status"] = "복귀조건 A 달성"
            out["experiments"].append(row)
            save(out)
            from app.round13_costs import simulate_cost_portfolio

            zero = simulate_cost_portfolio(p, **kw)
            for key, value in metrics.items():
                np.testing.assert_allclose(zero[key], value, rtol=0, atol=1e-10)
            row["costs"] = [
                dict(
                    funding_annual=0.1095,
                    slippage=slip,
                    metrics=old.summary(
                        simulate_cost_portfolio(
                            p, funding_annual=0.1095, slippage=slip, **kw
                        )
                    ),
                )
                for slip in [0.0005, 0.001]
            ]
            save(out)
            print("WINNER", config, metrics, flush=True)
            return
    out["experiments"].append(row)
    save(out)
    print(
        "RESULT", config, metrics, row.get("robustness", {}).get("verdict"), flush=True
    )


def run():
    frames, manifest, skipped = old.load_data()
    previous = json.loads(old.PATH.read_text())
    assert not skipped and manifest == previous["manifest"]
    out = (
        json.loads(PATH.read_text())
        if PATH.exists()
        else dict(
            manifest=manifest,
            baseline=previous["baseline"],
            experiments=[],
            sections=[],
            git=[],
            status="탐색중",
        )
    )
    if out["status"] == "복귀조건 A 달성":
        return
    old.build = build  # only this process; legacy source remains unchanged
    old.PATH, old.save = PATH, save
    configs = [c for _, _, cs in groups() for c in cs]
    keys = [json.dumps(c, sort_keys=True) for c in configs]
    assert len(keys) == len(set(keys))
    assert not set(keys) & {
        json.dumps(r["config"], sort_keys=True) for r in previous["experiments"]
    }
    out["planned"] = configs
    save(out)
    for section, title, configs in groups():
        if section in out["sections"]:
            continue
        for config in configs:
            execute(out, frames, config)
            if out["status"] == "복귀조건 A 달성":
                break
        with (ROOT / "docs/round13-verification-2026-10-07.txt").open("a") as f:
            subprocess.run(
                [sys.executable, "-m", "app.verify_round13"],
                stdout=f,
                stderr=subprocess.STDOUT,
                check=True,
            )
        write_section(
            out,
            section,
            title,
            [r for r in out["experiments"] if r["config"] in configs],
        )
        if out["status"] == "복귀조건 A 달성":
            return
    out["status"] = "복귀조건 미달성, 계속 진행 필요"
    out["next"] = [
        "실제 완료거래 승률·페이오프 축소추정 사이징",
        "OBV·일봉압축의 보유기간/추세 히스테리시스 결합",
        "완료주봉 Ichimoku·Keltner 확인과 일봉체결",
    ]
    save(out)


if __name__ == "__main__":
    run()
