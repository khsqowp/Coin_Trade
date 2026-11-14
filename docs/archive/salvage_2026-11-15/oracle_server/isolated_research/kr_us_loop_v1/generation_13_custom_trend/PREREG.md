# Generation 13 — DMI / Choppiness hysteresis trend state (SPY)

Status: frozen candidate proposal; **not authorized for market-data execution**. No market values, signals, or performance metrics were read or computed while preparing this preregistration.

## Candidate and hypothesis

One US broad-market, long-or-cash rule: `SPY_DMI14_CHOP14_HYSTERESIS_382_618`. The hypothesis is that directional movement dominance may identify direction while a separate path-efficiency/choppiness statistic distinguishes directional movement from a range-bound market. Hysteresis is intended to avoid changing exposure at one boundary: enter only in a low-chop state, but retain an existing position until chop becomes materially higher or directional dominance reverses. This is a plausible hypothesis, not a claim that it will work.

This is a custom combination of directional movement and the Choppiness Index. The available source implementation supplies a daily directional-movement/ADX family; the exact candidate rule below is a new specification, not a source-code port. It is **not an independent alpha family**: it is adjacent to Generation 03 Vortex / trend-state work, Generation 02 ADX-related/catalog research, and the source catalog’s directional-movement and trend-filter families. It must count as an additional dependent trend-rule trial.

## Duplicate audit (bounded, preregistration-only)

The inspected prior registrations show the following near-duplicates or related families:

- Gen 01 tested `KAMA_ER20`, `PERSIST63`, moving-average trend and momentum rules.
- Gen 02 tested Theil–Sen, multi-window OLS, sign-flip persistence, Kalman drift, Ehlers SSF, and breadth; none is this exact DMI-plus-Choppiness hysteresis rule.
- Gen 03 tested `VORTEX14_SMA100`, `FRAMA16_SLOPE5`, current-cloud Ichimoku, and other close-based trend/pivot rules. Vortex uses directional movement, so this candidate is materially related, although it substitutes Wilder DMI with a separate Choppiness state and does not use SMA100.
- Gen 04 and the source-catalog inventory document ADX/DMI/PSAR/Aroon/OBV/CMF and related daily trend families. The source inventory is not a complete proof that this exact combination was never run elsewhere.
- Gen 10 tested an NR7 price-range breakout; Gen 11 tested a volatility burst plus positive short-horizon momentum and breadth gating; Gen 12 tested downside-risk exposure control. Those exact rules differ, but are not independent evidence from this candidate.
- No inspected `PREREG.md` specifies the exact combination of DMI14 direction with Choppiness14 entry/exit hysteresis at 38.2/61.8. This is a bounded text audit, not proof of global novelty. Existing local historical screens and prior trial records may be incomplete.

## Signal definition and information timing

Instrument: SPY only. Long-only, unlevered, target exposure either 100% or 0%; no shorts, partial sizing, overlapping positions, stops, profit targets, or additional instruments.

Use the local SPY daily OHLCV snapshot. For each observed day, define adjusted OHLC as raw O/H/L/C multiplied by `AdjClose / Close`. All indicators use these consistently adjusted OHLC values. The vendor adjustment convention is not independently verified; report this limitation.

At each close `t`, compute the following over observed sessions:

