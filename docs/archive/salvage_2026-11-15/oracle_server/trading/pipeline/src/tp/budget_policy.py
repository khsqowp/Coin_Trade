"""Scheduler budget INCENTIVE policy (pre-registered). Deterministic code only; no LLM, no agent can call anything here.

Rule: the agent's daily cap starts at $0.30. An INCREASE may be PROPOSED (a Telegram text to the owner) when a forward paper evaluation meets every
condition below. Proposing never changes the cap. The effective cap comes from the host-side file config/daily_cap.txt (not mounted into any agent container,
read by run.sh when the scheduler container is started) and changes only when the OWNER runs `./budget.sh approve <cap>` on the host.
The measure is cost-adjusted, risk-adjusted performance (LLM cost deducted, Sharpe, drawdown, comparison with plain holding and with the deterministic
volatility-target rule), never raw profit. A large drawdown excludes any increase: risk-seeking must not be rewarded."""
import datetime as dt
import json
import os

import numpy as np

from . import metrics
from .config import RUNS

STAGES = (0.30, 0.60, 1.00)
CAPITAL = 128.88                              # paper base used to convert LLM dollars into return
COOLDOWN_DAYS = 28
CONFIG_DIR = RUNS.parent / "config"
CAP_FILE = CONFIG_DIR / "daily_cap.txt"
HISTORY = CONFIG_DIR / "daily_cap.history"
PROPOSAL = RUNS / "budget_proposal.json"
C = dict(min_days=28, min_trades=20, min_net_return=0.0, min_sharpe=0.5, max_mdd=0.15)
AGENT_CANDIDATE, DETERMINISTIC_SUBSTITUTE, BENCHMARK = "C6_llm_rm_on_C3", "C3v_voltarget", "C0_buyhold_BTC"


def effective_cap():
    """Cap the scheduler runs with: env (set by run.sh at container start) > config file > first stage."""
    v = os.environ.get("TP_DAILY_CAP")
    if v:
        try:
            return float(v)
        except ValueError:
            pass
    try:
        return float(CAP_FILE.read_text().strip())
    except (OSError, ValueError):
        return STAGES[0]


def next_stage(cap):
    for s in STAGES:
        if s > cap + 1e-9:
            return s
    return None


