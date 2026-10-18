"""마하세븐 '이평선 눌림목' 파라미터 스윕.

수정된 add_mach7_ma_pullback / simulate 를 코인 유니버스에 대해 ~48개 파라미터 조합으로
돌려, B&H 대비 알파(연환산) 중앙값 기준으로 랭킹한다. 데이터는 심볼당 한 번만 받아 캐시.

실행: docker run --rm --entrypoint python -v .../trading/app:/app/app \
        ochestration-trading-momentum-rotation -m app.mach7_ma_pullback_sweep
"""
from __future__ import annotations

import itertools
import statistics

from app.data import fetch_ohlcv
from app.mach7_backtest_core import simulate
from app.mach7_indicators import add_mach7_ma_pullback
from app.momentum_rotation_loop import UNIVERSE

SINCE = "2020-01-01"
INITIAL_CAPITAL = 10_000.0

GRID = {
    "ema_fast": [10, 20],
    "ema_slow": [100, 200],
    "pullback_window": [3, 5, 10],
    "risk_reward_ratio": [1.5, 2.5],
    "exit_ema": [50, 100],
}
EMA_MID = 50
COOLDOWN = 3


def _load_frames() -> dict[str, "object"]:
    frames = {}
    for base in UNIVERSE:
        try:
            frame = fetch_ohlcv(f"{base}/USDT", "1d", SINCE)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base}: 시세조회 실패 — {exc}")
            continue
        if len(frame) >= 260:
            frames[base] = frame
    return frames


def _run_config(frames: dict, cfg: dict) -> dict | None:
    ann, alpha, trades, beat = [], [], [], 0
    for base, frame in frames.items():
        enriched = add_mach7_ma_pullback(
            frame,
            ema_fast=cfg["ema_fast"],
            ema_mid=EMA_MID,
            ema_slow=cfg["ema_slow"],
            pullback_window=cfg["pullback_window"],
            exit_ema=cfg["exit_ema"],
        )
        stats = simulate(
            enriched,
            INITIAL_CAPITAL,
            risk_reward_ratio=cfg["risk_reward_ratio"],
            cooldown_bars=COOLDOWN,
        )
        if stats is None:
            continue
        ann.append(stats["annualized_pct"])
        alpha.append(stats["alpha_annualized_pct"])
        trades.append(stats["trades"])
        if stats["alpha_annualized_pct"] > 0:
            beat += 1
    if len(ann) < 10:
        return None
    return {
        "cfg": cfg,
        "n": len(ann),
        "median_ann": statistics.median(ann),
        "mean_ann": statistics.mean(ann),
        "median_alpha": statistics.median(alpha),
        "mean_alpha": statistics.mean(alpha),
        "beat_pct": beat / len(ann) * 100,
        "avg_trades": statistics.mean(trades),
    }


def run() -> None:
    keys = list(GRID)
    combos = [dict(zip(keys, values)) for values in itertools.product(*(GRID[k] for k in keys))]
    print(f"코인 {len(UNIVERSE)}종목 데이터 로드 중...")
    frames = _load_frames()
    print(f"유효 {len(frames)}종목. 파라미터 조합 {len(combos)}개 스윕 시작...\n")

    rows = []
    for i, cfg in enumerate(combos, 1):
        res = _run_config(frames, cfg)
        if res:
            rows.append(res)
        print(f"  [{i}/{len(combos)}] {cfg} -> "
              f"{'median알파 %+.2f%%' % res['median_alpha'] if res else '스킵'}")

    rows.sort(key=lambda r: r["median_alpha"], reverse=True)
    print("\n" + "=" * 100)
    print("랭킹 (median 알파 연환산 기준, 상위 = B&H를 가장 덜 밑도는/이기는 설정)")
    print("=" * 100)
    print(f"{'fast':>4} {'slow':>4} {'pb':>3} {'RR':>4} {'exitEMA':>7} | "
          f"{'유효':>4} {'med연환산':>9} {'med알파':>9} {'avg알파':>9} {'B&H초과%':>8} {'avg매매':>7}")
    for r in rows:
        c = r["cfg"]
        print(f"{c['ema_fast']:>4} {c['ema_slow']:>4} {c['pullback_window']:>3} {c['risk_reward_ratio']:>4} "
              f"{c['exit_ema']:>7} | {r['n']:>4} {r['median_ann']:>+8.2f}% {r['median_alpha']:>+8.2f}% "
              f"{r['mean_alpha']:>+8.2f}% {r['beat_pct']:>7.0f}% {r['avg_trades']:>7.1f}")

    if rows:
        best = rows[0]
        print(f"\n최고 설정: {best['cfg']}")
        print(f"  median 연환산 {best['median_ann']:+.2f}%, median 알파 {best['median_alpha']:+.2f}%, "
              f"B&H 초과 {best['beat_pct']:.0f}%, 종목당 평균 {best['avg_trades']:.1f}매매")


if __name__ == "__main__":
    run()
