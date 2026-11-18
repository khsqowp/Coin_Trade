# Micro-candle phase 5 — one-bar body-dominance feasibility preregistration

Status: frozen before the label-blind frequency screen. This is an exploratory candidate on previously exposed development data, not sealed OOS evidence.

## Question and mechanism

Does an unusually dominant one-minute candle body, with little combined wick, indicate enough immediate directional order-flow agreement to forecast a short-horizon continuation? This begins with one completed candle only; no macro regime, indicators, market-wide context, cross-symbol features, or longer pattern is allowed.

## Exact rule

- Anchor `t` is a completed, valid, UTC-aligned 1-minute candle.
- Let `range = high[t] - low[t]`, `body = abs(close[t] - open[t])`.
- Emit LONG iff `close[t] > open[t]` and `body / range >= 0.80`.
- Emit SHORT iff `close[t] < open[t]` and `body / range >= 0.80`.
- Doji, zero-range, malformed, non-finite, off-grid, or non-contiguous input rows are invalid. No threshold sweep or alternate candle anatomy is included.
- Forecast is issued only after candle `t` closes. Intended executable entry is the next contiguous 1-minute candle open.

## Label-blind feasibility gate only

- Input is the `candles` table in `candles.sqlite`, opened read-only. Freeze the intended snapshot by SHA-256 `cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1` (1,864,249,344 bytes). Keep every symbol; contract-underlying metadata is not proven, and this remains an exploratory archive.
- Fixed completed-candle cutoff: `2026-11-14T00:29:00Z` (Unix ms `1794616140000`). Include a candle only when `t_open_ms + 60,000 <= cutoff`; the snapshot's last included open is `2026-11-14T00:28:00Z`. Reject a different content hash. Hash before and after the read-only scan and reject any mismatch. Require non-WAL journal mode and no SQLite `-wal`, `-shm`, or `-journal` sidecars so the hash identifies the queried database state.
- Denominator: every valid completed one-minute anchor in the fixed snapshot after per-symbol timestamp continuity and OHLC integrity checks.
- Report scheduled anchors, signal count/coverage, long/short counts, active symbol count, and chronological per-symbol cooldown counts for both 10- and 20-minute cooldowns. The 10% threshold is inherited unchanged from the prior micro-candle feasibility protocol as a candidate-availability gate, not an efficacy or statistical-power threshold.
- Do not read any row after a candidate anchor, calculate next-candle direction, build ATR, or access target/stop/outcome labels in this stage.
- Continue only if raw coverage is at least 10%, at least 20 symbols emit, and the outcome-blind non-overlap count is at least 200 under each horizon's cooldown. Otherwise reject before opening outcome paths.

## If and only if the feasibility gate passes

Require an independent review of this frozen rule before a separate outcome-evaluation run. The existing phase-4 execution contract remains unchanged: next contiguous 1m open; causal 14-bar mean true range at the signal anchor; 1R stop and 1R target; 10- and 20-minute horizons evaluated separately; stop-first same-bar tie; adverse stop-gap fills; timeout is not M2 success; unresolved paths remain visible. Report all-issued M2, separate outcome-blind non-overlap N, deadline direction, same-anchor momentum and deterministic random baselines, assumed 14 bp base/28 bp stress round-trip costs, funding omission, per-symbol results, and calendar-time folds.

Primary gate remains M2 target-first >=80%, positive cost-adjusted expectancy, and no material disadvantage versus either matched baseline. Exposed historical data can only yield a development result, never independent confirmation or live approval. Monte Carlo, WFA refinements, and parameter-plateau work are not run for a candidate that fails its primary screen.

## Prior-art distinction and limitations

Local reviewed pattern code includes engulfing, hammer/pin, stars, doji, inside-bar, volume-climax wick rejection, Heikin-Ashi reversal, and multi-bar breakout/compression families. The rule above uses only one-bar body dominance and body sign; it is not claimed globally novel. Before outcome access, reviewers must confirm it is not duplicated by a local setup or older research report. It is a candle-shape proxy, not verified aggressor flow or order-book imbalance.
