# Forward salvage manifest — linuxserver_research

Source: `/Users/user/CODE/linuxserver_research` (read-only). Destination payload: `linuxserver_research/` below this manifest directory. Traversal and file decisions followed ascending, top-down alphabetical order.

## LEDGER.md/PLAN.md connection to the Ochestration cumulative-trial-count gap

`stock_loop/LEDGER.md` and `stock_loop/PLAN.md` are **high-value primary findings documents**, not incidental documentation. The related Ochestration log at `docs/research/kr-us-systematic-strategy-log.md` (as described in the task background) says its Oracle cumulative trial databases are unavailable locally, global cumulative N is unknown, and therefore it makes no DSR/PSR/Bonferroni/BH significance claim. This separate linuxserver research program supplies a concrete, completed KR/US ledger for its own scope and answers the analogous missing-count question; it must remain a distinct study and must not be silently pooled into the Ochestration log.

The plan began **2026-11-13**, names the user as owner, and splits work between the “coin-trade” session (KR + shared library) and “리눅스 투자 세션” (US), under `/home/noroot/research/stock_loop/`. It expressly prohibits touching the live Binance bot, `.env`, secrets, or containers. The planned anti-overfit gates were: Stage 1 at most 12 hypotheses per market, net mean > 0, |t| >= 3, same sign in both development halves; Stage 2 a small grid, plateau, walk-forward, and BH q < 0.10 across all trials; Stage 3 one untouched final 24-month holdout with Sharpe >= 1, random-entry percentile >= 95 from >= 1,000 draws, positive in >= 70% of development years, positive at 2x cost, >= 200 trades, and <= 10 concurrent positions. The plan capped at six rounds per market, later extended by owner authorization.

The ledger records KR-01 through KR-36: 36 named KR hypotheses, with **zero Stage-2 survivors** through the KR rounds; its own R2 entry says “0 survivors, no Stage 2” and “Total trials 24” for KR-13..24, before later rows. Examples include KR-01 gap-down fade (noise/drop, t=1.29), KR-02 gap-up continuation (hurts, t=-13.98), KR-03/04 overnight drift (hurts), and KR-18/19/22/23 (hurts). Other KR rows are noise/drop.

The US running counters explicitly progress **30 → 45 → 99 → 112 → 129 → 140 → 149 → 196 → 207**: round 1; round 2; its 54-cell US-18 Stage-2 grid; rounds 4–6; the survivorship-repair round 7; longer-hold round 8; and ETF/VIX/cross-asset round 9. The ledger states: “Search ended: 6 rounds, 140 trials, 0 survivorship-robust candidates.” Round 7 was an authorized extra survivorship repair; round 9 exceeded the plan’s six-round cap under the owner’s “until meaningful” instruction. BB-01 then tested 32 intraday Bollinger cells across KR and US/tick datasets and ended “hurts; stop.” The cumulative 207 count is for the US counter; KR and BB-01 are additional program rows/cells. The user-provided characterization is **roughly 250+ completed KR+US price-performance trials**, with no robust candidate after survivorship and costs. Do not claim that the US counter 207 alone is the entire combined total.

Only `US-18-T100-cand` reached Stage 3: the momentum-leader dip (RSI2 < 5, 126-day top-quartile momentum, PIT top-100 universe). It technically passed all six holdout gates: net +1.98%/trade, t=3.31, N=10 portfolio Sharpe 2.01, max drawdown -12.8%. The ledger itself marks it **SURVIVORSHIP-SENSITIVE**: on a frozen-2014 universe holdout it fell to +0.45%, Sharpe 0.81 (2x cost +0.05%). Round 7’s point-in-time membership rerun reduced the development edge and recorded recent 2019+ t=1.16 with 2x-cost -0.21%, describing the edge as “front-loaded and fading.” `results/US_FINAL.md` says “Recommend paper-trading only.” Thus the narrow technical pass is not a validated, survivorship-corrected tradeable edge. The overall disposition is **0 of roughly 250+ completed KR+US price-performance trials produced a robust, survivorship-corrected, cost-surviving edge**. This is strong evidence about short-horizon (intraday through 40-day) KR/US price-based technical, momentum, reversal, calendar, and volatility hypotheses in this dataset, not proof that no strategy can work universally.

## Copied, by subproject

This forward curation selected **241 files (5,394,330 bytes)**. At final audit, the payload subtree contained 14 additional source-relative files not in this selection list: six excluded tests (`gulp_pattern/test_gulp.py`, `stock_loop/bb/test_bb.py`, `stock_loop/collect/tests/conftest.py`, `stock_loop/collect/tests/test_collect.py`, `stock_loop/lib/tests/test_lib.py`, `stock_loop/us/tests/test_us.py`), six preregistration timestamp/hash markers (`gulp_pattern/prereg.timestamp`, `stock_loop/bb/prereg.sha256`, `stock_loop/bb/prereg.timestamp`, and the three `stock_loop/spec/KR*_prereg.timestamp` files), and two run wrappers (`stock_loop/kr/run_heavy.sh`, `stock_loop/us/run_heavy.sh`). These were present in the destination payload at audit but are not claimed as files selected or copied by this forward pass.

