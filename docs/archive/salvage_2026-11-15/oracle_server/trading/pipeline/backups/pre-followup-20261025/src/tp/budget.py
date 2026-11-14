"""Shared LLM spend ledger (JSONL, file-locked). Hard stop at 80% of the budget."""
import fcntl
import json
import time

from .config import BUDGET_STOP_FRAC, BUDGET_TOTAL, RUNS

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


def check():
    t = total_cost()
    if t >= BUDGET_TOTAL * BUDGET_STOP_FRAC:
        raise BudgetExceeded("spent $%.4f >= 80%% of $%.2f budget" % (t, BUDGET_TOTAL))
    return t


def record(**entry):
    entry.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
