# Gate 0 L2 pilot — preregistered plan

- Protocol: `docs/research/crypto_l2_resilience_research_gate_20261115.md`
- Purpose: public-data integrity and storage feasibility only; no signal, outcome label, account access, order, strategy performance test, or alpha claim.
- Scope: Binance USDⓈ-M public BTCUSDT and ETHUSDT `depth@500ms` plus `aggTrade`; capture 60 minutes after both local books synchronize.
- Hard limits: 512 MiB total output and 75 minutes wall-clock.
- Per-symbol coverage: at least 99% valid synchronized-book seconds across the 60-minute observation window.
- Recovery: every injected disconnect/gap must resnapshot and bridge both books within 30 seconds; a recovery not naturally observed in the live run is `null`/unobserved, not a pass.
- Persistence: append-only capture segment, exact record/byte counts and SHA-256; verify every record and manifest identity after capture.
- Fault tests: synchronization bridge, duplicates/reordering, sequence gaps, disconnect/resnapshot, restart, partial tail, retry supervision, output cap and no stale-book exposure.
- Decision: Gate 0 permits only consideration of a separately authorized prospective development capture. It does not authorize strategy evaluation, deployment, or live trading.

