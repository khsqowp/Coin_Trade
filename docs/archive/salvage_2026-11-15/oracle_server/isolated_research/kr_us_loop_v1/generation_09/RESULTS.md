# Generation 09 — Results

Run ID: `GEN09-20261106T120246-41107`  
Status: `COMPLETED_EXPLORATORY` — fixed candidate rejected; not a confirmatory/OOS result.

## Recorded candidate

US SPY, long-only exposure for the first three observed sessions of each complete in-sample calendar month; otherwise cash. Open-to-open adjusted-price returns, 10 bp entry/exit costs, and terminal liquidation cost. One fixed rule was run, with no parameter search.

## Results (net of the specified costs)

| Window | Strategy CAGR | SPY buy-and-hold CAGR | Strategy Sharpe | SPY Sharpe | Strategy MDD | SPY MDD |
|---|---:|---:|---:|---:|---:|---:|
| Full (1993-02-01–2026-11-02) | 8.15% | 10.77% | 0.518 | 0.648 | -58.56% | -55.42% |
| 2001–2016 | 2.79% | 5.29% | 0.239 | 0.362 | -56.91% | -55.42% |
| 2017–2026-11-02 (previously inspected) | 12.25% | 14.97% | 0.754 | 0.893 | -32.18% | -32.05% |

Full-window compounded total return was 1,303.0% for the strategy versus 3,048.8% for SPY buy-and-hold. The strategy was invested on 14.30% of sessions and had approximately 24.02 annual turnover. It did not improve the tested risk/return profile over the benchmark in any reported window. The rule is rejected as a candidate for this objective.

## Interpretation limits

- The final window is explicitly not OOS: it was previously inspected in the research history.
- The source session list was not independently reconciled to an authoritative exchange calendar; a missing vendor session could change the “first three sessions” labels.
- Global historical trial multiplicity remains unresolved. No DSR/PSR, null-portfolio, or family-wise significance claim is made.
- This is evidence against this one fixed rule on this snapshot, not evidence that profitable systematic strategies do not exist.

## Artifacts

- Preregistration: `PREREG.md` (SHA-256 in run manifest)
- Runner and unit tests: `run_gen09.py`, `test_gen09.py` (6 tests passed before market-data run)
- Manifest: `manifest_GEN09-20261106T120246-41107.json`
- Attempt ledger: `attempts_GEN09-20261106T120246-41107.jsonl` (one start and one finish event)
- Net daily return/exposure curve: `equity_curves_GEN09-20261106T120246-41107.csv.gz`
- SPY input SHA-256: `533ea8cccbd302d3f5faa771f0ceb461f697e1f75302497ca053a6b3d98b09ba`
