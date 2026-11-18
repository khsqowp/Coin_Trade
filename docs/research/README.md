# docs/research — start here

This directory accumulated ~100 one-off result files from two separate
sprints (2026-11-07 "oracle" equity-factor work, 2026-11-15 "agent loop"
equity+coin work) with no central index. If you are looking for "did we
already test X", **do not grep this directory by hand** — read
[`INDEX.md`](INDEX.md) first.

## The registry

[`registry.jsonl`](registry.jsonl) is the append-only source of truth: one
line per tested hypothesis (coin or stock), with its scope, headline
result, verdict, and a pointer to the full write-up. `INDEX.md` is a
generated view of it — never edit `INDEX.md` by hand, it is overwritten.

To log a new experiment or rebuild the index, see the usage docstring in
[`../../scripts/research/registry.py`](../../scripts/research/registry.py):

```bash
python3 scripts/research/registry.py list                  # browse
python3 scripts/research/registry.py list --verdict REJECT
python3 scripts/research/registry.py show 42                # full row
python3 scripts/research/registry.py rebuild-index           # after hand-editing jsonl
```

Any new backtest/probe script should call `log_experiment(...)` from that
module right after it has a result, instead of leaving a report file for
someone to find later by accident.

## Where the long-form write-ups live

- `docs/chart_predictor/rounds.md` — coin chart_predictor P4-P9 series (26
  rule-based setups, all against the 1/5/30/60m target-first hit-rate bar).
- `docs/research/agent_strategy_research_rounds_20261115.md` — the
  2026-11-15 sprint's own Round 1-7 (KR/US equity momentum + factor probes,
  coin signal/boundary diagnostics).
- `docs/research/strategy_research_round4_20261115.md` — an umbrella doc
  that actually covers Rounds 4 through 11 of that same sprint (misleading
  filename; every `round4_*`/`round5_*`/.../`round9_*` registry row below
  Round 7 points here unless noted otherwise).
- `docs/research/crypto_round10_liquidity_sweep_preregistration_20261115.md`,
  `docs/research/crypto_round11_streak_results_20261115.md`,
  `docs/research/equity_kr_compression_breakout_results_20261115.md` — three
  rounds that got their own dedicated files instead of the umbrella doc.
- `docs/research/kr-us-systematic-strategy-log.md` — the 2026-11-07 sprint's
  first pass, blocked entirely on data rights/point-in-time coverage before
  any strategy could be scored (0/2 valid).
- `docs/archive/salvage_2026-11-15/oracle_server/isolated_research/kr_us_loop_v1/`
  — the 2026-11-07 sprint's later generations (Gen02 through Gen18), moved
  to archive after three independent reviewers agreed no new hypothesis was
  left to try (`FEASIBILITY_BLOCKED`). `Gen17-low_skew-toy`'s 7/21-symbol
  "passing" low-skewness factor is the one historical result worth knowing
  about: it numerically cleared the CAGR/MDD/Sharpe bar, but only on a toy
  universe, and the 2026-11-18 `Round4` re-test on the full 92-symbol cache
  shows it does not survive.
- Everything else under `docs/research/` not listed above (`alpha.md`,
  `risk.md`, `cadence.md`, `map_api.md`, `strategy_catalog.md`, the
  `PREREG_*`/`ADDENDUM_*` gen14-18 files, etc.) is **not yet triaged into
  the registry** — it reads as coin live-trading ops/infra tuning (circuit
  breakers, cadence staggering, profit-lock patches) for the already-chosen
  momentum-rotation strategy rather than a pass/fail hypothesis test, so it
  does not fit this registry's schema as-is. Treat it as untriaged, not as
  confirmed-irrelevant.

## Conventions

- Never retroactively edit a past registry row's `verdict` or
  `headline_metric` after you've seen a later, better result — append a new
  row instead (e.g. `Gen17-low_skew-toy` stays `VALIDATION_REQUIRED`;
  `Round4` is the separate row that supersedes it with `REJECT`). The
  registry is a lab notebook, not a leaderboard.
- `bar` should name the pre-registered pass/fail threshold that was active
  *at the time*, not today's threshold, if they differ.
- One row per named round/phase as it appears in the long-form doc, not one
  row per grid cell — the long-form doc is still the place for full detail.
