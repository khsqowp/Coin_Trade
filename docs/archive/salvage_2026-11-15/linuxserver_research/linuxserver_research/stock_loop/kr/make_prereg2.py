"""Writes spec/KR-13..24/prereg.md from kr.hypotheses2.H2 (run BEFORE any Round-2 backtest)."""
import sys, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kr.hypotheses2 import H2

COMMON = """
## Round-2 common (inherits spec/KR-01/prereg.md 'Common' section unchanged: universe, liquidity>=2e9, costs A/B/tax18/2x, dev data only, holdout locked)
- Why Round 2: Round-1 audit found the KRX opening price is systematically elevated (all-liquid-stock open->close mean -0.14%/day, overnight +0.11..0.17%/day; same sign in KOSPI/KOSDAQ index data and every year). Buying at the next OPEN therefore carries a structural ~0.14%/day drag. Round 2 uses CLOSE entries (MOC) for non-gap ideas. Caveat: signal uses close_t and fills at close_t (closing-auction indicative price 15:20-15:30); survivors get a +1 bar lag robustness check (buy close t+1).
- Trials counted for BH: 12 (Round 1) + 12 (this round) + every Stage-2 grid cell.
- Gate (Stage 1, unchanged): net(B) mean>0, |t|>=3 clustered by entry date, same sign in both dev halves, n>=30. One Stage-2 grid run for all survivors (<=3 params x 3 values), plateau rule + BH q<0.10 as in Round 1. Random-entry baseline for survivors.
- Reported per strategy: n, net mean/trade, t, portfolio Sharpe (N slots as stated), break-even round-trip cost (=gross mean), A(Prime) vs B(no Prime), tax 0.18%, 2x cost.
- Long-only, no shorting. Defaults below are fixed; no search in Stage 1.
"""
stamp = datetime.datetime.now().isoformat(timespec="seconds")
for hid, (fn, dflt, grid, idea, N, sig) in H2.items():
    d = ROOT / "spec" / hid
    d.mkdir(parents=True, exist_ok=True)
    (d / "prereg.md").write_text(f"# {hid} - {idea} (KR Round 2, Stage 1 prereg)\nWritten {stamp} BEFORE any Round-2 run.\n\n## Signal\n{sig}\n\n## Portfolio slots N\n{N}\n\n## Defaults (fixed)\n{dflt}\n\n## Stage-2 grid\n{grid}\n{COMMON}")
(ROOT / "spec" / "KR_round2_prereg.timestamp").write_text(stamp + "\n")
print("wrote", len(H2), stamp)
