"""Resumable Round14 search; immutable prior artifacts and definition Y only."""

import json
import subprocess
import numpy as np
from app import crypto_round12_research as old
from app.crypto_round13_extension import build, audit
from app.technical_portfolio_engine import simulate_portfolio
from app.round14_validation import robustness
from app.round_period_standard import ALPHA_PERIODS, PERIOD_STANDARD, assert_standard

ROOT = old.ROOT
PATH = ROOT / "docs/round14-results-2026-10-07.json"
DOC = old.DOC
LOG = ROOT / "docs/round14-git-2026-10-07.txt"


def save(out: dict) -> None:
    PATH.write_text(
        json.dumps(
            out,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            default=lambda x: x.item() if isinstance(x, np.generic) else str(x),
        )
    )


def git_section(out: dict, section: int) -> None:
    files = [
        "app/round_period_standard.py",
        "app/crypto_round8_research.py",
        "app/crypto_round13_research.py",
        "app/crypto_round13_accept.py",
        "app/crypto_round9_research.py",
        "app/crypto_round10_research.py",
        "app/crypto_round11_research.py",
        "app/crypto_round12_research.py",
        "app/verify_round14.py",
        "app/round14_validation.py",
        "app/crypto_round14_research.py",
        "app/crypto_round14_report.py",
        str(PATH.relative_to(ROOT)),
        str(DOC.relative_to(ROOT)),
    ]
    files += [
        str(p.relative_to(ROOT)) for p in sorted((ROOT / "docs").glob("round14-*.txt"))
    ]
    events = []
    commit = None
    pushed = False
    for action, cmd in [
        ("add", ["git", "add", *files]),
        (
            "commit",
            ["git", "commit", "-m", f"연구: 라운드14 섹션{section} 정의Y 고정 및 검증"],
        ),
        ("push", ["git", "push", "origin", "main"]),
    ]:
        for attempt in range(3):
            try:
                r = subprocess.run(
                    cmd, cwd=ROOT, capture_output=True, text=True, timeout=50
                )
                code, message = r.returncode, r.stdout + r.stderr
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
    with LOG.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    with DOC.open("a") as f:
        f.write(
            f'\n- Git §{section}: {record["status"]}, 해시 {commit or "없음"}; 최초+2회 재시도: round14-git-2026-10-07.txt.\n'
        )


def initialize() -> dict:
    if PATH.exists():
        return json.loads(PATH.read_text())
    prior = json.loads((ROOT / "docs/round13-results-2026-10-07.json").read_text())
    winner = next(
        r for r in prior["experiments"] if r["config"] == prior["winner_config"]
    )
    b = winner["robustness"]
    assert_standard(b["periods"])
    assert sum(p["alpha"] > 0 for p in b["periods"]) == 6
    votes = list(b["votes"])
    votes[0] = False
    out = dict(
        status="탐색중",
        period_standard=PERIOD_STANDARD,
        periods=ALPHA_PERIODS,
        manifest=prior["manifest"],
        baseline=prior["baseline"],
        experiments=[],
        sections=[76],
        git=[],
        round13_reassessment=dict(
            config=winner["config"],
            metrics=winner["metrics"],
            periods=b["periods"],
            votes=votes,
            verdict="기각",
            source="round13-results-2026-10-07.json; §74",
            failed=[p for p in b["periods"] if p["alpha"] <= 0],
        ),
    )
    save(out)
    with DOC.open("a") as f:
        f.write(
            "\n\n## 76. 기간분리 8구간 기준 통일 및 §74 후보 재판정 (2026-10-07, 라운드14)\n\n**§74 후보 기각 확정 — 정의Y(실제 2년 8구간) 기준 6/8 미달**\n\n"
        )
        f.write(
            "- 정의X는 §16/§18·Round4/6의 광역분할2개+롤링6개다. 정의Y는 Round8 코드에서 출발해 Round9 및 Round10~12에 재사용된 순수2년8개다. §74는 X의7/8을 채택하고 Y의6/8을 참고로 내려 승인을 선언했다. 이는 완화 없음 요구와 불일치하며 §74/§75의 승인·발견 결론을 철회한다. 원문과 원JSON은 역사적 증거로 보존하고 이 섹션과 Round14 JSON이 최종 재판정을 기록한다.\n"
        )
        f.write(
            "- app/round_period_standard.py의 불변 ALPHA_PERIODS를 유일 기준으로 고정했다. Round8이 직접 import하고 Round13 판정기도 정의Y만 사용한다. 폐기된 Round13 승인 실행기는 재승인을 차단한다. Round14 검증은 X를 읽거나 추가표로 평가하지 않으며 경계 순서까지 assert한다. 이전 라운드 회귀는 역사적 결과 재현이며 신규 승인으로 사용하지 않는다.\n\n| 정의Y 구간 | 전략 CAGR | BTC CAGR | 알파 | 결과 |\n|---|---:|---:|---:|---|\n"
        )
        for p in b["periods"]:
            f.write(
                f'| {p["start"]}~{p["end"]} | {p["metrics"]["cagr"]:.6f}% | {p["btc_cagr"]:.6f}% | {p["alpha"]:.6f}%p | {"통과" if p["alpha"]>0 else "실패"} |\n'
            )
        f.write(
            "- 2022-09-08~2024-09-07 및 2023-10-06~2025-10-05 실패로 6/8. 나머지4검사 통과 여부가 기간미달을 상쇄하지 않는다. 최종5표=[False,True,True,True,True], 기각. 복귀조건A/B 모두 미달성에서 탐색 재개한다.\n"
        )
    git_section(out, 76)
    return out


