"""Write Round 3 preregistrations before running any Round-3 strategy."""
import sys
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kr.hypotheses3 import H3

COMMON = """## Common rules
- Development data only; holdout remains locked. Universe and survivorship limits inherit Round 1.
- All entries are at close t; exits are close t+h. Costs use the existing A (Prime) and B (no Prime) models.
- Event hypotheses use eligible=P.liquid(2e9), require finite close at t and t+h, and apply per-stock cooldown after accepted signal bars. Cooldown bars are h; rebalance hypotheses signal every h-th bar.
- Signals use information through t only. Stage 1 defaults are fixed before results are observed.
- Verdict gate: B net mean>0, date-clustered t>=3, both dev halves positive, n>=30. Survivors receive one Stage-2 grid; plateau requires at least 70% cells with mean>0 and t>=2 and every default-axis neighbor mean>0. Final advance additionally requires BH q<0.10.
- Report n, gross/net means, date-clustered and month-clustered t, portfolio Sharpe, break-even cost (=gross mean), A/B, 2x costs, lag-1 robustness, yearly consistency and random-entry baseline.
- Stage-1 BH family: 24 prior hypotheses + 12 new hypotheses = 36; append every Stage-2 cell p-value to this same family before computing q-values.
- Round-3 diagnostics: yearly count/mean; exclusion of 2020-02-15 through 2020-04-30; concentration by stock and entry date; KOSPI/KOSDAQ splits; signal-time liquidity buckets; next-close fill realism; winsorized mean and median; Prime A versus B; pairwise agreement among KR-24 reference and KR-25..27.
- Part A includes KR-24 as a labeled reference diagnostic only; it is not a new trial.
- Random baseline uses 1,000 draws and seed 7. Holdout is not used for any selection, ranking, or decision.
"""


def main():
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    for hid, (fn, defaults, grid, idea, slots, signal) in H3.items():
        folder = ROOT / "spec" / hid
        folder.mkdir(parents=True, exist_ok=True)
        body = (f"# {hid} - {idea} (Round 3 prereg)\nWritten {stamp} before Round-3 runs.\n\n"
                f"## Signal\n{signal}\n\n## Portfolio slots N\n{slots}\n\n"
                f"## Defaults (fixed)\n{defaults}\n\n## Stage-2 grid\n{grid}\n\n{COMMON}")
        (folder / "prereg.md").write_text(body)
    (ROOT / "spec" / "KR_round3_prereg.md").write_text("# Korea Round 3 preregistration\n\n" + COMMON)
    (ROOT / "spec" / "KR_round3_prereg.timestamp").write_text(stamp + "\n")
    print("wrote", len(H3), "hypothesis preregistrations", stamp)


if __name__ == "__main__":
    main()
