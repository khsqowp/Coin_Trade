"""Additional distinct shared-slot unions with risk/holding budgets."""

import json
import subprocess
import sys
from app import crypto_round13_research as r13
from app import crypto_round13_extension as extension
from app import crypto_round12_research as old


def groups():
    return [
        (
            73,
            "운용북 실제 완료거래의 온라인 축소추정 사이징",
            [
                dict(family=n, online_sizing=mode, online_window=window)
                for n in ["volume_spike", "obv_breakout", "donchian"]
                for mode, window in [("win", 40), ("payoff", 40), ("payoff", 80)]
            ]
            + [
                dict(
                    family="volume_spike",
                    or_family=n,
                    online_sizing="payoff",
                    online_window=40,
                )
                for n in ["keltner", "ichimoku", "obv_breakout"]
            ],
        ),
        (
            74,
            "거래량 무반응·신규신호 합집합의 역변동성 위험예산",
            [
                dict(
                    family="volume_spike",
                    or_family=n,
                    sizing="inverse_vol",
                    target_vol=v,
                    weight_cap=0.25,
                )
                for n in ["keltner", "ichimoku", "obv_breakout"]
                for v in [0.8, 1.0, 1.2]
            ],
        ),
        (
            75,
            "거래량 합집합·저변동순위·보유기간 결합",
            [
                dict(family="volume_spike", or_family=n, rank="low_vol", hold_days=h)
                for n in ["keltner", "ichimoku", "obv_breakout"]
                for h in [10, 30, 40]
            ],
        ),
        (
            76,
            "OBV·일봉압축 합집합의 보유기간과 위험예산",
            [
                dict(
                    family="obv_breakout",
                    or_family="compression_breakout",
                    rank="low_vol",
                    hold_days=h,
                )
                for h in [10, 20, 30]
            ]
            + [
                dict(
                    family="obv_breakout",
                    or_family="compression_breakout",
                    sizing="inverse_vol",
                    target_vol=v,
                    weight_cap=0.25,
                )
                for v in [0.8, 1.0, 1.2]
            ],
        ),
    ]


def run():
    frames, manifest, skipped = old.load_data()
    out = json.loads(r13.PATH.read_text())
    assert not skipped and manifest == out["manifest"]
    if out["status"] == "복귀조건 A 달성":
        return
    original_audit = old.audit

    def causal(frames, config, full):
        old.audit = original_audit
        try:
            return extension.audit(frames, config, full)
        finally:
            old.audit = causal

    old.build, old.audit = extension.build, causal
    previous = json.loads(
        (r13.ROOT / "docs/round12-results-2026-10-07.json").read_text()
    )
    used = {json.dumps(r["config"], sort_keys=True) for r in previous["experiments"]}
    planned = [c for _, _, cs in groups() for c in cs]
    assert len({json.dumps(c, sort_keys=True) for c in planned}) == len(planned)
    assert not used & {json.dumps(c, sort_keys=True) for c in planned}
    out["planned_final"] = planned
    out["status"] = "탐색중"
    r13.save(out)
    for section, title, configs in groups():
        if section in out["sections"]:
            continue
        for config in configs:
            r13.execute(out, frames, config)
            if out["status"] == "복귀조건 A 달성":
                break
        with (r13.ROOT / "docs/round13-verification-2026-10-07.txt").open("a") as f:
            subprocess.run(
                [sys.executable, "-m", "app.verify_round13"],
                stdout=f,
                stderr=subprocess.STDOUT,
                check=True,
            )
        r13.write_section(
            out,
            section,
            title,
            [r for r in out["experiments"] if r["config"] in configs],
        )
        if out["status"] == "복귀조건 A 달성":
            return
    out["status"] = "복귀조건 미달성, 계속 진행 필요"
    out["next"] = [
        "운용북 실제완료거래 온라인 사이징",
        "새지표 시간축/횡단면 점수의 결합",
        "ATR기간정규화 채널의 과거변동성순위 결합",
    ]
    r13.save(out)


if __name__ == "__main__":
    run()
