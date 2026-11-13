"""v3 completion: no-stop crash-filter-off baselines for the three D pairs."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from docs.research.sl_loop import run_v3 as R

if __name__ == "__main__":
    reg = {}
    for lev, kill, cool in ((4., .15, 30), (4., .30, 14), (3., .20, 1)):
        R._add(reg, lev=lev, kill=kill, cool=cool, crash=0, family="crash_off_baseline", s=None)
    ex = {json.loads(l)["id"] for l in open(R.OUT / "ledger.jsonl") if l.strip()}
    reg = {k: v for k, v in reg.items() if k not in ex}
    rows = R._run_batch(reg, 9) if reg else {}
    for r in rows.values():
        print(r["params"]["lev"], r["params"]["kill"], r["params"]["cool"], r["IS"]["calmar_i"], r["OOS"]["calmar_i"])
