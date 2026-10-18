"""코인 신규 전략 탐색 루프 — 거래량 폭증 시그널 개선안 검증.

실행:
  docker run --rm --entrypoint python coin-trade -u -m app.crypto_volume_spike_research_loop

목적:
  docs/전략-백테스트-종합.md §12의 미채택 후보(거래량 폭증 + 당일무반응)를 기준으로,
  계좌단위 서킷브레이커 / 상대강도 필터 / 변동성 역가중 / TOP_K 변형을 같은 데이터에서
  반복 검증한다. 각 라운드는 이벤트스터디, 포트폴리오 백테스트, 연도별 분해를 함께 기록한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd

from app.futures_data import fetch_perp_ohlcv
from app.momentum_rotation_loop import UNIVERSE
from app.volume_spike_signal_core import find_signals

SINCE = "2019-01-01T00:00:00Z"
FEE_PCT_ONE_WAY = 0.04
LOG_PATH = Path("docs/루프엔지니어링-신규전략탐색-2026-10-05.md")


@dataclass(frozen=True)
class RoundConfig:
    name: str
    hypothesis: str
    lookback: int = 20
    volume_multiple: float = 3.0
    price_cap_pct: float = 5.0
    hold_days: int = 20
    top_k: int = 8
    circuit_dd: float = 0.0
    circuit_resume_dd: float = 0.0
    rs_top_frac: float = 0.0
    require_positive_rs: bool = False
    sizing: str = "equal"  # equal | inv_vol
    max_weight: float = 0.35
    capital_fraction: float = 1.0


ROUNDS = [
    RoundConfig(
        name="R01_base_best_sweep",
        hypothesis="§12 스윕 최고 조합(vol3x/cap5%/hold20d)을 재현해 이후 라운드의 내부 기준선으로 쓴다.",
    ),
    RoundConfig(
        name="R02_circuit_20_10",
        hypothesis="동반추락은 개별 손절보다 계좌단위 신규진입 중단이 더 직접적으로 막을 수 있다.",
        circuit_dd=0.20,
        circuit_resume_dd=0.10,
    ),
    RoundConfig(
        name="R03_circuit_15_7",
        hypothesis="서킷브레이커를 더 빠르게 걸면 MDD를 낮출 수 있지만 반등 재진입 지연 비용이 생길 수 있다.",
        circuit_dd=0.15,
        circuit_resume_dd=0.07,
    ),
    RoundConfig(
        name="R04_circuit_25_12",
        hypothesis="너무 빠른 정지는 휩쏘를 만들 수 있으므로 25% 낙폭에서만 신규진입을 막는 느슨한 방어를 검증한다.",
        circuit_dd=0.25,
        circuit_resume_dd=0.12,
    ),
    RoundConfig(
        name="R05_rs_top_half",
        hypothesis="거래량 폭증 신호 중 상대강도 상위 절반만 남기면 약한 코인의 반등 실패를 줄일 수 있다.",
        rs_top_frac=0.50,
    ),
    RoundConfig(
        name="R06_positive_rs_only",
        hypothesis="90일 모멘텀이 양수인 종목만 진입하면 구조적 하락 추세의 신호를 거를 수 있다.",
        require_positive_rs=True,
    ),
    RoundConfig(
        name="R07_rs_half_circuit",
        hypothesis="상대강도 필터와 계좌단위 정지를 결합하면 수익원은 유지하면서 꼬리위험을 낮출 수 있다.",
        rs_top_frac=0.50,
        circuit_dd=0.20,
        circuit_resume_dd=0.10,
    ),
    RoundConfig(
        name="R08_inv_vol_sizing",
        hypothesis="동일비중 대신 20일 변동성 역가중을 쓰면 고변동 알트 쏠림이 줄어 MDD가 낮아질 수 있다.",
        sizing="inv_vol",
        max_weight=0.25,
    ),
    RoundConfig(
        name="R09_top5_concentrated",
        hypothesis="신호 품질이 높다면 TOP_K를 8에서 5로 줄여 약한 후보를 덜 담는 편이 효율적일 수 있다.",
        top_k=5,
    ),
    RoundConfig(
        name="R10_top12_diversified",
        hypothesis="동반추락이 문제라면 TOP_K를 12로 늘려 개별 종목 급락 기여도를 낮출 수 있다.",
        top_k=12,
    ),
    RoundConfig(
        name="R11_top12_cash35",
        hypothesis="TOP12 분산 조합의 Calmar가 높으므로 자본 65%만 투입하면 벤치마크 MDD 29% 근처에서 더 높은 CAGR이 가능한지 확인한다.",
        top_k=12,
        capital_fraction=0.65,
    ),
    RoundConfig(
        name="R12_top12_cash30",
        hypothesis="TOP12 분산 조합의 자본 투입률을 70%로 올리면 MDD가 벤치마크 한계 안에 남는지 확인한다.",
        top_k=12,
        capital_fraction=0.70,
    ),
    RoundConfig(
        name="R13_top12_cash40",
        hypothesis="TOP12 분산 조합의 자본 투입률을 60%로 낮춰 같은 수익에서 더 낮은 MDD 후보가 되는지 확인한다.",
        top_k=12,
        capital_fraction=0.60,
    ),
    RoundConfig(
        name="R14_top12_cash42",
        hypothesis="TOP12 분산 조합의 자본 투입률을 58%로 낮춰 MDD 29% 기준을 엄격히 통과하는지 확인한다.",
        top_k=12,
        capital_fraction=0.58,
    ),
    RoundConfig(
        name="R15_cap3_hold20",
        hypothesis="당일 가격무반응 조건을 3%로 다시 조이면 수익 일부를 내주고 MDD를 줄일 수 있다.",
        price_cap_pct=3.0,
    ),
    RoundConfig(
        name="R16_vol4_cap5_hold20",
        hypothesis="거래량 기준을 4배로 높이면 더 희귀하지만 더 강한 수급 이벤트만 남길 수 있다.",
        volume_multiple=4.0,
    ),
]


def _metrics(equity: pd.Series) -> dict:
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-6)
    final = float(equity.iloc[-1])
    cagr = (final ** (1 / years) - 1) * 100 if final > 0 else -100.0
    peak = equity.cummax()
    mdd = float(((peak - equity) / peak).max() * 100)
    daily = equity.pct_change().dropna()
    sharpe = float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() > 0 else 0.0
    calmar = cagr / mdd if mdd > 0 else float("inf")
    return {"cagr": cagr, "mdd": mdd, "sharpe": sharpe, "calmar": calmar, "final": final, "years": years}


def _yearly_returns(equity: pd.Series) -> dict[int, float]:
    out: dict[int, float] = {}
    for year, chunk in equity.groupby(equity.index.year):
        if len(chunk) < 2:
            continue
        out[int(year)] = (float(chunk.iloc[-1]) / float(chunk.iloc[0]) - 1) * 100
    return out


def _max_drawdown_year(equity: pd.Series) -> tuple[int, float]:
    yearly = {}
    for year, chunk in equity.groupby(equity.index.year):
        if len(chunk) < 2:
            continue
        peak = chunk.cummax()
        yearly[int(year)] = float(((peak - chunk) / peak).max() * 100)
    if not yearly:
        return 0, 0.0
    y = max(yearly, key=yearly.get)
    return y, yearly[y]


def _load_raw() -> dict[str, pd.DataFrame]:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    raw: dict[str, pd.DataFrame] = {}
    print(f"[로드] 선물 일봉 {len(UNIVERSE)}종목, since={SINCE}")
    for base in UNIVERSE:
        try:
            frame = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, exchange=exchange)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base}: 실패 {exc}")
            continue
        if len(frame) >= 260:
            raw[base] = frame
            print(f"  {base}: {len(frame)}봉, {frame.index[0].date()} ~ {frame.index[-1].date()}")
    return raw


def _prep(raw: dict[str, pd.DataFrame], cfg: RoundConfig) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sym, frame in raw.items():
        if len(frame) < cfg.lookback + cfg.hold_days + 100:
            continue
        df = find_signals(frame, cfg.lookback, cfg.volume_multiple, cfg.price_cap_pct)
        df["RET90"] = df["Close"].pct_change(90)
        df["VOL20"] = df["Close"].pct_change().shift(1).rolling(20).std() * np.sqrt(365)
        out[sym] = df
    return out


def _event_study(prepped: dict[str, pd.DataFrame], cfg: RoundConfig) -> dict:
    rets = []
    baseline = []
    for df in prepped.values():
        opens = df["Open"].to_numpy()
        closes = df["Close"].to_numpy()
        signals = df["SIGNAL"].to_numpy()
        max_i = len(df) - 1 - cfg.hold_days
        for i in range(max_i):
            entry_i = i + 1
            exit_i = entry_i + cfg.hold_days
            if opens[entry_i] <= 0:
                continue
            r = closes[exit_i] / opens[entry_i] - 1
            baseline.append(r)
            if signals[i]:
                row = df.iloc[i]
                if cfg.require_positive_rs and not (pd.notna(row["RET90"]) and row["RET90"] > 0):
                    continue
                rets.append(r)
    sig = pd.Series(rets, dtype=float)
    base = pd.Series(baseline, dtype=float)
    return {
        "signals": int(len(sig)),
        "avg": float(sig.mean() * 100) if len(sig) else float("nan"),
        "win": float((sig > 0).mean() * 100) if len(sig) else float("nan"),
        "base_avg": float(base.mean() * 100) if len(base) else float("nan"),
        "edge": float((sig.mean() - base.mean()) * 100) if len(sig) and len(base) else float("nan"),
    }


def _rank_candidates(cands: list[tuple[str, float, float]], cfg: RoundConfig) -> list[tuple[str, float, float]]:
    if not cands:
        return []
    if cfg.rs_top_frac > 0:
        rs_values = [c[2] for c in cands if pd.notna(c[2])]
        if rs_values:
            threshold = pd.Series(rs_values).quantile(1 - cfg.rs_top_frac)
            cands = [c for c in cands if pd.notna(c[2]) and c[2] >= threshold]
        else:
            cands = []
    if cfg.require_positive_rs:
        cands = [c for c in cands if pd.notna(c[2]) and c[2] > 0]
    return sorted(cands, key=lambda x: x[1], reverse=True)


def _target_allocs(cands: list[tuple[str, float, float]], prepped: dict[str, pd.DataFrame],
                   date: pd.Timestamp, cfg: RoundConfig) -> dict[str, float]:
    picked = cands[:cfg.top_k]
    if not picked:
        return {}
    if cfg.sizing == "equal":
        return {sym: 1.0 / cfg.top_k for sym, _, _ in picked}

    raw_w = {}
    for sym, _, _ in picked:
        vol = prepped[sym].loc[date, "VOL20"] if date in prepped[sym].index else np.nan
        raw_w[sym] = 1 / float(vol) if pd.notna(vol) and vol > 0 else 0.0
    total = sum(raw_w.values())
    if total <= 0:
        return {sym: 1.0 / cfg.top_k for sym, _, _ in picked}
    weights = {sym: min(w / total, cfg.max_weight) for sym, w in raw_w.items()}
    scale = min(1.0, sum(weights.values()))
    return {sym: w / scale / cfg.top_k * len(picked) for sym, w in weights.items()} if scale > 0 else {}


def _simulate(prepped: dict[str, pd.DataFrame], cfg: RoundConfig) -> dict:
    dates = pd.DatetimeIndex(sorted(set().union(*(df.index for df in prepped.values()))))
    fee = FEE_PCT_ONE_WAY / 100
    cash = 1.0
    positions: dict[str, dict] = {}
    curve = []
    trades = 0
    halted_days = 0
    peak = 1.0
    allow_entries = True

    for idx, d in enumerate(dates):
        for sym in list(positions):
            pos = positions[sym]
            df = prepped[sym]
            if d not in df.index:
                continue
            row = df.loc[d]
            if d >= pos["exit_date"]:
                cash += pos["qty"] * float(row["Close"]) * (1 - fee)
                del positions[sym]
                trades += 1

        mtm = cash + sum(
            positions[s]["qty"] * float(prepped[s].loc[d, "Close"])
            for s in positions if d in prepped[s].index
        )
        peak = max(peak, mtm)
        dd = (peak - mtm) / peak if peak > 0 else 0.0
        if cfg.circuit_dd > 0 and dd >= cfg.circuit_dd:
            allow_entries = False
            halted_days += 1
        if cfg.circuit_dd > 0 and not allow_entries and dd <= cfg.circuit_resume_dd:
            allow_entries = True

        free = cfg.top_k - len(positions)
        if free > 0 and idx > 0 and allow_entries:
            prev_d = dates[idx - 1]
            cands = []
            for sym, df in prepped.items():
                if sym in positions or prev_d not in df.index or d not in df.index:
                    continue
                row = df.loc[prev_d]
                if bool(row["SIGNAL"]):
                    cands.append((sym, float(row["VOL_RATIO"]), float(row["RET90"]) if pd.notna(row["RET90"]) else np.nan))
            cands = _rank_candidates(cands, cfg)
            allocs = _target_allocs(cands, prepped, prev_d, cfg)
            mtm = cash + sum(
                positions[s]["qty"] * float(prepped[s].loc[d, "Close"])
                for s in positions if d in prepped[s].index
            )
            exit_date = dates[min(idx + cfg.hold_days, len(dates) - 1)]
            for sym in list(allocs)[:free]:
                price = float(prepped[sym].loc[d, "Open"])
                alloc = min(mtm * cfg.capital_fraction * allocs[sym], cash)
                if price <= 0 or alloc <= 0:
                    continue
                qty = alloc * (1 - fee) / price
                cash -= alloc
                positions[sym] = {"qty": qty, "exit_date": exit_date}

        mtm = cash + sum(
            positions[s]["qty"] * float(prepped[s].loc[d, "Close"])
            for s in positions if d in prepped[s].index
        )
        curve.append((d, mtm))

    equity = pd.Series([v for _, v in curve], index=[t for t, _ in curve])
    m = _metrics(equity)
    m["trades"] = trades
    m["halted_days"] = halted_days
    m["yearly"] = _yearly_returns(equity)
    m["worst_year_mdd"] = _max_drawdown_year(equity)
    return m


def _init_log(raw: dict[str, pd.DataFrame]) -> None:
    starts = [df.index[0] for df in raw.values()]
    ends = [df.index[-1] for df in raw.values()]
    LOG_PATH.write_text(
        "# 루프엔지니어링 신규전략탐색 — 2026-10-05\n\n"
        "## 범위와 검증 기준\n\n"
        f"- 시작점: `docs/전략-백테스트-종합.md` §12의 거래량 폭증 미채택 후보.\n"
        "- 끝점: 최소 10라운드 이상 가설을 실제 docker 백테스트로 검증하고, 벤치마크 대비 승자 여부를 판정.\n"
        "- 검증 기준: 이벤트스터디, 포트폴리오 CAGR/MDD/Sharpe/Calmar, 연도별 수익률, 연도별 최악 MDD.\n"
        "- 데이터: Binance USDT-M 선물 일봉, `fetch_perp_ohlcv(..., since='2019-01-01T00:00:00Z')` 사용.\n"
        f"- 실제 로드 범위: {len(raw)}종목, 최초 {min(starts).date()} / 최종 {max(ends).date()}.\n"
        "- 수수료: 선물 편도 0.04% 적용. 슬리피지·펀딩비·상장폐지 생존편향은 미반영.\n"
        "- 현재 벤치마크: 실거래 결정값 모멘텀 로테이션 2배 delever, CAGR +33%, MDD 29%, Calmar 1.11.\n\n"
        "## 라운드 기록\n\n",
        encoding="utf-8",
    )


def _append_round(i: int, cfg: RoundConfig, event: dict, result: dict, verdict: str) -> None:
    yearly = ", ".join(f"{y}:{v:+.1f}%" for y, v in result["yearly"].items())
    worst_y, worst_mdd = result["worst_year_mdd"]
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(
            f"### [{i}/{len(ROUNDS)}] {cfg.name}\n\n"
            f"- 가설: {cfg.hypothesis}\n"
            f"- 구현: lookback={cfg.lookback}, vol>={cfg.volume_multiple:g}x, cap<{cfg.price_cap_pct:g}%, "
            f"hold={cfg.hold_days}d, TOP_K={cfg.top_k}, circuit={cfg.circuit_dd:.0%}/{cfg.circuit_resume_dd:.0%}, "
            f"rs_top_frac={cfg.rs_top_frac:g}, positive_rs={cfg.require_positive_rs}, sizing={cfg.sizing}, "
            f"capital_fraction={cfg.capital_fraction:.0%}.\n"
            f"- 이벤트스터디: 신호 {event['signals']}건, 평균 {event['avg']:+.2f}%, "
            f"기준 {event['base_avg']:+.2f}%, 엣지 {event['edge']:+.2f}%p, 승률 {event['win']:.1f}%.\n"
            f"- 포트폴리오: CAGR {result['cagr']:+.2f}%, MDD {result['mdd']:.1f}%, "
            f"Sharpe {result['sharpe']:.2f}, Calmar {result['calmar']:.2f}, "
            f"최종 {result['final']:.2f}x, 매매 {result['trades']}건, 정지일 {result['halted_days']}일.\n"
            f"- 연도별: {yearly}.\n"
            f"- 연도별 최악 MDD: {worst_y}년 {worst_mdd:.1f}%.\n"
            f"- 판정: {verdict}\n\n"
        )


def _append_summary(results: list[tuple[RoundConfig, dict]]) -> None:
    ranked = sorted(results, key=lambda x: x[1]["calmar"], reverse=True)
    strict_winners = [x for x in ranked if x[1]["cagr"] >= 33 and x[1]["mdd"] <= 29]
    best = strict_winners[0] if strict_winners else ranked[0]
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write("## 종합 결론\n\n")
        fh.write("| 순위 | 라운드 | CAGR | MDD | Sharpe | Calmar | 판정 |\n")
        fh.write("|---:|---|---:|---:|---:|---:|---|\n")
        for rank, (cfg, r) in enumerate(ranked, 1):
            beats = r["cagr"] >= 33 and r["mdd"] <= 29
            verdict = "벤치마크 상회" if beats else "벤치마크 미달"
            fh.write(
                f"| {rank} | {cfg.name} | {r['cagr']:+.2f}% | {r['mdd']:.1f}% | "
                f"{r['sharpe']:.2f} | {r['calmar']:.2f} | {verdict} |\n"
            )
        if strict_winners:
            fh.write(
                "\n최종 판정: "
                f"{best[0].name}이 이번 루프의 최종 승자다. "
                f"CAGR {best[1]['cagr']:+.2f}%, MDD {best[1]['mdd']:.1f}%, "
                f"Sharpe {best[1]['sharpe']:.2f}, Calmar {best[1]['calmar']:.2f}로 "
                "실거래 결정값(CAGR +33%, MDD 29%, Calmar 1.11)을 동시에 넘었다.\n\n"
            )
        else:
            fh.write(
                "\n최종 판정: 실거래 결정값(CAGR +33%, MDD 29%, Calmar 1.11)을 동시에 넘는 조합은 없다. "
                f"가장 근접한 조합은 {best[0].name}이다.\n\n"
            )
        fh.write(
            "공통 한계: 선물 펀딩비, 슬리피지, 부분체결, 상장폐지 생존편향 미반영. "
            "롱온리로 20일 보유하는 조합은 양(+) 펀딩 지불 구간에서 실측 CAGR이 의미 있게 낮아질 수 있다.\n"
        )


def run() -> None:
    raw = _load_raw()
    if not raw:
        raise RuntimeError("유효 가격 데이터가 없다.")
    _init_log(raw)
    results: list[tuple[RoundConfig, dict]] = []
    no_improve_streak = 0

    for i, cfg in enumerate(ROUNDS, 1):
        print(f"\n[{i}/{len(ROUNDS)}] {cfg.name}")
        prepped = _prep(raw, cfg)
        event = _event_study(prepped, cfg)
        result = _simulate(prepped, cfg)
        improved = (result["cagr"] >= 33 and result["mdd"] <= 29) or result["calmar"] > 1.11
        if improved:
            if result["cagr"] >= 33 and result["mdd"] <= 29:
                verdict = "개선됨: 실거래 벤치마크의 CAGR과 MDD 기준을 동시에 충족."
            else:
                verdict = "개선후보: MDD는 더 크지만 Calmar가 실거래 벤치마크 1.11을 상회해 스케일다운 검증 대상."
            no_improve_streak = 0
        else:
            verdict = "효과없음: 실거래 벤치마크(CAGR +33%, MDD 29%)를 동시에 넘지 못함."
            no_improve_streak += 1
        _append_round(i, cfg, event, result, verdict)
        results.append((cfg, result))
        print(
            f"  이벤트 신호 {event['signals']}건, 엣지 {event['edge']:+.2f}%p | "
            f"CAGR {result['cagr']:+.2f}% MDD {result['mdd']:.1f}% "
            f"Sharpe {result['sharpe']:.2f} Calmar {result['calmar']:.2f}"
        )
        if i >= 10 and no_improve_streak >= 8:
            print(f"  중단 조건 충족: {no_improve_streak}라운드 연속 개선 없음")
            break

    _append_summary(results)
    print(f"\n로그 작성 완료: {LOG_PATH}")


if __name__ == "__main__":
    run()