def plans() -> list[dict]:
    base = dict(
        family="donchian",
        btc_hysteresis=0.03,
        sizing="inverse_vol",
        target_vol=1.0,
        weight_cap=0.25,
    )
    # Holding horizon controls realized breakout payoff, ranking controls slot competition.
    configs = [
        dict(base, hold_days=h) for h in [12, 15, 18, 22, 25, 28, 30, 35, 40, 50, 60]
    ]
    configs += [
        dict(base, hold_days=h, rank=rank)
        for rank in ["low_vol", "residual", "relative_strength", "downside"]
        for h in [15, 25, 30]
    ]
    configs += [
        dict(base, params={"lookback": l}, hold_days=h)
        for l in [20, 35, 70, 90]
        for h in [15, 25, 35]
    ]
    configs += [
        dict(base, btc_hysteresis=w, hold_days=h)
        for w in [0.01, 0.05, 0.10]
        for h in [15, 25, 35]
    ]
    return configs


def run() -> None:
    out = initialize()
    if out["status"] == "복귀조건 A 달성":
        return
    frames, manifest, skipped = old.load_data()
    assert manifest == out["manifest"] and not skipped
    old.build = build
    prior_keys = {
        json.dumps(r["config"], sort_keys=True)
        for n in [12, 13]
        for r in json.loads(
            (ROOT / f"docs/round{n}-results-2026-10-07.json").read_text()
        )["experiments"]
    }
    for config in plans():
        key = json.dumps(config, sort_keys=True)
        assert key not in prior_keys
        if any(r["config"] == config for r in out["experiments"]):
            continue
        p, kw, state = build(frames, config)
        full = simulate_portfolio(p, return_trace=True, **kw)
        m = old.summary(full)
        b = out["baseline"]
        dominates = (
            m["cagr"] > b["cagr"] and m["mdd"] < b["mdd"] and m["sharpe"] > b["sharpe"]
        )
        row = dict(
            config=config,
            metrics=m,
            dominates=bool(dominates),
            causal_checks=audit(frames, config, full),
        )
        assert all(row["causal_checks"].values())
        if dominates:
            row["robustness"] = robustness(p, kw, state, full)
        out["experiments"].append(row)
        if row.get("robustness", {}).get("verdict") == "통과":
            out["status"] = "복귀조건 A 달성"
            out["winner_config"] = config
        save(out)
        print(
            "RESULT",
            len(out["experiments"]),
            config,
            m,
            row.get("robustness", {}).get("votes"),
            flush=True,
        )
        if out["status"] == "복귀조건 A 달성":
            return
    out["status"] = "복귀조건 미달성, 계속 진행 필요"
    out["next"] = [
        "완료월봉·주봉 확인과 압축/OBV 결합",
        "실제 완료거래 축소추정 사이징과 신규돌파기간 결합",
        "추가 신호군/변동성추세 예산: 아이디어 소진 미확인",
    ]
    save(out)


if __name__ == "__main__":
    run()
