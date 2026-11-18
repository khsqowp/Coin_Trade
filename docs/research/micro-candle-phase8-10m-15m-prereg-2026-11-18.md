# Phase 8 preregistration — fixed micro-patterns at 10m and 15m scale

Status: new scale-only replication after Phase 7 rejected the same fixed candle rules at 3m and 5m. Freeze before Phase 8 frequency/outcome runs. This is still price-only local-pattern research; no macro context is introduced.

## Question

Do the frozen body-dominance and two-candle sweep/reclaim rules retain target-first behavior on UTC-aligned 10-minute and 15-minute aggregate candles, with 10- and 20-bar expiries? This broadens candle scale without changing either signal definition or tuning parameters.

## Frozen input and candle construction

- Use `chart_predictor/data/candles.sqlite`: 100 symbols, 1m rows through completed cutoff `2026-11-14T00:29:00Z`, 1,864,249,344 bytes, SHA-256 `cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1`.
- Open read-only; reject a different size/hash, SQLite sidecar, WAL mode, schema, or symbol count.
- For N=10 and N=15, bucket each 1m open by `bucket_start=floor(open_ms/(N*60,000))*(N*60,000)`. Require exactly N valid rows at timestamps `bucket_start + j*60,000`, `j=0…N-1`. OHLC is first open, maximum high, minimum low, last close. No partial bucket, forward fill, or missing minute is allowed. Aggregate availability is `bucket_start+N*60,000` and must be at/before the frozen cutoff.
- Use the same five UTC half-open folds as Phase 7, assigning signal membership by aggregate-candle availability. Signal availability exactly on a fold boundary belongs to the fold starting there. A known completed prior-fold candle may be used as history; an outcome path may not cross its assigned fold end.
- The archive and folds are previously exposed development data, not independent OOS evidence. The fixed symbol list is not a point-in-time membership/delistings universe.

## Frozen signals

1. **Body dominance:** LONG iff `close>open` and `abs(close-open)/(high-low)>=0.80`; SHORT iff `close<open` and the same ratio is at least 0.80. Doji and zero-range bars do not signal.
2. **Sweep/reclaim:** on adjacent aggregate `bar1`,`bar2`, LONG iff `low2<low1`, `high2<=high1`, and `(high1+low1)/2<close2<high1`; SHORT iff `high2>high1`, `low2>=low1`, and `low1<close2<(high1+low1)/2`. If both extremes are swept or adjacency/validity fails, no signal.

No indicator, volume, BTC regime, session, cross-symbol, news, or macro filter. No threshold changes, side inversion, parameter rescue, or post-result candidate additions.

## Entry and outcome contract

- Signal only after aggregate bar close; enter at next contiguous aggregate-bar open.
- Body dominance: causal ATR(14) simple mean of aggregate true range through the signal bar; all 14 true ranges and the prior closes required to calculate them must come from valid contiguous aggregate bars. Missing ATR/entry/path keeps the issued signal unresolved.
- Sweep/reclaim: stop at bar2 extreme; target is 1R from next-open entry using positive entry-to-stop risk. If the next open is at/beyond the stop, retain it as a resolved no-trade failure, zero success/PnL, no fee; report separately and exclude only from resolved-tradable mean net R.
- Evaluate H=10 and H=20 aggregate bars: 10m gives 100/200 minutes; 15m gives 150/300 minutes. The entry bar is outcome bar 1; deadline exit if barriers are not hit is Hth bar close. Stop wins a same-bar tie; adverse-open stop gap, target barrier fill.
- Unresolved/missing/malformed/discontinuous/cutoff- or fold-crossing paths stay in all-issued M2 and count as zero successes. All-issued M2 = target-first count / all emitted signals. No-trade signals also count as zero successes. Report the resolved-tradable denominator separately.
- Costs: round-trip fractions 0.0014 base and 0.0028 stress. `gross_return=side*(exit_price/entry_price-1)`, `risk_fraction=abs(entry_price-stop_price)/entry_price`, `net_R=(gross_return-cost_fraction)/risk_fraction`. M2 is not cost-adjusted; funding omitted.
- Controls use identical anchors/horizons. Body momentum is identical to candidate by construction and is a plumbing identity check only; body random control uses candidate entry and ATR risk with its own side-specific barriers. Sweep momentum uses bar2 body sign (flat uses deterministic SHA side); random uses deterministic SHA-256 with seed `20261118`, key `seed|tag|symbol|signal_close_ms`. Each sweep control uses its own side and corresponding bar2 extreme as stop. Any control entry at/beyond its own stop is a zero-success all-anchor no-trade, no fee/PnL, separately counted.

## Label-blind frequency gate

First report complete aggregate opportunities, signal side/count/coverage by symbol and fold, and actual-timestamp non-overlap counts for all 8 rule × size × horizon cells. Earliest signal per symbol/fold/cell is selected; skip until the prior H-bar outcome expires. The outcome interval is next bar through Hth bar inclusive; a signal available exactly when that prior Hth bar closes is admissible. Signals remain in frequency/all-issued counts when next entry or outcome is unavailable. **Do not run any Phase 8 outcome evaluation unless all eight cells individually have non-overlap N≥200 across at least 20 symbols.** A frequency failure blocks the whole Phase 8 result-label stage; do not pool, tune, or rescue it.

## Decision gates

- Cell must satisfy all: all-issued target-first M2≥80%, mean net R after 14bp >0 across resolved tradable events, M2 not below either matched control, path resolution≥95%, non-overlap N≥200 across≥20 symbols, and scalar/vector audit has resolved/tradable/no-trade samples as applicable, zero label/no-trade mismatches, and max net-R error<1e-12.
- Frequency/implementation gate failure is inconclusive. Performance failure after all data gates pass rejects that exact fixed rule/scale/horizon. No parameter tuning or Monte Carlo rescue.
- Report all eight cells; do not select a winner as confirmation. A survivor is only a review trigger and requires truly untouched prospective data plus dependence-aware inference before promotion.
