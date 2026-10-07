"""Predeclared Round16 proxy research; existing portfolio engines only.

Run python3.12 -m app.crypto_round16_liquidation_research. Resume uses exact grid,
cache hashes and saved results. All four gates AND Bonferroni AND full BH required.
500 random-entry trials have finite resolution; no p=0 or post-hoc grid changes.
"""

import itertools
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

import numpy as np
import pandas as pd
from app.liquidation_proximity_signal_core import find_signals, TIER_SETS
from app.crypto_technical_ict_research import ROOT, load_data
from app.crypto_bucket_ensemble_research import volume_prep
from app.crypto_round8_research import core, aggregate, resolved
from app.crypto_round13_extension import build as donor_build
from app.crypto_round7_research import summary, random_data
from app.crypto_round4_robustness import concentration
from app.crypto_round6_research import btc_period, symbols
from app.round_period_standard import PERIOD_STANDARD, ALPHA_PERIODS, alpha_pass
from app.technical_portfolio_engine import (
    prepare,
    simulate_portfolio,
    simulate_research_portfolio,
)

PATH = ROOT / "docs/round16-results-2026-10-08.json"
DOC = ROOT / "docs/전략-백테스트-종합.md"
START = pd.Timestamp("2019-09-08", tz="UTC")
MC_N = 500
DONCHIAN = dict(
    family="donchian",
    params={"lookback": 70},
    btc_hysteresis=0.03,
    sizing="inverse_vol",
    target_vol=1.0,
    weight_cap=0.25,
    hold_days=25,
)
FAMILIES = (
    "heikin_ashi",
    "frvp",
    "volume",
    "vwap",
    "fvg",
    "fibonacci",
    "ema_cross",
    "liquidity_sweep",
    "elliott_wave",
    "donchian",
)


def save(out: dict) -> None:
    """Atomic artifact replacement, strict JSON without NaN."""
    temp = PATH.with_suffix(".tmp")
    temp.write_text(
        json.dumps(
            out,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            default=lambda v: v.item() if isinstance(v, np.generic) else str(v),
        )
    )
    temp.replace(PATH)


def plans() -> list[dict]:
    """Every executed performance configuration, including unchanged controls."""
    rows: list[dict] = [dict(variant="reference", family="volume")]
    rows += [dict(variant="control_C", family=f) for f in FAMILIES]
    rows += [dict(variant="control_D", hold_days=h) for h in (10, 20)]
    for t, w, threshold in itertools.product(
        range(2), (7, 14, 30), (1.0, 2.0, 3.0, 5.0)
    ):
        common = dict(tier_set=t, window=w, threshold=threshold)
        rows += [
            dict(common, variant=v, hold_days=h)
            for v, h in itertools.product(("A", "B", "D"), (10, 20))
        ]
        rows += [dict(common, variant="C", family=f) for f in FAMILIES]
    assert len(rows) == 397
    assert len({json.dumps(r, sort_keys=True) for r in rows}) == len(rows)
    return rows


def donors(frames: dict) -> tuple:
    """§21 single-family representatives plus §77, keeping their original exits."""
    representatives = aggregate()[-1]
    bank, provenance = {}, {}
    allowed = (
        "timing",
        "stop",
        "tp",
        "hold_days",
        "selection",
        "dd_trigger",
        "resume_mode",
        "cooldown_days",
        "sizing",
        "target_vol",
        "weight_cap",
    )
    for family in FAMILIES:
        if family == "donchian":
            p, kw, _ = donor_build(frames, DONCHIAN)
            provenance[family] = dict(source="§77", config=DONCHIAN)
        else:
            rep = next(r for r in representatives if r["family"] == family)
            config = rep["config"]
            p = (
                volume_prep(frames, multiple=config.get("volume_multiple", 3.0))
                if family == "volume"
                else core(family, frames)
            )
            kw = resolved(
                {k: v for k, v in config.items() if k in allowed and v is not None},
                frames,
            )
            provenance[family] = dict(
                source="§21", config=config, source_files=rep["sources"]
            )
        bank[family] = ({s: f.loc[START:].copy() for s, f in p.items()}, kw)
    return bank, provenance


