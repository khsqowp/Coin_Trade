"""Shared LLM spend ledger (JSONL, file-locked). Hard stop at 80% of the budget."""
import datetime as dt
import fcntl
import json
import time
from zoneinfo import ZoneInfo

from .config import BUDGET_BASELINE, BUDGET_STOP_FRAC, BUDGET_TOTAL, DAILY_CAP, RUNS

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


class DailyCapExceeded(BudgetExceeded):
    pass


def day_start_utc(now=None):
    """Start of the current owner-facing day (KST midnight) as a UTC ledger timestamp string. Ledger timestamps stay UTC."""
    now = now or dt.datetime.now(dt.timezone.utc)
    k = now.astimezone(ZoneInfo("Asia/Seoul")).replace(hour=0, minute=0, second=0, microsecond=0)
    return k.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sched_spent_today(now=None):
    """Scheduler spend since KST midnight (= 15:00 UTC the previous day). The window start is earlier than the former UTC-day window,
    so the switch can only count MORE spend, never less."""
    start = day_start_utc(now)
    return sum(e.get("cost", 0.0) for e in entries() if str(e.get("run_id", "")).startswith("sched-") and str(e.get("ts", "")) >= start)


def check():
    if DAILY_CAP > 0 and sched_spent_today() >= DAILY_CAP:
        raise DailyCapExceeded("scheduler daily cap $%.2f reached" % DAILY_CAP)
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
