# Preregistration — fixed 50:50 Dual Thrust + 14/3/8 portfolio diagnostic

Date: 2026-11-20  
Status: registered before downloading or reading archive OHLC/funding values for this reconstruction.  
Classification: `EXPLORATORY_POST_SELECTION_DIAGNOSTIC`; not independent OOS, not strategy approval, and not a forward result.

## Objective

Test the single fixed portfolio question left open in the research record: does an initial, unrebalanced 50:50 allocation to the existing Dual Thrust sleeve and the existing 14-day/3-day/K8 long-short rotation produce greater after-cost terminal wealth than either sleeve alone on the same dates and eligible symbols?

The investment objective remains maximum long-run after-cost compounded wealth across market regimes. This reconstruction cannot prove that a strategy is best in every regime. It only estimates historical interaction between these two already-selected sleeves. The components and much of the evaluation window were previously examined, so a favorable result is selection-biased and cannot be called confirmation.

## Frozen source, universe, and period

- Source: Binance Vision USD-M monthly `1h` kline and `fundingRate` archives. Personal, non-commercial, non-production historical backtesting only, consistent with the user-approved boundary. Never reuse Vision-derived results for live/manual signals.
- Fixed universe (45 bases, each paired with USDT): `BTC ETH BNB XRP SOL TRX DOGE ZEC LINK XMR ADA XLM BCH LTC HBAR AVAX SUI UNI NEAR TAO AAVE ONDO THETA DOT ENA WLD ICP ETC POL QNT ALGO ATOM RENDER JUP ARB FIL VET CAKE LDO CRV INJ OP APT IMX STX`. The SHA-256 of these newline-terminated base symbols in this exact order is `02f27f494a2836653290402244152a1529e6f68532834dc2f1b4374ca5e3fc28`. This is a current-survivor list, not a point-in-time historical contract universe.
- Evaluation window: 2022-01-01 00:00 UTC through 2026-09-30 23:00 UTC, exclusive end at 2026-10-01 00:00 UTC. This uses complete calendar-month archives only. No values beyond that boundary may enter calculations. December 2021 is allowed only for the fixed indicator warm-up.
- Preflight S3 object-key metadata (not file contents): over the 57-month evaluation window, at least 27 symbols have both hourly-kline and funding ZIP keys in every month; 39 symbols have at least 36 common months over the 58-month inventory that was checked through 2026-10; each of those 58 calendar months had at least 27 symbols with both keys. This establishes archive-key availability only, not successful download, checksum, continuous rows, or actual tradability. Metadata for 2026-10 was not used in strategy design or will not be used as a return input.
- Every downloaded archive must pass SHA-256 sidecar and ZIP CRC checks; row-level timestamps, duplicate bars, expected cadence, missing intervals, funding cadence, and symbol coverage must be audited before strategy returns are calculated. Do not synthesize missing prices, funding events, or pre-listing history.
- The minimum cross-sectional availability for the rotation at a rebalance is 16 symbols (K=8 long and K=8 short); otherwise retain the prior position and record the skipped rebalance. Dual Thrust candidates are ranked only among symbols with valid bars on that signal date. Coverage and missingness are reported by month and year.

## Frozen sleeves

### Rotation sleeve

- Use `app/rs_risk_engine.py` unchanged for the position/accounting rules unless a concrete parity defect is found before outcome access. Record source hash and exact configuration.
- Config: `lookback=14`, `rebal=3`, `K=8`, `lev=1.0`, `deploy=1.0`, `cost=0.001` per traded notional, `funding=True`, no volatility target, no drawdown ladder, no kill switch, no minimum-notional filter, starting NAV 1.0.
- At each scheduled rebalance, rank eligible symbols by trailing 14-day return; hold top 8 long and bottom 8 short, equal gross notional per side, dollar-neutral. Preserve unchanged-name quantities as the existing engine specifies.
- Use hourly OHLC extremes for intraday adverse-equity/liquidation diagnostics and exact funding-time rows; missing hourly data remain missing and may not be forward-filled.

### Dual Thrust sleeve