def setup(config: dict, frames: dict, bank: dict, proxy: dict, volume: dict) -> tuple:
    """C uses technical engine; A/B/D use the existing Round11 research engine."""
    variant = config["variant"]
    if variant in ("C", "control_C"):
        p, basekw = bank[config["family"]]
        p = {s: f.copy() for s, f in p.items()}
        kw, engine = dict(basekw), "technical"
    else:
        p = {s: f.loc[START:].copy() for s, f in volume.items()}
        kw, engine = dict(hold_days=config.get("hold_days", 20)), "research"
    if variant in ("A", "B", "C", "D"):
        for s, f in p.items():
            q = proxy[config["tier_set"], config["window"]][s].reindex(f.index)
            near = q.DOWN_DISTANCE.le(config["threshold"])
            if variant == "A":
                f["SIGNAL"] = near
                f["VOL_RATIO"] = q.VOL_RATIO
            elif variant == "B":
                f["SIGNAL"] &= near
            elif variant == "D":
                momentum = (
                    frames[s].Close.pct_change(30, fill_method=None).reindex(f.index)
                )
                f["SIGNAL"] = momentum.gt(0)
                # Fixed bonus doubles positive momentum rank for downside proximity.
                f["VOL_RATIO"] = momentum * np.where(near, 2.0, 1.0)
            if variant in ("A", "C"):
                f["EXIT_SIGNAL"] = q.UP_DISTANCE.le(config["threshold"])
    if variant == "control_D":
        for s, f in p.items():
            momentum = frames[s].Close.pct_change(30, fill_method=None).reindex(f.index)
            f["SIGNAL"], f["VOL_RATIO"] = momentum.gt(0), momentum
    data = prepare(p)
    if variant in ("A", "C"):
        kw["exit_signals"] = np.array(
            [
                p[s].EXIT_SIGNAL.reindex(data[0], fill_value=False).to_numpy(float)
                for s in data[1]
            ]
        ).T
    return p, data, kw, engine


def execute(p: dict, data: tuple, kw: dict, engine: str, trace: bool = False) -> dict:
    """Dispatch to existing account frameworks."""
    fn = simulate_portfolio if engine == "technical" else simulate_research_portfolio
    return fn(p, prepared=data, return_trace=trace, **kw)


def bootstrap(equity: list, years: float) -> dict:
    """Daily NAV Sharpe CI: circular moving blocks of 20 days, 1000 draws."""
    returns = pd.Series(equity).pct_change().dropna().to_numpy()
    rng = np.random.default_rng(160000)
    draws = []
    for _ in range(1000):
        starts = rng.integers(0, len(returns), int(np.ceil(len(returns) / 20)))
        idx = (starts[:, None] + np.arange(20)).ravel()[: len(returns)] % len(returns)
        sample = returns[idx]
        draws.append(
            float(sample.mean() / sample.std(ddof=1) * np.sqrt(365))
            if sample.std(ddof=1) > 0
            else 0.0
        )
    return dict(
        unit="daily_NAV",
        block_days=20,
        iterations=1000,
        seed=160000,
        ci95=np.percentile(draws, [2.5, 97.5]).tolist(),
        samples=draws,
    )


_MC_CONTEXT: tuple | None = None


def _mc_initialize(
    p: dict, data: tuple, kw: dict, engine: str, probability: float
) -> None:
    """Each spawned worker receives one immutable candidate context."""
    global _MC_CONTEXT
    _MC_CONTEXT = (p, data, kw, engine, probability)


def _mc_trial(index: int) -> dict:
    """Fixed seeds preserve results regardless of worker scheduling."""
    assert _MC_CONTEXT is not None
    p, data, kw, engine, probability = _MC_CONTEXT
    seed = 1600000 + index
    return dict(
        seed=seed,
        **summary(execute(p, random_data(data, seed, probability), kw, engine)),
    )


