# R033 — frozen 37-symbol daily-macro × intraday consensus replay

Date: 2026-11-17 (Asia/Seoul)

Status: preregistered exploratory development replay. This is not OOS: the symbols/data panel and related research have already been inspected in prior rounds. It cannot qualify a strategy for the user's 80% OOS gate.

## Question and fixed hypothesis

Does a daily trend regime improve the target-first performance of the four already-tested 1m-price-action atoms when applied to a wider fixed futures cohort that includes five officially settled contracts? Compare each fixed consensus strategy with and without a daily macro alignment filter. Do not change candidate rules after results.

## Frozen sample and design

- Universe: the exact sorted 37-symbol cohort in `symbols.json`, extracted from R030's fixed universe. No substitutions. The source candle DB is read-only at `chart_predictor/data/vision_pit_dev_sample.sqlite`.
- Contract boundaries: exact Binance USD-M settlements in `settlements.json` for ALPHA, BAL, BLZ, ICX, and REN. Trim each contract at official settlement; discard pre-first-trade rows. Any unmapped symbol ending in a zero-trade tail causes the run to fail closed.
- Atoms: existing `bb_squeeze_breakout`, `orb_funding_session`, `vwap_band_fade`, and `volume_climax_exhaustion` implementations, unchanged. Test every nonempty subset: 15 subsets, with 4 singles, 6 pairs, 4 triples, and 1 four-rule set.
- Signal bars: fully closed UTC bars on 1m, 3m, 5m, 10m, 15m, 30m, 60m, 120m, and 240m.
- Regimes: (A) unfiltered consensus; (B) same-direction alignment with the latest fully closed UTC daily SuperTrend(14, 3×ATR). A zero/unknown macro direction abstains. This is a fixed filter, not a tuned parameter.
- Evaluation horizons: 10 and 20 signal bars as separate claims. Expected total cells: **15 subsets × 9 timeframes × 2 horizons × 2 regimes = 540**.
- Entry/exit: next timeframe open; median structural stop among agreeing votes; target 2R; stop-first same-minute ties; target fills at target; a stop gapped through fills at observed open; 0.05% fee each side. No funding, spread, market impact, mark-price liquidation, or depth model is available; disclose these omissions.
- Executability gate: the signal bar's last 1m row and entry bar's first 1m row must have trades; require a complete, contiguous horizon; barriers count only on traded 1m rows; require a traded final-minute mark for timeout. Skip incomplete path/data-end labels and labels crossing official settlement. Disallow new entries in the final 30 minutes before settlement.
- Cooldown: separately per symbol, subset, timeframe, regime, and horizon; do not count overlapping events inside that horizon.

## Fixed acceptance and reporting

- Primary label: target reached before stop and within the selected 10× or 20× horizon. Timeout is failure for target-first precision.
- Secondary label: entry-to-horizon-end close direction accuracy, reported separately even if a barrier was reached earlier.
- Report every one of 540 cells including zero-event cells, event count, unique symbols, target-first and deadline-direction point estimates with Wilson 95% intervals, gross/net mean trade return, net R, timeout rate, profit factor, skipped-window reasons, and symbol-level counts/rates.
- User's eventual crypto pass criterion remains OOS target-first ≥80% with at least 200 non-overlapping events per claim. The wider spec additionally requires appropriate uncertainty/baseline, coverage, symbol diversity, and positive cost-adjusted expectancy. No retrospective result in R033 can satisfy OOS qualification.
- Do not select a winner from R033, tune parameters, or open a sealed/forward evaluation boundary based on these results.

## Reproducibility and sources

- Strategy definitions and prior comparison: R025; source-quality cohort: R030; settlement evidence: R032.
- Exact frozen universe and settlement timestamps are stored beside this plan. The run hashes the exact post-epoch candle rows and each settlement cutoff.
- Official exchange settlement notices are linked in the R032 report; five boundaries are preserved in `settlements.json`.