- Freeze the existing implementation in `app/new_strategy_screening.py::dual_thrust` and the portfolio contract documented in `docs/신규전략100-정밀검증.md` §2-base. No parameter tuning or variant substitution.
- Construct UTC daily OHLC from the verified hourly bars. At daily close, calculate the preceding four completed daily bars' range:
  `R = max(max(high[-4:]) - min(close[-4:]), max(close[-4:]) - min(low[-4:]))`.
- Long event if `close > open + 0.5*R`; short event if `close < open - 0.5*R`. Use only information through the completed signal day.
- Enter at the next UTC daily open. Maintain at most four long and four short slots; rank same-side candidates by the existing 20-day Donchian breakout-distance score, tie-break alphabetically by symbol. Hold for 20 daily sessions, then exit at that session's close. Do not overlap same-symbol positions; preserve the existing simulator's entry/exit priority only if it is explicitly documented and parity-tested before reading outcomes.
- Apply the same 0.10% per-side traded-notional cost to new and closed exposure. Apply observed funding only for settlement events strictly after entry and strictly before exit; at an exact entry/exit timestamp, exclude the event because the ordering is not identifiable. For funding cashflow, use the archive's settlement `markPrice` and the position quantity. Missing funding rows are not filled.

## Portfolio accounting and comparisons

- Produce a daily NAV series for each sleeve from the same initial NAV 1.0, common dates, same fixed universe, and identical date boundary.
- Combined NAV is exactly `0.5*NAV_rotation + 0.5*NAV_dual_thrust` each day. The 50:50 initial allocation is not rebalanced; no mixture weight is optimized.
- Compare rotation-only, Dual-Thrust-only, the fixed blend, cash NAV 1.0, and a BTCUSDT perpetual 1.0x long from the first common entry timestamp to the final timestamp, charging matched entry/exit costs and actual funding. Do not use leverage above 1x.
- Report terminal NAV, total return, CAGR, daily marked MDD, Sharpe, turnover, exposure, fees, funding PnL, liquidations, skipped rebalances, and calendar-year returns. Identify the prespecified 2022 bear, 2023 recovery, and 2024-2026 periods separately; these labels are descriptive, not chosen from results.
- Primary diagnostic is whether the fixed blend increases terminal NAV versus both component sleeves under base assumptions. Risk evidence includes whether MDD exceeds either sleeve and whether any full calendar year loses more than the corresponding rotation sleeve. This is not a pass criterion for deployment because the sample is selected and already observed.
- Uncertainty: paired 30-calendar-day block bootstrap of daily portfolio log returns, 10,000 resamples, fixed seed 20261120. Bootstrap is descriptive only; do not treat it as repairing selection bias or survivor bias.

## Pre-outcome verification gates

1. Reconstruct the exact 45-symbol list from source; assert 45 unique names and verify the frozen SHA-256 above.
2. Create a manifest for each requested ZIP and checksum sidecar. Download only within the frozen period plus the minimum indicator warm-up; do not inspect post-window price or funding values.
3. Verify ZIP CRC and SHA-256; parse schema, UTC timestamp units, unique/monotonic rows, 1h continuity, daily aggregation, funding-event timestamps/rates/mark prices, and coverage. Report all holes; never fill them silently.
4. Add synthetic tests for no lookahead at signal-to-next-open entry, exact-time funding exclusion, exits after 20 sessions, deterministic score ties, same-symbol non-overlap, fee/funding ledger reconciliation, blend identity, exclusive end boundary, and deliberate future-row mutation invariance.
5. Run the baseline and candidate once. No threshold, universe, cost, start-date, or weight changes after outcomes are read. Any necessary engine correction must be logged before outcome computation and invalidate this registration if it alters a frozen rule.

## Decision language

- Any result is an exploratory historical portfolio-interaction diagnostic on a survivor universe whose component strategies were already selected using overlapping historical evidence.
- A favorable result may justify a separately registered forward/paper evaluation, but it does not pass the crypto signal M2 gate, validate the 80% target-first objective, remove survivorship bias, or authorize live/manual signals.
- A non-favorable result rejects this specific fixed blend as a portfolio complement under the stated data and accounting contract; it does not imply all possible strategies fail.
- No raw market-data files are committed. Commit only code, manifests with hashes/coverage, synthetic tests, and the report.