def robustness(p: dict, data: tuple, kw: dict, engine: str, full: dict) -> dict:
    """All four required gates, never short-circuited on an early failure."""
    rows = []
    for start, end in ALPHA_PERIODS:
        mask = np.array(
            [
                pd.Timestamp(start, tz="UTC") <= d <= pd.Timestamp(end, tz="UTC")
                for d in data[0]
            ]
        )
        dates = [d for d, yes in zip(data[0], mask) if yes]
        subdata = (dates, data[1], {k: a[mask] for k, a in data[2].items()})
        subkw = dict(kw)
        if "exit_signals" in kw:
            subkw["exit_signals"] = kw["exit_signals"][mask]
        # Keep historical indicator/volatility warmup; prepared dates reset the account.
        sub = p
        m = execute(sub, subdata, subkw, engine)
        b = btc_period(p["BTC"], start, end)
        rows.append(
            dict(
                start=start,
                end=end,
                metrics=summary(m),
                btc_cagr=b["cagr"],
                alpha=m["cagr"] - b["cagr"],
            )
        )
    records = full["records"]
    np.testing.assert_allclose(
        sum(r["pnl"] for r in records), full["final"] - 1, atol=1e-8
    )
    conc, sy = concentration(records), symbols(records)
    eligible = np.isfinite(data[2]["Open"][:-1]) & np.isfinite(data[2]["Open"][1:])
    probability = len(records) / eligible.sum()
    trials = []
    with ProcessPoolExecutor(
        max_workers=4,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=_mc_initialize,
        initargs=(p, data, kw, engine, float(probability)),
    ) as pool:
        for trial in pool.map(_mc_trial, range(MC_N), chunksize=10):
            trials.append(trial)
            if len(trials) % 100 == 0:
                print("MC", len(trials), "/", MC_N, flush=True)
    # Independently verify one scheduled trial against direct in-process execution.
    direct = summary(execute(p, random_data(data, 1600000, probability), kw, engine))
    assert all(trials[0][k] == direct[k] for k in direct)
    tests = {
        k: dict(
            exceedances=sum(t[k] >= full[k] for t in trials),
            p=(1 + sum(t[k] >= full[k] for t in trials)) / (MC_N + 1),
        )
        for k in ("cagr", "sharpe")
    }
    boot = bootstrap(full["equity"], full["years"])
    votes = [
        alpha_pass(rows),
        conc["10"]["net_pct"] <= 103 and sy["net_pct"] <= 88,
        all(t["p"] < 0.05 for t in tests.values()),
        boot["ci95"][0] > 0,
    ]
    return dict(
        period_standard=PERIOD_STANDARD,
        periods=rows,
        concentration=conc,
        symbols=sy,
        monte_carlo=dict(probability=float(probability), trials=trials, tests=tests),
        bootstrap=boot,
        votes=[bool(x) for x in votes],
        verdict="개별통과" if all(votes) else "기각",
        records=records,
    )


