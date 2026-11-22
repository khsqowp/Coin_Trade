# `dist/data.json` data contract

Forward gate: l5 profiles require at least 30 closed trades and 90 days; jbb requires 100 closed trades and 60 days. Below either threshold, decision_label is 데이터 부족; after both thresholds it is 판정 가능. confirmed is true only when the threshold is met, marked net return after costs is positive, and the linked backtest verdict is known and not rejected. Otherwise confirmation_label is 확정 아님. A zero-trade profile sets no_signals: true and is displayed as 아직 신호 없음(정상). Unknown 12-hour backtest period length keeps pace-adjusted expectations null.

Only a strategy with an explicit profile link changes its graph-node color. The two L5 profiles have no strategy ID in the archive, so they remain visible in the forward band without guessing a node mapping.

The output is UTF-8 JSON. `generated_at` is the only build-time timestamp and is excluded from fixture snapshot comparison. Paths in the dataset are trading-root-relative; host absolute paths and email addresses are not emitted.

Top-level fields:

- `counts`: `total_archived`, `spec_complete`, `implemented_tested`, `trials_counted`, `adjusted_passed`, `adjusted_tested`, `confirmed_real_winners` (non-negative integers). `trials_counted` is the maximum `n_candidates_tested` value in `results/ledger.csv`, avoiding duplicate addition across ledger strategy rows.
- `headline`: exact user-facing phrase `Confirmed real winners: N`.
- `adjusted_sentence`: adjusted PASS count over rows with an adjusted verdict.
- `depth_test_sources`: ordered source map for each depth flag, including its relative file and tested column/rule.
- `nodes`: one record per strategy ID, selected timeframe, and direction.
- `edges`: metadata similarity links plus optional measured return-correlation links. Every edge has `source`, `target`, `edge_kind`, `label`, and `weight`; correlation links additionally include `correlation` and their relative `source_file`. The 3D view maps measured correlation weights to line thickness, opacity, color, filtering, and spring distance. Metadata similarity remains a separate approximate edge kind.
- `forward`: one record for each `l5_4h`, `l5_12h`, and `jbb_1h`; unavailable databases have `loaded: false` and `verdict: "not loaded"`.

The current 3D interface requires no additional JSON fields; it uses the existing edge weights and node metadata, and preserves the existing build calculations. Node fields include identity and archive metadata (`id`, `strategy_id`, `timeframe`, `side`, `name`, `family`, `symbol_class`, `symbols`, `description`, `source_url`, `spec_complete`, `implemented`), verdict fields (`verdict`, `raw_verdict`, `adjusted_verdict`), `verification_depth`, `tests`, and secondary evidence (`params`, `train_return`, `test_return`, `null_percentile`, `per_year`, `forward`). Return fields never contribute to `verification_depth`.

Each `tests` entry has `name`, `status` (`passed`, `failed`, or `not_run`), `source_file` (relative path or empty string), `source_column`, and `plain_reason`. Test order is `null`, `plateau`, `adjusted`, `A1`, `B1` through `B6`, `execution_stress`, `regime`.

Verdict color keys: `not_tested` (gray), `failed` (red), `downgraded` (orange: raw PASS but adjusted verdict is not PASS), `adjusted_pass` (yellow), `forward_running` (green), and `forward_confirmed` (bright green). A linked profile sets forward_running; forward_confirmed requires the explicit gate above.

Depth rules: null passes at percentile >=95; plateau passes recorded `PASS`, `ROBUST`, `TRUE`, or `YES`; adjusted passes only exact `PASS`; A1 passes only `A1=PASS`; B1-B3 use their candidate-specific B1/B2/B3 failure labels in the `FINAL` tag; B4 requires recorded positive `walk_forward_pct`; B5 passes when failed years are no more than half of the recorded years; B6 passes only `status=PASS`; execution stress requires positive return at 2x cost; regime passes if any recorded V1/V2/V3 row has `PASS=true`. Missing data or missing columns yields `not_run`, never a failure. A loaded `jbb_1h` forward database is joined to the known `jesse_simple_bollinger` strategy ID; the two L5 profiles are shown in the forward band without assuming their archive identity.
