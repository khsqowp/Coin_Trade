"""Predeclared continuation: reference-ledger estimates and weekly indicators."""

import json
import subprocess
import sys
import numpy as np
import pandas as pd
from app import crypto_round13_research as r13
from app import crypto_round12_research as old
from app.round13_signals import find_signals
from app.crypto_round4_robustness import ledger_run

BASE_BUILD = r13.build


def shrink_scales(p, kw, mode, window=40):
    # The equal-sized reference book executes real trades in the common engine.
    # Estimates train on its completed trades, never on open positions.
    _, records, _, dates, _ = ledger_run(p, kw)
    ordered = sorted(records, key=lambda t: (t["exit"], t["id"]))
    cursor, completed, values = 0, [], {}
    for i, date in enumerate(dates):
        while cursor < len(ordered) and ordered[cursor]["exit"] <= i:
            completed.append(ordered[cursor]["return_pct"] / 100)
            cursor += 1
        recent = np.asarray(completed[-window:])
        positive, negative = recent[recent > 0], -recent[recent <= 0]
        probability = (len(positive) + 10) / (len(recent) + 20)
        if mode == "win":
            scale = np.clip((probability - 0.35) / 0.25, 0.25, 1.0)
        else:
            win = (positive.sum() + 0.2) / (len(positive) + 10)
            loss = (negative.sum() + 0.2) / (len(negative) + 10)
            payoff = win / loss
            edge = probability - (1 - probability) / payoff
            scale = 0.25 + 0.75 * np.clip(edge / 0.25, 0, 1)
        values[date] = float(scale)
    return values


def build(frames, config):
    clean = {
        k: v
        for k, v in config.items()
        if k
        not in [
            "shrink_sizing",
            "shrink_window",
            "weekly_indicator",
            "or_family",
            "online_sizing",
            "online_window",
        ]
    }
    if clean["family"] == "volume_spike":
        clean["family"] = "rebound"
    p, kw, state = BASE_BUILD(frames, clean)
    if config["family"] == "volume_spike":
        bank = old.volume_prep(frames)
        for s, f in p.items():
            f["SIGNAL"] = bank[s].SIGNAL.reindex(f.index)
            # Retain ATR and structure from common signal fields, unlike baseline's zeros.
    if config.get("or_family"):
        for s, f in p.items():
            extra = find_signals(frames[s], config["or_family"]).SIGNAL
            f["SIGNAL"] |= extra.reindex(f.index, fill_value=False)
    # Apply the slow regime AFTER replacing/combining entry legs.
    if config.get("monthly_trend"):
        for s, f in p.items():
            m = frames[s].Close.resample("ME").last()
            mask = m > m.rolling(6).mean()
            f["SIGNAL"] &= mask.reindex(f.index, method="ffill").fillna(False)
    if config.get("weekly_indicator"):
        for s, f in p.items():
            w = (
                frames[s]
                .resample("W-SUN")
                .agg(
                    dict(
                        Open="first", High="max", Low="min", Close="last", Volume="sum"
                    )
                )
                .dropna()
            )
            weekly = find_signals(w, config["weekly_indicator"]).SIGNAL
            # Weekly confirmation persists for four completed weeks.
            mask = weekly.rolling(4).max().fillna(0).astype(bool)
            f["SIGNAL"] &= mask.reindex(f.index, method="ffill").fillna(False)
    if config.get("shrink_sizing"):
        kw["entry_scale"] = shrink_scales(
            p, kw, config["shrink_sizing"], config.get("shrink_window", 40)
        )
    if config.get("online_sizing"):
        from app.round13_adaptive import CompletedTradeScale

        kw["entry_scale"] = CompletedTradeScale(
            config["online_sizing"], config.get("online_window", 40)
        )
    return p, kw, state


def audit(frames, config, full):
    result = old.audit(frames, config, full)
    if config.get("shrink_sizing"):
        cutoff = pd.Timestamp("2024-06-30", tz="UTC")
        prefix = {s: f.loc[:cutoff] for s, f in frames.items() if len(f.loc[:cutoff])}
        _, a, _ = build(frames, config)
        _, b, _ = build(prefix, config)
        # Prefix's forced terminal liquidation affects only its terminal scale,
        # which is never read by any prefix entry. All executable scales match.
        for date, value in b["entry_scale"].items():
            if date < cutoff:
                np.testing.assert_allclose(
                    a["entry_scale"][date], value, rtol=0, atol=1e-12
                )
        result["completed_reference_scale_prefix"] = True
    return result


