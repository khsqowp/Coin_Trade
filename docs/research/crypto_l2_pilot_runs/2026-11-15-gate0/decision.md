# Gate 0 decision

## Outcome: PASS for bounded data-integrity feasibility; HOLD for longer capture

Passed evidence:

- BTCUSDT and ETHUSDT each met the 60-minute target with 100% valid synchronized-book coverage and no observed invalid seconds inside the scored observation window.
- Capture and metadata totaled 230,850,555 bytes, below the 536,870,912-byte hard cap.
- Independent JSONL count, newline termination, byte-count, SHA-256, cap, and script-hash checks passed.
- The mocked end-to-end disconnect path forced one depth-stream failure, discarded stale book state, fetched new snapshots, bridged both books, and passed the <=30-second recovery gate.
- No credentials, account endpoints, signals, or orders were used.

Unobserved or limited:

- The 60-minute live run had zero reconnects, so natural live recovery is unobserved. It is not a live recovery pass.
- Aggregate-trade socket coverage and zero observed aggregate IDs jumps do not prove every exchange event was received.
- One hour's output rate is an observation, not a guaranteed future storage rate.
- Mocked restart/partial-file/fault tests and live connectivity do not establish 24-hour operational reliability.

Decision: the collector is eligible for a separately bounded prospective development-capture proposal, subject to storage allocation and a reviewed operating/rotation plan. No strategy test or performance claim is authorized by this Gate 0 result. The broader research objective remains open; no qualifying strategy has been demonstrated.

