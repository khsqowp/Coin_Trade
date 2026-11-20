# Preregistration: contract–mark deviation mean-reversion M2 diagnostic

Frozen: 2026-11-21, before price-outcome scoring. Status: **FROZEN**. This is one historical,
exploratory diagnostic only. It is not an untouched OOS test, an execution
simulation, or a Core approval. No further parameter choice is allowed from
this run.

## Hypothesis and overlap review

At an extreme and newly crossed contract-close/mark-close deviation, the
contract price is more likely to mean-revert than continue in the deviation
direction over the next 10 minutes. The 20-minute result is a prespecified
secondary horizon. This is a custom hypothesis, not a reproduction of an
external strategy. It is not the spot–perpetual basis: both series are from
the same USD-M contract, with the mark series used only as the signal anchor.

Before registering this test, the research registry and source rounds were
checked. The 15-minute candle-boundary candidate was not advanced because
registry row 23 already tested it (47–49% target-first in the six-symbol
probe, with negative cost-proxy net returns). The pre-settlement direction
candidate was rejected because its source and prior work do not support a
new minute-scale directional rule. Pine CVD/flow candidates overlap prior
families or require lower-frequency inputs. Candidate B is therefore the
only candidate in this run. It remains at risk of overlap with broader
mean-reversion/basis research and cannot be called novel alpha without a
separate registry review.

## Frozen market data and interval

- Market: Binance USD-M perpetuals; price, mark price, and historical funding.
- Signal interval: 1 minute; timestamps are UTC candle **open** times in
  milliseconds. Each candle represents `[open_time, open_time + 60s)`.
- Scoring interval: `2026-07-01 00:00:00 UTC` inclusive to
  `2026-11-01 00:00:00 UTC` exclusive. Each signal must have a full 20-minute
  forward path inside this interval.
- Price/mark audit cohort: the 35 symbols listed in the data audit; funding
  intersection and fixed scoring cohort (34 symbols):
  `1000PEPEUSDT`, `1000SHIBUSDT`, `AAVEUSDT`, `ADAUSDT`, `APTUSDT`,
  `ARBUSDT`, `ATOMUSDT`, `AVAXUSDT`, `BCHUSDT`, `BNBUSDT`, `BTCUSDT`,
  `CRVUSDT`, `DOGEUSDT`, `DOTUSDT`, `ENAUSDT`, `ETCUSDT`, `ETHUSDT`,
  `FILUSDT`, `HBARUSDT`, `INJUSDT`, `LINKUSDT`, `LTCUSDT`, `NEARUSDT`,
  `OPUSDT`, `POLUSDT`, `RUNEUSDT`, `SEIUSDT`, `SOLUSDT`, `SUIUSDT`,
  `TIAUSDT`, `TRXUSDT`, `UNIUSDT`, `WLDUSDT`, `XRPUSDT`.
- The window is historical and overlaps dates whose hourly aggregates were
  used in prior studies. Candidate-specific minute outcomes were not opened
  during this continuation, but the interval is **not pristine or prospective**.
  Any score is diagnostic only.
- The NAS-side external manifest is actively growing as unrelated downloads
  complete, so its whole-file row count and hash are not frozen. The 416 files
  required for this exact interval (140 contract, 140 mark, 136 funding) are
  fixed and present. Their selected manifest records, byte counts, and SHA-256
  hashes are checked before the runner reads price outcomes; unrelated manifest
  appends do not invalidate this fixed input set. All 280
  contract/mark files passed exact expected monthly row-count and 60-second
  timestamp-grid checks. The downloader source code references official
  `data.binance.vision` objects and validates publisher `.CHECKSUM` responses
  when present; original ZIP hashes/responses were not retained. Local hash
  agreement proves identity with the current manifest, not independent
  publisher attestation.
- The NAS archive is read-only input. No market data is copied into this repo.

## Signal, entry, exits, and event handling

Let `b[t] = ln(contract_close[t] / mark_close[t])`. At the close of minute
`t`, compute `mu[t]` and sample standard deviation (`ddof=1`) from exactly the
previous 60 completed `b` observations `[t-60, t)`. Then
`z[t] = (b[t] - mu[t]) / sd[t]`. The current observation is not in the
normalization window. Missing/nonpositive prices, non-finite values, zero
standard deviation, or missing history produce no signal.

- Short trigger: `z[t-1]` is within the closed interval `[-2,+2]` and
  `z[t] > +2`.
- Long trigger: `z[t-1]` is within `[-2,+2]` and `z[t] < -2`.
- No repeat trigger while `z[t-1]` is already outside the band. A signal
  suppressed by the position lockout is discarded, not queued.
- Signal time is the completed candle close `open_time[t] + 60s`. Entry is
  assumed at the next candle's contract `open`; this is an OHLC proxy, not a
  demonstrated fill.