1. On the first row of a continuous valid series, `TR_0=H_0-L_0` and `+DM_0=-DM_0=0`. For each later row, `TR_t = max(H_t-L_t, abs(H_t-C_(t-1)), abs(L_t-C_(t-1)))`.
2. For each later row, `up_t=H_t-H_(t-1)` and `down_t=L_(t-1)-L_t`. `+DM_t=up_t` only when `up_t > down_t` and `up_t > 0`, otherwise zero. `-DM_t=down_t` only when `down_t > up_t` and `down_t > 0`, otherwise zero. Ties produce both zero.
3. For `TR`, `+DM`, and `-DM`, use period-14 Wilder smoothing: seed each series with the arithmetic mean of its first 14 consecutive valid observations; thereafter `W_t=(13*W_(t-1)+x_t)/14`. No implicit pandas/EWM seed convention is permitted. `DI+ = 100 * smoothed(+DM) / smoothed(TR)` and `DI- = 100 * smoothed(-DM) / smoothed(TR)`. If the denominator is nonpositive or nonfinite, the feature is unavailable and the attempt fails closed.
4. `CHOP14_t = 100 * log10(sum(TR_(t-13)..TR_t) / (max(H_(t-13)..H_t)-min(L_(t-13)..L_t))) / log10(14)`. Require all 14 consecutive valid TR/H/L observations and a finite positive range; otherwise unavailable/fail closed.

The binary state updates once per observed close, after all values for `t` are known:

- If currently flat, enter state 1 only if `DI+_t > DI-_t` **and** `CHOP14_t < 38.2`.
- If currently long, exit to state 0 if `DI+_t <= DI-_t` **or** `CHOP14_t >= 61.8`.
- Otherwise retain the prior state. In particular, when already long, CHOP in `[38.2, 61.8)` does not force an exit; when flat, it does not permit entry.
- Before the first complete indicator state, remain flat. No backfilled warm-up state.

The close-`t` state first becomes the target at the next observed session's open. It must not receive any return interval ending at that open. No signal is evaluated from a partial session or from future-aligned data.

## Accounting, costs, and benchmark

- Measure returns from adjusted open to adjusted open on consecutive observed dates. At each open, first mark the prior target through the just-completed open-to-open interval, then trade to the target determined by the preceding close. This prevents a close signal from earning the prior interval.
- Charge 10 basis points per unit of absolute traded notional at each entry, exit, or state change: wealth is multiplied by `(1 - 0.001 * abs(target_weight - drifted_weight))`. For this binary unlevered target, the target change is 0 or 1; calculate drifted weight from marked wealth before turnover. Cash return is zero. No cash yield, financing, tax, market-impact model, or intraday fills are assumed.
- Start the strategy and benchmark on the first common eligible open. Charge the benchmark 10 bp at initial entry and terminal liquidation. At the final open, first earn the preceding interval, then liquidate the strategy’s carried exposure and charge its exit fee. Do not enter a terminal position that cannot earn a subsequent interval.
- Primary benchmark: SPY adjusted-open buy-and-hold on the identical eligible open-to-open intervals and with the same entry/terminal cost convention.
- Report net CAGR, annualized Sharpe (252), maximum drawdown, mean exposure, exposure transitions, total traded notional, time invested, and cost drag. The strategy and benchmark must use identical curve dates; any non-finite wealth, invalid gross return, or mismatched interval count fails the attempt.

## Fixed descriptive partitions and interpretation

Report one continuous portfolio over (a) the full eligible sample, (b) 2001-01-02 through 2016-12-30, and (c) 2017-01-03 through the final eligible date. For descriptive partition drawdown, reset only the reporting baseline; do not reset portfolio state or create trades/fees at boundaries. These windows have already been examined in previous research and are **not OOS**. No statistical-significance, DSR/PSR/BH, untouched-OOS, or investment-suitability claim is authorized. The exact global historical trial count and market-data vendor provenance remain unresolved.

## Frozen decision and stop gates

Exactly one rule, one SPY input, one execution attempt. No threshold changes, alternate periods, KR transfer, subperiod selection, or post-result rerun. The candidate is rejected for the stated all-window trend-timing objective if net CAGR **or** Sharpe fails to exceed matched SPY buy-and-hold in any one of the three display windows. Drawdown, exposure, turnover, and costs remain mandatory context even when this gate passes. A descriptive pass is only a lead for a separately preregistered study on validated PIT data and an untouched prospective holdout.

