"""Writes spec/KR-*/prereg.md from hypotheses.H (run BEFORE any backtest)."""
import sys, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kr.hypotheses import H

SIG = {
 "KR-01": "gap = open_t/close_{t-1}-1 <= -3%. Buy open t, sell close t. No trend filter (ma=0 default; ma in {60,200} is Stage-2 grid).",
 "KR-02": "gap = open_t/close_{t-1}-1 >= +3%. Buy open t, sell close t. (Gap-ups may be unbuyable at the open; slippage tier + 2x cost cover it.)",
 "KR-03": "Every liquid KOSPI name, every day: buy close t (MOC, approximated), sell open t+1. Complement (open->close intraday drift) is the mirror and is reported as gross only.",
 "KR-04": "Same as KR-03 for KOSDAQ names.",
 "KR-05": "IBS=(C-L)/(H-L) <= 0.2 at close t AND close_t > SMA200. Buy open t+1, sell close t+3 (3 bars).",
 "KR-06": "RSI(2, Wilder) <= 10 at close t AND close_t > SMA200. Buy open t+1, sell close t+3.",
 "KR-07": ">=3 consecutive down closes ending at t. Buy open t+1, sell close t+3. No trend filter.",
 "KR-08": "close_t/close_{t-1}-1 >= 29% (KR +-30% limit since 2015-06-15, so only the later part of dev can fire); buy next open ONLY if open_{t+1} < 1.29*close_t (not locked at limit up); sell close t+1. Long-only: the fade side needs shorting and is not testable by a retail KR account.",
 "KR-09": "volume_t >= 3x mean(volume, t-20..t-1) AND |ret_t| <= 1.5%. Buy open t+1, sell close t+3. Long only.",
 "KR-10": "close_t > max(high over t-20..t-1) AND volume_t >= 2x avg20. Buy open t+1, sell close t+5.",
 "KR-11": "Turn-of-month: buy open of the LAST trading day of each month, sell close 4 bars later (3rd trading day of next month). All liquid names. Weekday effects are NOT tested in this round (dropped to stay <=12).",
 "KR-12": "3-day KOSDAQ index return minus KOSPI index return <= -3% at close t. Buy liquid KOSDAQ stocks open t+1, sell close t+3.",
}

COMMON = """
## Common (all KR hypotheses)
- Data: FinanceDataReader/Naver daily OHLCV (price-adjusted) cached under gulp_pattern/cache (read-only reuse, no re-download); calendar = KOSPI index days. Bars with volume 0 or price<=0 are NaN.
- Universe: KOSPI+KOSDAQ names in kr_universe.csv with code ending 0 (excludes preferred), excluding SPAC/ETF/ETN/REIT-like names by name regex. Liquidity: 20-bar mean traded value (close*volume) >= 2e9 KRW, known at signal bar (for open-entry-same-day signals the value is lagged one bar).
- SURVIVORSHIP: the listing is of CURRENTLY listed names only (no delisted). Results are upward-biased, esp. for mean-reversion/oversold ideas; discount accordingly.
- Dev data: start (2014-08) .. 2024-11-11. FINAL HOLDOUT 2024-11-12..2026-11-12 stays locked (lib.splits guard); never unlocked in Stage 1-2. Dev halves split at the dev-sample midpoint (by bar).
- Costs (lib/costs.py): sell tax 0.20% (2026 KOSPI 0.05%+0.15% 농특세 / KOSDAQ 0.20%), commission 0.015%/side, slippage 0.05%/side if 20d value >= 2e10 KRW else 0.10%/side. Scenario A (Toss Prime: commission 0 within 1e8 KRW/month turnover, fixed 5,900 KRW/month) and B (no Prime). Sensitivities: tax 0.18%, 2x all costs. Gating scenario = B (stricter per trade); A shown.
- Stage 1 pass rule (PLAN): net mean trade return > 0, |t|>=3 (SE clustered by entry date), same sign in both dev halves. Defaults fixed here; NO parameter search in Stage 1. Long-only.
- Portfolio: equal weight, max 5 concurrent (capital 1.3M KRW, N=5), first-come by entry time with seeded random tie-break; Sharpe from realised daily P&L (annualised sqrt(252)); implied monthly turnover (buy+sell notional) reported vs Prime cap 1e8 KRW.
- Also reported: break-even round-trip cost (= gross mean trade return).
- Stage 2 (survivors only, max one round): grid of <=3 params x 3 values listed below; plateau rule: >=70% of grid cells have net mean>0 and t>=2 AND all axis-neighbours of the default are net-positive; BH q<0.10 over ALL trials (Stage-1 + Stage-2 cells); random-entry baseline (1000 draws, same entry dates) percentile reported.
- Verdicts: advance / noise / hurts exactly per PLAN.md.
"""

stamp = datetime.datetime.now().isoformat(timespec="seconds")
for hid, (fn, dflt, grid, idea) in H.items():
    d = ROOT / "spec" / hid
    d.mkdir(parents=True, exist_ok=True)
    txt = f"# {hid} - {idea} (KR, Stage 1 prereg)\nWritten {stamp} by the KR session BEFORE any run.\n\n## Signal\n{SIG[hid]}\n\n## Defaults (fixed)\n{dflt}\n\n## Stage-2 grid\n{grid}\n{COMMON}"
    (d / "prereg.md").write_text(txt)
(ROOT / "spec" / "KR_prereg.timestamp").write_text(stamp + "\n")
print("wrote", len(H), stamp)
