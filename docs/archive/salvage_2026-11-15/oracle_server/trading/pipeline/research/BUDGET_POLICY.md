# Agent budget incentive policy (pre-registered, owner decision of round 3)
Purpose: today everything is backtest / forward paper. The owner's intent: if the pipeline keeps producing risk-adjusted profit after its own costs, the regime agent's
budget may later be increased. This document, the regime agent's system prompt (`tp.regime.SYSTEM`) and the Hermes skill (`pipeline-qa`) carry the same rules.

## Cap and stages
Default daily cap for the scheduler agent: **0.30 USD** (owner-confirmed). Stages: **0.30 -> 0.60 -> 1.00 USD** (one stage at a time, at least 28 days apart). Round budget (separate): 3.00 USD, auto-stop at 80%.

## Conditions for a PROPOSAL (all must hold; computed by deterministic code `tp.budget_policy.decide`, no LLM)
Evaluated on forward paper candidate C6 (C3 scaled by the agent's risk_multiplier), registered in `runs/forward_registry.json`:
1. at least 28 forward days and at least 20 trades;
2. net return after deducting the scheduler's LLM spend since registration (converted with the 128.88 USDT paper base) is > 0;
3. annualised Sharpe after the same deduction >= 0.5;
4. maximum drawdown <= 15% and the candidate is not in a FAIL state (a large drawdown EXCLUDES any increase);
5. adjusted Sharpe > buy&hold BTC Sharpe (C0) - the measure is risk-adjusted performance versus simply holding, not raw profit;
6. adjusted Sharpe > the deterministic volatility-target rule C3v - the LLM must add value over a rule that costs nothing;
7. at least 28 days since the last cap change; a next stage must exist.
Why not raw profit: the survival-arena experiment showed that pressure can increase risk taking. Raising risk to make profit is NOT a reason for more budget; it is penalised
(risk_multiplier can only reduce risk, and any drawdown above 15% disqualifies).

## Who can change the cap
* The agent cannot: the cap is read from `config/daily_cap.txt` by `run.sh` on the HOST when the scheduler container is started and passed as an environment variable. `config/` is not mounted into
  the scheduler (or any LLM) container; tp-watch/offline mount it read-only.
* Deterministic code only PROPOSES: when the conditions hold, tp-watch (daily, after the summary) writes `runs/budget_proposal.json` and sends one Telegram text ("[예산 증액 제안 - 자동 적용 없음]"),
  repeated at most every 7 days. A proposal changes nothing.
* The owner applies it on the server: `./budget.sh approve 0.60` (re-computes the conditions; refuses if not met), `./budget.sh approve 0.60 --force` (explicit owner override, logged as forced),
  `./budget.sh reset` (back to 0.30), `./budget.sh status`. Each change is appended to `config/daily_cap.history` and restarts only `tp-sched`.
* Tests: `tests/test_round3_ops.py` (conditions met / each condition failing / drawdown / LLM cost erasing the edge / cooldown / last stage / no auto-apply / no code path writes the cap file).
Earliest possible proposal: 28 days after the candidates were registered (2026-10-25), i.e. not before 2026-11-22, and only if the numbers hold.