Input/calendar/implementation/hash/serialization failure is `FAILED`, not a performance rejection. Preserve every artifact; do not repair or silently omit rows. No source, signal, or accounting change after freeze. Any required correction needs a dated addendum, a new candidate identifier, and an explicit root authorization before reading performance.

## Pre-run gates (must pass before root GO)

1. Synthetic indicator tests: hand-computed TR/+DM/-DM/Wilder seed and recurrence; period-14 CHOP formula; threshold equality; ties; flat/range data; warm-up; missing, duplicate, nonascending, and invalid OHLC rejection.
2. Causality: perturb values strictly after cutoff `t`; all indicator values and states through `t` remain identical. Prove a state decided at close `t` first changes exposure at open `t+1`.
3. Accounting: hand-computed multi-interval long/flat example including drifted weight, entry/exit costs, terminal liquidation, benchmark alignment, and no exposure above 100%.
4. Independent review of code, exact input/source hashes, warm-up, execution clock, fees, fixed partitions, and one-run limit. Write durable `STARTED` before loading performance values and durable `FAILED` on any exception.
5. Before root GO, record SHA-256 for this preregistration, the finalized runner and tests, the exact SPY input, and imported helpers. Independently verify every digest. The SPY market file was not hashed or read in preparing this preregistration.
6. Before any market-value read, require an authoritative, provenance-documented NYSE Arca session calendar that exactly matches normalized SPY dates over the entire frozen input interval. Never infer sessions from observed bars, weekdays, or price-file gaps. The local mirror currently has no such calendar artifact (see `generation_12_volatility/ADDENDUM_A2.md`); until one is supplied and independently pinned, status is `DATA_BLOCKED`, not a strategy failure, and no performance run is permitted.

## Source and duplicate-audit fingerprints

Source idea/code inspected (read-only):

| File | SHA-256 | Relevant lines | Use |
|---|---|---:|---|
| `trading/app/rs_map_off_fam_a.py` | `efdf2e80b0cd32e4d63ebb17fc162d71cd9425e33dc0137728ab62e9e71da954` | 48–60, 371–376 | Directional movement/ADX definitions motivating a directional-state family; candidate calculation above is newly specified and must be implemented independently. |
| `trading/docs/research/kr_us_loop_v1/generation_01/PREREG.md` | `43f6747d59bc7e623ab82a06d9baaa369bcd72517a7d3ad1a5ab64bb8af98213` | 29–34 | Duplicate audit: KAMA, persistence, moving average, and momentum rules. |
| `trading/docs/research/kr_us_loop_v1/generation_02/PREREG.md` | `9f1fc16657cd1161b3eb41fdc672514c5b8bd4c092902fbb643f71fc4fcca04a` | 9–20 | Duplicate audit: trend estimators, sign persistence, Kalman, SSF, breadth. |
| `trading/docs/research/kr_us_loop_v1/generation_03/PREREG.md` | `1ae3c7a74a3882b8a5cf0b1fbb9c7cc559e145e2416cb98c6b594188f5ef1d68` | 12–18 | Duplicate audit: Vortex14/SMA100 and other OHLC trend families. |
| `trading/docs/research/kr_us_loop_v1/generation_04/PREREG.md` | `29da9a81922ceccb6c432bec87b1b6e932c60bd5b9d70db6dad1664f81cd25b7` | full file | Related TEMA/CLV transfer research. |
| `trading/docs/research/kr_us_loop_v1/generation_11_trend/PREREG.md` | `454704a4937d13f8a0f4bb82ec7a3d672a21ad88f781eab2739bb046bda7672f` | full file | Related volatility-expansion plus momentum candidate. |
| `trading/docs/research/kr_us_loop_v1/generation_12_volatility/PREREG.md` | `cb31e994c862e3154336f738404855add57b18d2df65efb3b14f336f398e7296` | full file | Adjacent risk-overlay candidate; not this trend rule. |

This is a bounded duplicate review of named local registrations, not a proof that no unrecorded historical test exists. No market-data values, signals, or performance statistics were accessed or computed for this task.