def corrections(out: dict) -> None:
    """Full BH step-up over n: unscreened/untested hypotheses assigned p=1."""
    n = len(out["grid"])
    for metric in ("cagr", "sharpe"):
        vals = [
            r.get("robustness", {})
            .get("monte_carlo", {})
            .get("tests", {})
            .get(metric, {})
            .get("p", 1.0)
            for r in out["experiments"]
        ]
        order = np.argsort(vals, kind="stable")
        adjusted = np.minimum.accumulate(
            np.array([vals[j] * n / (i + 1) for i, j in enumerate(order)])[::-1]
        )[::-1].clip(0, 1)
        for i, j in enumerate(order):
            out["experiments"][int(j)].setdefault("correction", {})[metric] = dict(
                p=vals[j],
                rank=i + 1,
                bonferroni_p=min(1.0, vals[j] * n),
                bh_q=float(adjusted[i]),
            )
    for row in out["experiments"]:
        c = row["correction"]
        passed = row["dominates"] and all(
            row.get("robustness", {}).get("votes", [False])
        )
        passed = passed and all(
            v["bonferroni_p"] < 0.05 and v["bh_q"] < 0.05 for v in c.values()
        )
        row["verdict"] = "복귀조건 A 후보" if passed else "기각"
        row["reason"] = (
            "세축우위 미달"
            if not row["dominates"]
            else (
                "개별 강건성 실패"
                if not all(row["robustness"]["votes"])
                else "다중비교보정 실패" if not passed else "모든 지정검사 통과"
            )
        )
    out["multiple_testing"] = dict(
        n=n,
        alpha=0.05,
        bonferroni_threshold=0.05 / n,
        method="Full BH step-up; untested p=1; CAGR/Sharpe separately AND",
        minimum_mc_p=1 / (MC_N + 1),
    )


def pairwise_comparisons(out: dict) -> None:
    """Matched entry/exit baselines for every C and D configuration."""
    controls = {
        (
            r["config"]["variant"],
            r["config"].get("family"),
            r["config"].get("hold_days"),
        ): r
        for r in out["experiments"]
        if r["config"]["variant"] in ("control_C", "control_D")
    }
    for row in out["experiments"]:
        cfg = row["config"]
        if cfg["variant"] not in ("C", "D"):
            continue
        key = (
            ("control_C", cfg["family"], None)
            if cfg["variant"] == "C"
            else ("control_D", None, cfg["hold_days"])
        )
        control = controls[key]
        row["paired_control"] = dict(
            config=control["config"],
            metrics=control["metrics"],
            delta={
                k: row["metrics"][k] - control["metrics"][k]
                for k in ("cagr", "mdd", "sharpe", "trades", "final")
            },
        )


def final_summary(out: dict) -> str:
    """Terminal outcome distinguishes raw best from individually robust candidates."""
    new = [
        r for r in out["experiments"] if r["config"]["variant"] in ("A", "B", "C", "D")
    ]
    best = max(new, key=lambda r: r["metrics"]["sharpe"])
    m, b = best["metrics"], out["baseline"]
    passed = [r for r in new if all(r.get("robustness", {}).get("votes", [False]))]
    if passed:
        strongest = max(passed, key=lambda r: r["metrics"]["sharpe"])
        t = strongest["metrics"]
        detail = (
            f"개별4검사통과 최고Sharpe {strongest['config']} "
            f"CAGR{t['cagr']:+.6f}%/MDD{t['mdd']:.6f}%/Sharpe{t['sharpe']:.6f}, "
            f"4표 {strongest['robustness']['votes']}, "
            f"Bonf CAGR/Sharpe {[strongest['correction'][k]['bonferroni_p'] for k in ('cagr','sharpe')]}, "
            f"BH q {[strongest['correction'][k]['bh_q'] for k in ('cagr','sharpe')]}; "
        )
    else:
        detail = "신규 개별4검사통과 후보 없음; "
    winners = [r for r in new if r["verdict"] != "기각"]
    return (
        f"FINAL SUMMARY: Round16 {len(out['experiments'])}/{len(out['grid'])}조합, "
        f"최종후보 {len(winners)}개; 전체최고Sharpe {best['config']} "
        f"CAGR{m['cagr']:+.6f}%/MDD{m['mdd']:.6f}%/Sharpe{m['sharpe']:.6f} "
        f"({best['reason']}); 챔피언 {b['cagr']:+.6f}%/{b['mdd']:.6f}%/{b['sharpe']:.6f}; "
        f"세축우위 {sum(r['dominates'] for r in out['experiments'])}개, "
        f"개별4검사통과 전체{sum(all(r.get('robustness',{}).get('votes',[False])) for r in out['experiments'])}개/신규{len(passed)}개; "
        + detail
        + f"Bonferroni 기준 {out['multiple_testing']['bonferroni_threshold']:.9f}, "
        f"최종 {'복귀조건 A 후보 존재' if winners else '기각 — 챔피언 교체 근거 없음'}."
    )


