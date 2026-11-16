# R012 handoff

- Parent artifacts and SHA-256 fingerprints are in `manifest.json`.
- Draft protocol: `plan.md`; arithmetic-only result: `results.json`; current decision: `decision.md`.
- No market data or label outcomes were read; no performance calculation or backtest ran.
- The 365-day horizon-window counts were computed only from timeframe durations and the frozen 20T horizon. They are upper bounds, not independent sample estimates.
- Four independent reviewers provided bounded critiques. One directly reviewed an earlier full draft; three reviewed detailed summaries. They found unresolved policy-vs-signal estimands, incomplete baseline definitions, no paired interpretation for different-anchor policies, and an unspecified/withdrawn confirmatory composite test. These limitations and findings are captured in `results.json` and `decision.md`.
- Known blockers before capture: unresolved baseline/estimand/inference design; no qualified multi-symbol prospective L2/trade history; no reconnect-recovery evidence; unresolved exact data rights/retention; no complete T/H-to-candidate execution replay; no frozen minimum train/calibration/validation counts; costs not calibrated; durable storage/capacity and final horizon are not established.
- Do not generate labels or run the 108-cell grid until the revised protocol is frozen and all operational/data gates pass.
