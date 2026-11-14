"""Shared LLM spend ledger (JSONL, file-locked). Hard stop at 80% of the budget."""
import fcntl
import json
import time

from .config import BUDGET_BASELINE, BUDGET_STOP_FRAC, BUDGET_TOTAL, RUNS

LEDGER = RUNS / "ledger.jsonl"


class BudgetExceeded(RuntimeError):
    pass


def entries():
    if not LEDGER.exists():
        return []
    out = []
    with open(LEDGER) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def total_cost():
    return sum(e.get("cost", 0.0) for e in entries())


def task_spent():
    """Spend since the baseline (the follow-up task's own consumption)."""
    return max(0.0, total_cost() - BUDGET_BASELINE)


def check():
    t = task_spent()
    if t >= BUDGET_TOTAL * BUDGET_STOP_FRAC:
        raise BudgetExceeded("task spend $%.4f >= 80%% of $%.2f allowance" % (t, BUDGET_TOTAL))
    return t


def record(**entry):
    entry.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