def report(out: dict) -> None:
    """Append complete results without altering historical sections."""
    if "\n## 80." in DOC.read_text():
        raise ValueError("Round16 section already exists; avoid duplicate append")
    parts = [
        "\n\n## 80. 청산근접 프록시 방법론과 사전 그리드 (2026-10-08, Round16)\n",
        "**IMPORTANT DISCLOSED LIMITATION:** 실제 청산·미결제약정·히트맵 데이터가 아니다. "
        "가정 레버리지와 일봉 스윙 진입점으로 추정한 클러스터이며 청산량을 추정하지 않는다. "
        "펀딩·슬리피지 미반영 그로스이고 기존 생존편향·미관측 OOS 부재가 남는다.\n",
        "- 유지마진율 고정0.5%. 롱=진입가×(1−0.995/L), 숏=진입가×(1+0.995/L). "
        "고점에서 롱, 저점에서 숏 가정. 직전2봉 고가 이상/저가 이하인 현재봉을 인과적 스윙으로 정의한다. "
        "미래봉으로 스윙을 확인하지 않는다. 과거7/14/30달력일 창 밖 또는 다음 봉부터 청산가에 닿은 가상포지션은 제거한다.\n",
        "- 대표티어 (5,10,20)/(25,50,100): 저·중/고배율의 청산거리 범위를 분리한다. "
        "75배는50/100 사이 중복을 줄이기 위해 제외. log(price)/log(1.005) 고정 구간에2점 이상 모인 "
        "가격의 산술평균을 밀집클러스터로 정한다. 같은 티어 반복스윙도 포함하며 거래량 가중치는 없다. "
        "하방/상방 중 올바른 가격방향의 가장 가까운 평균까지 %거리를 계산한다. "
        "없으면 NaN, 신호False. 당일종가 확정신호→익일시가 진입/조기매도; 조기매도는 이익 여부와 무관하여 손실매도도 가능하다.\n",
        "- A 단독: 하방근접 매수/상방근접 익일시가매도+10/20일종가만기. "
        "B cap5% 챔피언진입 AND 하방근접, 기존20일 또는10일만기. "
        "D 양의30일모멘텀 후보를 근접시 순위점수2배, TOP_K8/10·20일만기; 추가진입 필터가 아니다.\n",
        "- C §21의9단일패밀리(하이킨아시, FRVP, 거래량, VWAP, FVG, 피보나치, EMA, 리퀴디티스윕, 엘리엇) "
        "+§77 Donchian70/25일. §21 분리자본 앙상블은 단일exit 규칙이 없어 제외하고 Donchian으로 대체했다. "
        "§21 대표 설정은 기존집계함수에서 추출하고 원TP/SL·CB·타이밍·만기·사이징을 유지한다. "
        "C 조기매도 추가판과 원exit 대조판을 비교한다. 원시JSON donor_provenance에 설정과 출처를 보존한다.\n",
        "- 조합수: A=2×3×4×2=48, B=48, D=48, C=2×3×4×10=240. "
        "신규384개+원exit C대조10개+D무가중대조2개+챔피언참조1개=전체397개. "
        "만기는 C 각 원전략 고정값, A/B/D는10/20일; 누락·신호0 조합도 분모에 포함. "
        "검증용prefix·미래변조·MC·bootstrap은 새 성과탐색 조합이 아니다. "
        "45종목 캐시2019-09-08~2026-10-05, 편도수수료0.04%, 현재 미완료일봉 제외.\n",
        "\n## 81. 청산근접 전체 조합 실행결과\n",
    ]
    for variant in ("reference", "control_C", "control_D", "A", "B", "C", "D"):
        parts += [
            f"\n### {variant}\n",
            "| 설정 | CAGR% | MDD% | Sharpe | 거래수 | 진입신호수 | 최종판정 |\n|---|---:|---:|---:|---:|---:|---|\n",
        ]
        for row in out["experiments"]:
            if row["config"]["variant"] != variant:
                continue
            m = row["metrics"]
            verdict = (
                "참조(기존 챔피언 유지)" if variant == "reference" else row["verdict"]
            )
            reason = "비교기준" if variant == "reference" else row["reason"]
            parts.append(
                f"| {json.dumps(row['config'],ensure_ascii=False)} | {m['cagr']:+.6f} | {m['mdd']:.6f} | {m['sharpe']:.6f} | {m['trades']} | {row['signals']} | {verdict} — {reason} |\n"
            )
    pairwise_comparisons(out)
    parts += [
        "\n### C 원exit 대비 비교 (패밀리별 최고Sharpe 조기매도 설정, 사후 서술용)\n",
        "| 패밀리 | 원exit CAGR/MDD/Sharpe | 조기매도 CAGR/MDD/Sharpe | ΔCAGR%p / ΔMDD%p / ΔSharpe |\n|---|---|---|---|\n",
    ]
    for family in FAMILIES:
        row = max(
            (
                r
                for r in out["experiments"]
                if r["config"]["variant"] == "C" and r["config"]["family"] == family
            ),
            key=lambda r: r["metrics"]["sharpe"],
        )
        m, control = row["metrics"], row["paired_control"]["metrics"]
        delta = row["paired_control"]["delta"]
        parts.append(
            f"| {family} | {control['cagr']:.6f}/{control['mdd']:.6f}/{control['sharpe']:.6f} | "
            f"{m['cagr']:.6f}/{m['mdd']:.6f}/{m['sharpe']:.6f} | "
            f"{delta['cagr']:+.6f}/{delta['mdd']:+.6f}/{delta['sharpe']:+.6f} |\n"
        )
    parts.append(
        "- C 전체240개와 D 전체48개 설정의 대응 대조군·지표차이는 원시JSON paired_control에 저장했다. "
        "이 표의 최고Sharpe 선택은 결과 설명이며 검증 통과나 승자 선언이 아니다.\n"
    )
    parts += [
        "\n## 82. 정의Y 강건성·다중비교 최종판정\n",
        "- 세축우위(CAGR↑,MDD↓,Sharpe↑) 후보 모두 정의Y8개·7개양의알파, 순손익집중103%/88%, "
        "MC랜덤진입500회 CAGR와Sharpe 각각(초과동률+1)/501<0.05, 일별NAV20일순환블록1000회Sharpe95%CI하한>0를 AND 적용했다. "
        "이전 거래단위CI 대신 실제 일별NAV Sharpe CI를 사용했다. 기간별 신규계좌·기존 워밍업 지표 유지, "
        "BTC 시작시가→종료종가와 양방향수수료0.04% 동일기준. "
        "랜덤진입은 체결수/유효종목일 확률, 후보의 원exit/사이징/레짐을 유지하며 SIGNAL과순위만 무작위화한다.\n",
        f"- 전체n=397, Bonferroni p<0.05/397={.05/397:.12f}. BH는 전체397개 p를 정렬해 step-up/q값 계산, 미검사 조합은p=1. CAGR·Sharpe 보정 모두 AND. 500회 최소p=1/501={1/501:.12f}여서 본페로니 통과 해상도가 부족하다. 이는 무효과의 증명이 아니다. 사전에500회로 고정했고 결과를 본 뒤 MC표본·그리드를 바꾸지 않았다.\n",
        "| 후보 | 알파 양수 | top10/top5% | MC CAGR/Sharpe p | 일별NAV Sharpe95%CI | 4표 | Bonf CAGR/Sharpe | BH q CAGR/Sharpe | 판정 |\n|---|---:|---|---|---|---|---|---|---|\n",
    ]
    period_parts: list[str] = []
    for row in out["experiments"]:
        if "robustness" not in row:
            continue
        r, c = row["robustness"], row["correction"]
        parts.append(
            f"| {json.dumps(row['config'])} | {sum(p['alpha']>0 for p in r['periods'])}/8 | {r['concentration']['10']['net_pct']:.6f}/{r['symbols']['net_pct']:.6f} | {[r['monte_carlo']['tests'][k]['p'] for k in ('cagr','sharpe')]} | {r['bootstrap']['ci95']} | {r['votes']} | {[c[k]['bonferroni_p'] for k in ('cagr','sharpe')]} | {[c[k]['bh_q'] for k in ('cagr','sharpe')]} | {row['verdict']} — {row['reason']} |\n"
        )
        period_parts.append(
            f"\n### 기간분할 {json.dumps(row['config'],ensure_ascii=False)}\n"
        )
        period_parts.append(
            "\n| 기간 | 전략CAGR% | BTCCAGR% | alpha%p |\n|---|---:|---:|---:|\n"
        )
        for period in r["periods"]:
            period_parts.append(
                f"| {period['start']}~{period['end']} | {period['metrics']['cagr']:.6f} | {period['btc_cagr']:.6f} | {period['alpha']:.6f} |\n"
            )
    parts += period_parts
    parts += [
        "\n" + final_summary(out) + "\n",
        "\n- 원시 결과: `docs/round16-results-2026-10-08.json`에 전체397설정·데이터hash·거래원장·MC전체시행·bootstrap전체시행·보정값을 보존한다. 검증결과는 verification에 저장한다.\n",
    ]
    with DOC.open("a") as f:
        f.write("".join(parts))