def groups():
    return [
        (
            69,
            "완료 기준거래 승률·페이오프 축소추정 사이징",
            [
                dict(family=n, shrink_sizing=mode, shrink_window=window)
                for n in [
                    "obv_breakout",
                    "donchian",
                    "compression_breakout",
                    "volume_spike",
                ]
                for mode, window in [("win", 40), ("payoff", 40), ("payoff", 80)]
            ],
        ),
        (
            70,
            "완료주봉 Ichimoku·Keltner 확인과 일봉체결",
            [
                dict(family=n, weekly_indicator=w)
                for n in ["obv_breakout", "donchian", "compression_breakout", "gap"]
                for w in ["ichimoku", "keltner"]
            ],
        ),
        (
            71,
            "거래량 무반응·신규지표 합집합의 슬롯공유",
            [
                dict(family="volume_spike", or_family=n, **x)
                for n in ["keltner", "ichimoku", "obv_breakout"]
                for x in [
                    {"rank": "low_vol"},
                    {"monthly_trend": True},
                    {"btc_hysteresis": 0.03},
                ]
            ],
        ),
        (
            72,
            "OBV·압축돌파 히스테리시스와 보유기간",
            [
                dict(
                    family=n,
                    btc_hysteresis=0.03,
                    sizing="inverse_vol",
                    target_vol=1.0,
                    weight_cap=0.25,
                    hold_days=h,
                )
                for n in ["obv_breakout", "compression_breakout"]
                for h in [10, 30, 40]
            ],
        ),
    ]


def run():
    frames, manifest, skipped = old.load_data()
    out = json.loads(r13.PATH.read_text())
    assert manifest == out["manifest"] and not skipped
    if out["status"] == "복귀조건 A 달성":
        return
    old.build, old.PATH, old.save = build, r13.PATH, r13.save
    original_audit = old.audit

    # audit wrapper calls the original implementation without recursion.
    def causal(frames, config, full):
        old.audit = original_audit
        try:
            return audit(frames, config, full)
        finally:
            old.audit = causal

    old.audit = causal
    previous = json.loads(
        (r13.ROOT / "docs/round12-results-2026-10-07.json").read_text()
    )
    used = {
        json.dumps(r["config"], sort_keys=True)
        for r in previous["experiments"] + out["experiments"]
    }
    planned = [c for _, _, cs in groups() for c in cs]
    assert len({json.dumps(c, sort_keys=True) for c in planned}) == len(planned)
    assert all(
        json.dumps(c, sort_keys=True) not in used
        or any(r["config"] == c for r in out["experiments"])
        for c in planned
    )
    out["planned_extension"] = planned
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
        with r13.DOC.open("a") as f:
            f.write(
                "\n- 다음 섹션 추가정의: 축소추정은 공통엔진의 동일 신호·보유기간 기준북에서 실제 완료한 거래의 수수료후 수익률만 사용한다. 운용북 자신의 거래로 학습하는 정책은 아니다. 마지막40/80건·승률 Beta(10,10), 평균이익/손실은 각각 가상10건×2%로 축소한다. 승률모드 scale=clip((p−0.35)/0.25,0.25,1); 페이오프모드 scale=0.25+0.75×clip((p−(1−p)/b)/0.25,0,1). 당일종가 완료거래는 익일시가부터 사용한다. 새기간에도 이전 기준북의 완료이력은 지표 워밍업으로 유지된다. 완료주봉 지표는 일봉 공식을 주봉OHLCV에 적용하고 최근4완료주 중 신호존재를 확인한다. Keltner의200주 워밍업은 의도적으로 유지한다. 합집합은 자본분리가 아니라 공통슬롯에서 단일순위로 경쟁한다.\n"
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
        "운용북 자체 완료거래의 온라인 학습 사이징",
        "거래량 무반응 합집합의 역변동성 위험예산",
        "추세 신호의 변동성 수축/확장에 따른 순위 결합",
    ]
    r13.save(out)


if __name__ == "__main__":
    run()
