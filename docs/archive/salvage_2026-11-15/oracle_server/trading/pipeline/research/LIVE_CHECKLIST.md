# Live-trading switch checklist (HUMAN APPROVAL REQUIRED - nothing here is implemented or enabled)
Status: live trading is FORBIDDEN for this pipeline. The owner records the intent to use the whole account (~128.88 USDT) if live trading is ever approved. That is a stated intention, not an approval.
The owner's separate live logic outside this server is not connected to, read by, or modified by this pipeline.

Before the owner is even asked, ALL of these must be true and documented:
1. Evidence: at least one candidate with forward paper status SUCCESS for >= 90 days (not 28), cost-model and fee tier confirmed with the owner's real account, DSR (null variance) >= 0.95 over all variants tried, and
   strictly better risk-adjusted performance than buy&hold in forward data. At the end of round 3 no candidate reaches even the research bar (see RESULTS_round3.md).
2. Risk limits: the owner explicitly approves each limit for the live profile in writing (position share, daily loss, drawdown halt, trades per day). A single full-account position implies that a 50-90% drawdown
   is a realistic outcome in this research; the owner must accept that number knowingly. Limits are never relaxed by code or agent.
3. Exchange facts: real maker/taker tier and BNB use, actual minNotional/stepSize for each symbol, maintenance margin brackets, margin mode, leverage (default 1x, none above 1x without separate approval), liquidation price buffer.
4. Keys: a NEW exchange API key created by the owner, trading permission only, withdrawal DISABLED, IP-restricted to this server, stored outside the repo with 600 permission; never reused from other systems; revoked on any incident.
5. Technical: an order module written and independently reviewed (it does not exist today); idempotent client order ids; kill switch file; exchange-side stop orders; reconciliation of position and balance every cycle; rate-limit handling;
   dry-run (exchange testnet) period of at least 14 days with zero reconciliation errors.
6. Process: the owner gives an explicit written go decision for a stated amount and date; a first phase with a small fraction of the account; automatic halt rules (drawdown, daily loss, data staleness, watchdog alert); the owner is notified on every order.
7. Rollback: documented procedure to flatten positions and revoke keys; who is reachable when something breaks.
Nothing on this list may be started by an agent. The Hermes chat assistant and the regime agent refuse order requests and cannot change limits or budgets.