def run() -> None:
    """Complete full grid before any final adoption decision."""
    frames, manifest, skipped = load_data()
    assert not skipped and len(frames) == 45
    bank, provenance = donors(frames)
    volume = volume_prep(frames)
    grid = plans()
    if PATH.exists():
        out = json.loads(PATH.read_text())
        assert out["grid"] == grid and out["manifest"] == manifest
    else:
        out = dict(
            status="running",
            grid=grid,
            manifest=manifest,
            period_standard=PERIOD_STANDARD,
            donor_provenance=provenance,
            experiments=[],
        )
        save(out)
    proxy = {}
    for t, w in itertools.product(range(2), (7, 14, 30)):
        proxy[t, w] = {s: find_signals(f, w, TIER_SETS[t]) for s, f in frames.items()}
        print("PROXY", t, w, flush=True)
    baseline = summary(
        simulate_portfolio({s: f.loc[START:] for s, f in volume.items()})
    )
    expected = json.loads((ROOT / "docs/round14-results-2026-10-07.json").read_text())[
        "baseline"
    ]
    for k in baseline:
        np.testing.assert_allclose(baseline[k], expected[k], atol=1e-9, rtol=0)
    out["baseline"] = baseline
    for config in grid:
        if any(r["config"] == config for r in out["experiments"]):
            continue
        p, data, kw, engine = setup(config, frames, bank, proxy, volume)
        full = execute(p, data, kw, engine, True)
        m = summary(full)
        dominates = bool(
            m["cagr"] > baseline["cagr"]
            and m["mdd"] < baseline["mdd"]
            and m["sharpe"] > baseline["sharpe"]
        )
        row = dict(
            config=config,
            metrics=m,
            signals=sum(int(f.SIGNAL.sum()) for f in p.values()),
            dominates=dominates,
            engine=engine,
        )
        if dominates:
            row["robustness"] = robustness(p, data, kw, engine, full)
        out["experiments"].append(row)
        save(out)
        print(
            "RESULT",
            len(out["experiments"]),
            "/",
            len(grid),
            config,
            m,
            row.get("robustness", {}).get("votes"),
            flush=True,
        )
    pairwise_comparisons(out)
    corrections(out)
    out["status"] = "전체 탐색 완료·최종판정 저장"
    save(out)
    print(final_summary(out), flush=True)


if __name__ == "__main__":
    run()