def last_change(now):
    """UTC datetime of the last approved cap change (history file), else None."""
    try:
        last = [x for x in HISTORY.read_text().splitlines() if x.strip()][-1]
        return dt.datetime.strptime(last.split()[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except (OSError, ValueError, IndexError):
        return None


def adjusted(r, llm_cost, capital=CAPITAL):
    """Hourly returns with the LLM spend deducted uniformly over the evaluation window."""
    r = np.asarray(r, float)
    return r - (llm_cost / capital) / max(len(r), 1)


def decide(agent, subst, bench, llm_cost, cap_now, since_change_days=None, capital=CAPITAL, ppy=8760):
    """agent/subst/bench = dicts from forward.evaluate(..., with_r=True) (need days, trades, mdd, status, _r). Returns dict(eligible, checks, next_cap, ...)."""
    checks = []

    def chk(name, ok, value, rule):
        checks.append(dict(name=name, ok=bool(ok), value=value, rule=rule))
    nxt = next_stage(cap_now)
    chk("next_stage_exists", nxt is not None, cap_now, "cap below %.2f" % STAGES[-1])
    ok_data = bool(agent) and "_r" in agent and len(agent["_r"]) > 50
    chk("data_available", ok_data, None, "forward series present")
    if not ok_data:
        return dict(eligible=False, next_cap=nxt, cap_now=cap_now, checks=checks)
    ra = adjusted(agent["_r"], llm_cost, capital)
    sr_a = float(metrics.sharpe_annual(ra, ppy))
    net = float((1 + agent["total_return"]) - 1 - llm_cost / capital)
    chk("days", agent["days"] >= C["min_days"], agent["days"], ">= %d" % C["min_days"])
    chk("trades", agent["trades"] >= C["min_trades"], agent["trades"], ">= %d" % C["min_trades"])
    chk("net_return_after_llm_cost", net > C["min_net_return"], round(net, 4), "> 0 (LLM cost %.3f USD deducted)" % llm_cost)
    chk("sharpe_after_llm_cost", sr_a >= C["min_sharpe"], round(sr_a, 3), ">= %.1f" % C["min_sharpe"])
    chk("max_drawdown", agent["mdd"] <= C["max_mdd"] and not str(agent.get("status", "")).startswith("FAIL"), agent["mdd"], "<= %.2f and not FAIL" % C["max_mdd"])
    if bench and "_r" in bench:
        chk("beats_buy_and_hold", sr_a > float(bench["sharpe"]), round(float(bench["sharpe"]), 3), "adjusted Sharpe > buy&hold Sharpe")
    else:
        chk("beats_buy_and_hold", False, None, "benchmark missing")
    if subst and "_r" in subst:
        chk("beats_deterministic_substitute", sr_a > float(subst["sharpe"]), round(float(subst["sharpe"]), 3), "adjusted Sharpe > vol-target rule (the LLM must add value)")
    else:
        chk("beats_deterministic_substitute", False, None, "substitute missing")
    chk("cooldown", since_change_days is None or since_change_days >= COOLDOWN_DAYS, since_change_days, ">= %d days since last change" % COOLDOWN_DAYS)
    return dict(eligible=all(c["ok"] for c in checks), next_cap=nxt, cap_now=cap_now, sharpe_adj=round(sr_a, 3), net_return=round(net, 4), checks=checks)


def check(now=None):
    """Evaluate from live forward data (read-only)."""
    from . import budget, forward
    now = now or dt.datetime.now(dt.timezone.utc)
    reg = forward.registry(now)
    ev = {n: forward.evaluate(n, reg, with_r=True) for n in (AGENT_CANDIDATE, DETERMINISTIC_SUBSTITUTE, BENCHMARK)}
    t0 = reg[AGENT_CANDIDATE]
    llm_cost = sum(e.get("cost", 0.0) for e in budget.entries() if str(e.get("run_id", "")).startswith("sched-") and str(e.get("ts", "")) >= t0)
    lc = last_change(now)
    d = decide(ev[AGENT_CANDIDATE], ev[DETERMINISTIC_SUBSTITUTE], ev[BENCHMARK], llm_cost, effective_cap(),
               None if lc is None else (now - lc).total_seconds() / 86400)
    d["llm_cost_usd"] = round(llm_cost, 4)
    d["evaluated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return d


def proposal_text(d):
    lines = ["[예산 증액 제안 - 자동 적용 없음] 국면 에이전트 일일 상한 $%.2f -> $%.2f" % (d["cap_now"], d["next_cap"]),
             "근거(사전등록 조건 전부 충족): " + "; ".join("%s=%s" % (c["name"], c["value"]) for c in d["checks"] if c["name"] != "next_stage_exists"),
             "비용(LLM $%.3f) 차감 후 샤프 %.2f, 순수익 %.1f%%. 기준은 원수익이 아니라 비용 차감 후 위험조정 성과입니다." % (d["llm_cost_usd"], d["sharpe_adj"], 100 * d["net_return"]),
             "적용하려면 서버에서 직접: ./budget.sh approve %.2f  (에이전트는 상한을 올릴 수 없습니다)" % d["next_cap"]]
    return "\n".join(lines)


def propose(now=None, resend_days=7):
    """Write runs/budget_proposal.json and return the Telegram text if a NEW proposal should be sent, else None. NEVER changes the cap."""
    now = now or dt.datetime.now(dt.timezone.utc)
    d = check(now)
    if not d["eligible"]:
        return None, d
    try:
        old = json.loads(PROPOSAL.read_text())
        age = (now - dt.datetime.strptime(old["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)).days
        if old.get("to_cap") == d["next_cap"] and old.get("status") == "pending" and age < resend_days:
            return None, d
    except (OSError, ValueError, KeyError):
        pass
    PROPOSAL.write_text(json.dumps(dict(created_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"), from_cap=d["cap_now"], to_cap=d["next_cap"], status="pending", checks=d["checks"]), indent=1))
    return proposal_text(d), d


def summary_line(d):
    ok = sum(1 for c in d["checks"] if c["ok"])
    return "예산 정책: 상한 $%.2f, 증액 조건 %d/%d 충족%s" % (d["cap_now"], ok, len(d["checks"]), " -> 제안 대상" if d["eligible"] else "")