### `stock_loop/kr`
- `stock_loop/kr/__init__.py` — KR hypothesis definitions, preregistration generators, and round runners.
- `stock_loop/kr/hypotheses.py` — KR hypothesis definitions, preregistration generators, and round runners.
- `stock_loop/kr/hypotheses2.py` — KR hypothesis definitions, preregistration generators, and round runners.
- `stock_loop/kr/hypotheses3.py` — KR hypothesis definitions, preregistration generators, and round runners.
- `stock_loop/kr/make_prereg.py` — KR hypothesis definitions, preregistration generators, and round runners.
- `stock_loop/kr/make_prereg2.py` — KR hypothesis definitions, preregistration generators, and round runners.
- `stock_loop/kr/make_prereg3.py` — KR hypothesis definitions, preregistration generators, and round runners.
- `stock_loop/kr/run_kr.py` — KR hypothesis definitions, preregistration generators, and round runners.
- `stock_loop/kr/run_kr2.py` — KR hypothesis definitions, preregistration generators, and round runners.
- `stock_loop/kr/run_kr3.py` — KR hypothesis definitions, preregistration generators, and round runners.
### `stock_loop/us`
- `stock_loop/us/__init__.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/common.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/diag7.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/drift_diag.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/hyp.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/hyp2.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/hyp4.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/hyp5.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/hyp6.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/hyp7.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/ledger_s2_us18.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/mem_info.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/robust_us18.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/run_round.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/run_round8.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/run_round9.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/run_stage1.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/stage2_us18.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/stage3_us18.py` — US hypothesis families, diagnostics, and stage/round runners.
- `stock_loop/us/survivorship_us18.py` — US hypothesis families, diagnostics, and stage/round runners.
### `stock_loop/bb`
- `stock_loop/bb/bb.py` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/fetch.py` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/final.py` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/kr_ticks.py` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/prereg.md` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/report.md` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/results.json` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/results_dev.json` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/results_dev_buggy_activity.json` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/results_dev_optleak.json` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/results_test.json` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/run_bb.py` — BB-01 strategy code, preregistration, report, and compact result JSONs.
- `stock_loop/bb/summ.py` — BB-01 strategy code, preregistration, report, and compact result JSONs.
### `stock_loop/results`
- `stock_loop/results/KR_all.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/KR_round2.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/KR_round3.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/KR_stage1.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/KR_stage2.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-01/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-02/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-03/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-04/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-05/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-06/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-07/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-08/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-09/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-10/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-11/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-12/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-13/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-14/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-15/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-16/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-17/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-18/robustness.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-18/stage2.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-18/stage3.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-18/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-18/survivorship.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-19/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-20/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-21/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-22/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-23/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-24/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-25/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-26/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-27/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-28/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-29/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-30/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-31/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-32/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-33/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-34/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-35/diag_periods.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-35/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-42/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-43/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-44/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-45/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-46/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-47/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-48/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-49/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-50/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-51/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US-52/summary.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_FINAL.md` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_STATE.md` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_drift_by_year_dev.csv` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_ledger_table.md` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_ledger_table_round8.md` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_ledger_table_round9.md` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_requests_for_lib.md` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_round2.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_round4.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_round5.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_round6.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_round7.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_round8.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_round9.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/US_stage1.json` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/us35_raw/retrieved_at.txt` — Compact result summaries, tables, and US-35 membership provenance.
- `stock_loop/results/us35_raw/sp500_wikipedia.html` — Compact result summaries, tables, and US-35 membership provenance.
### `stock_loop/spec`
- `stock_loop/spec/KR-01/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-02/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-03/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-04/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-05/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-06/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-07/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-08/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-09/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-10/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-11/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-12/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-13/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-14/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-15/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-16/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-17/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-18/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-19/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-20/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-21/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-22/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-23/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-24/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-25/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-26/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-27/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-28/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-29/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-30/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-31/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-32/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-33/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-34/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-35/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR-36/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/KR_round3_prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-01/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-02/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-03/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-04/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-05/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-06/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-07/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-08/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-09/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-10/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-11/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-12/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-13/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-14/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-15/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-16/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-17/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-18/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-18/stage2_prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-18/stage3_prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-19/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-20/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-21/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-22/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-23/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-24/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-25/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-26/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-27/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-28/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-29/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-30/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-31/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-32/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-33/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-34/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-35/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-36/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-37/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-38/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-39/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-40/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-41/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-42/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-43/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-44/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-45/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-46/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-47/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-48/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-49/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-50/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-51/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-52/prereg.md` — Pre-run strategy specifications and preregistration records.
- `stock_loop/spec/US-ADDENDUM-data.md` — Pre-run strategy specifications and preregistration records.
### `stock_loop/lib`
- `stock_loop/lib/__init__.py` — Reusable shared backtest and statistics harness modules.
- `stock_loop/lib/baseline.py` — Reusable shared backtest and statistics harness modules.
- `stock_loop/lib/costs.py` — Reusable shared backtest and statistics harness modules.
- `stock_loop/lib/data.py` — Reusable shared backtest and statistics harness modules.
- `stock_loop/lib/eventstudy.py` — Reusable shared backtest and statistics harness modules.
- `stock_loop/lib/features.py` — Reusable shared backtest and statistics harness modules.
- `stock_loop/lib/portfolio.py` — Reusable shared backtest and statistics harness modules.
- `stock_loop/lib/report.py` — Reusable shared backtest and statistics harness modules.
- `stock_loop/lib/splits.py` — Reusable shared backtest and statistics harness modules.
### `stock_loop/collect`
- `stock_loop/collect/README.md` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/__init__.py` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/common.py` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/manifest.py` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/manifest_check.py` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/run_collect.sh` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/tick_to_bars.py` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/universe/kr_20261113.csv` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/universe/us_20261113.csv` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/universe.py` — Collection modules, docs/config, and value20 universe snapshots.
- `stock_loop/collect/yf_collect.py` — Collection modules, docs/config, and value20 universe snapshots.
### `gulp_pattern`
- `gulp_pattern/combos_kr.csv` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/combos_us.csv` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/fetch.py` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/gulp.py` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/out/combos_kr.csv` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/out/combos_us.csv` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/out/results_kr.json` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/out/results_us.json` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/prereg.md` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/report.md` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
- `gulp_pattern/summ.py` — Gulp strategy code, preregistration, report, combo tables, and compact outputs.
### `stock_loop` root
- `stock_loop/LEDGER.md` — High-value row-per-hypothesis trial findings with cumulative BH q values.
- `stock_loop/PLAN.md` — Dated preregistration, anti-overfit gates, and live-server safety boundaries.

## Skipped (low-value/cache/binary/lock/state/parquet/tests)

- `gulp_pattern/cache/` — 288M; cached price parquet inputs, reproducible from public data.
- `stock_loop/bb/cache/` — 69M; cached intraday datasets, including the individually >20MB `us_5m.parquet` (55M).
- `stock_loop/lib/cache/` — 6.8M; cached source data.
- `stock_loop/data/minute/` — 161M; raw per-symbol/per-minute dumps and manifests, reproducible inputs.
- `stock_loop/collect/state/` — 432K; `.done` completion flags and tick-to-bars state JSON.
- `stock_loop/kr/tests/`, `stock_loop/us/tests/`, `stock_loop/lib/tests/`, `stock_loop/collect/tests/`, `stock_loop/bb/test_bb.py`, `gulp_pattern/test_gulp.py` — 6 test files, about 44K total; mechanics-only tests.
- `stock_loop/results/**/trades_*.parquet` and `holdout_trades_*.parquet` — per-trade intermediate exports; not copied because compact summaries and ledger results preserve findings.
- `stock_loop/results/us42_raw/VIX.parquet` — 155K; raw input series, excluded under the parquet rule.
- `stock_loop/.heavy.lock` — 0B; lock file.
- `stock_loop/bb/TEST_LOCK` — 4K; lock/state marker.
- `stock_loop/bb/prereg.sha256`, `stock_loop/bb/prereg.timestamp`, `gulp_pattern/prereg.timestamp`, `stock_loop/spec/KR_prereg.timestamp`, `stock_loop/spec/KR_round2_prereg.timestamp`, `stock_loop/spec/KR_round3_prereg.timestamp` — marker/hash/timestamp artifacts; preregistration content itself is copied.
- `stock_loop/lib/READY` — 0B; harness readiness marker.
- `gulp_pattern/tools/pip.pyz` — vendored binary.
- `stock_loop/collect/pytest.ini` — test-only configuration.
- `stock_loop/collect/universe/` is copied: the two CSVs include `value20`/group fields, so they are dated universe snapshots rather than bare symbol lists.
- Results/output files were checked for the >20MB rule: `gulp_pattern/out/` outputs are 1.0–1.4M each; no file in `stock_loop/results/` exceeds 20MB.

## Secrets flagged

None found. The only credential-related scan match was the safety instruction in `stock_loop/PLAN.md` saying not to read/print secrets; it contains no credential value and is copied as plan context.
