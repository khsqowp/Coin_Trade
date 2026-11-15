# R004 handoff

## Current state

- R004 registration was amended and the final train/validation screen completed after code corrections.
- Validation selected **zero** timeframe/exit candidates. The final holdout must remain unopened for R004; do not fetch final funding data or run `--final` unless a new, separately preregistered study authorizes a different selection protocol.
- No live/paper exchange orders were sent. No short trade was tested in this R004 hypothesis.
- Final runner and selection regression test are captured in the run manifest. Ten synthetic tests pass.

## Results

- Read `decision.md` for the conclusion and `results.json` for all 96 aggregate train/validation cells. Decompress `symbol_results.json.gz` for all 576 per-symbol train/validation summaries.
- The ignored full output is `chart_predictor/data/strategy_lab/2026-11-16-r004-macd-zero-rsi50/screen.json` in the isolated research worktree; its SHA-256 is recorded in `manifest.json` and `decision.md`.
- The ignored public funding pages are stored alongside that output, in `funding/screen-through-2025-01-01/`. Do not copy those data files into Git.

## Important caveats

- Funding `markPrice` was blank for roughly 72–73% of records. For those events, the code uses the most recent prior minute candle open with a strict <60-second age guard. Cost-adjusted results are therefore approximate with respect to mark price.
- The historical sample has six current symbols and no point-in-time universe. It does not establish an 80% generalizable signal.
- The validation interval's matched buy-and-hold CAGR was exceptionally strong at 127.07%; the best strategy cell was +40.02%, so no selection gate passed.
- Main checkout `/Users/user/CODE/Coin_Trade` was dirty before this task. All research edits were isolated in this worktree; do not copy changes into the main checkout without a deliberate review.

## Next action

Continue the broader research goal with a distinct hypothesis and fresh preregistration. Do not alter R004's entry/exit settings based on its results and then call the same holdout independent. Preserve R004 as a completed negative validation screen and retain the final period as unopened for this run.