- Risk distance is the arithmetic mean of true range over the 14 completed
  contract candles ending at `t`, inclusive. True range is
  `max(high-low, abs(high-prev_close), abs(low-prev_close))`.
- At the next candle open, freeze a 1.0×ATR target and a 1.0×ATR stop around
  entry in the signaled direction. A nonpositive or non-finite ATR or invalid
  entry excludes the event before outcome scoring and is counted as an
  invalid issued trigger.
- Primary outcome horizon is 10 complete 1-minute candles after entry.
  Secondary horizon is 20 complete candles. Both are scored on the same
  accepted signal anchors; report both and do not select one after seeing
  results. For each H, inspect the H future bars beginning with the entry
  candle. Timeout exit is the close of the H-th future candle.
- Use contract OHLC for price barriers. If target and stop are both touched
  in one candle, stop wins. A stop gap fills at the adverse candle open; a
  target gap receives no improvement beyond the fixed target. A target/stop
  touch is recorded at the barrier. OHLC cannot reveal the true within-minute
  path; these are conservative simulation conventions, not fills.
- One position per symbol. Accepted entries for a symbol are separated by at
  least 20 minutes. If entry is at `E`, a signal decision at `t < E+20m` is
  suppressed; a decision exactly at `E+20m` may enter at the next minute open.
  Signals during lockout are counted as suppressed, never queued. Invalid
  ATR/entry triggers are counted separately from lockout suppression.
- M2 success means target touches before stop. Stop-first same-candle
  collisions and timeouts are failures. Report all accepted signals and the
  per-symbol non-overlap sample separately from simultaneous cross-symbol
  UTC-time clusters.
- M1 is separately reported: direction of the H-th future candle close
  relative to the signal candle close. It is not substituted for M2.

## Funding and cost accounting

Use the archived realized funding event only as a holding cost, never as an
entry feature. A funding event is charged when
`entry_ms < calc_time <= exit_candle_close_ms`; if an event shares the exit
minute with an intrabar target/stop, charge it conservatively. The signed
funding return per unit entry notional is
`-side * funding_rate * mark_open_of_calc_time_minute / entry_price`, where
`side` is +1 for long and -1 for short. Funding timestamps can contain
millisecond jitter; they map to the containing UTC minute only if they are no
more than 1,000 ms after its start. Missing, duplicate, out-of-order,
off-grid, or interval-inconsistent funding events fail input QA; they are not
silently filled with zero.

Subtract the audited legacy 10 bp and 30 bp **round-trip fee proxies** from
gross return, plus signed funding. These proxies do not include measured
spread or slippage. No BBO or execution-quality claim is possible from this
dataset. Report gross and both fee-proxy net results; label net results as
conditional diagnostics, not realistic or executable returns.

## Baselines and frozen decision gates

At each accepted candidate event, score two controls with the same entry,
ATR barriers, and horizon:

1. Previous-candle direction (momentum): long if the immediately preceding
   contract close-to-close return is positive, short if negative; exact zero
   yields no control trade.
2. Deterministic random side from SHA-256 of the fixed seed, symbol, and
   signal close timestamp. It is a reproducibility control, not an optimized
   random benchmark.
3. Always flat: zero signals and zero coverage; no M2 denominator.

The primary decision uses H=10 only and requires all of:

- M2 target-first point estimate ≥80%.
- 95% Wilson lower bound above the same-event previous-candle momentum
  baseline M2 point estimate.
- At least 200 accepted per-symbol non-overlapping events and at least 20
  scoring symbols; report unique UTC timestamps, UTC-day clusters, and
  simultaneous cross-symbol clusters because these events are not all
  statistically independent.
- Candidate coverage ≥10% of all eligible symbol-minute opportunities after
  warmup and before the fixed interval end.
- Positive mean return after both 10 bp and 30 bp round-trip fee proxies and
  realized funding.

H=20 is prespecified secondary evidence, not an alternate route to pass.
Also report day-block bootstrap uncertainty (7-day circular blocks, 1,000
replicates, fixed seed 20261120), M1, per-symbol outcomes, baseline results,
and all invalid/suppressed triggers. No parameter/horizon selection or
re-run based on results. Failure of a gate rejects this fixed candidate for
progression; passing this historical diagnostic still does not qualify a
Core, validate execution, or replace future forward evidence.

## Frozen implementation and reproduction

- Runner: `scripts/research/mark_deviation_m2_probe.py`.
- Unit tests: `tests/test_mark_deviation_m2_probe.py`.
- Input root must be passed explicitly with `--root`; no path is inferred.
- Reproduction command and file/code/prereg fingerprints are captured in the
  generated run directory. Preflight is performed before signal/outcome reads.
- The strategy research status is one registered trial. All candidate and
  parameter choices in the broader project remain part of the research-wide
  multiple-testing history; this diagnostic does not erase or replace it.
