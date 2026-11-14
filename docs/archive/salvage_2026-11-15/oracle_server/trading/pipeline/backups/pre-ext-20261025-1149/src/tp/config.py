"""Paths, budget constants and secret scrubbing. No secret value is ever logged."""
import os
import re
from pathlib import Path

ROOT = Path(os.environ.get("TP_ROOT", "/app"))
DATA = ROOT / "data"
RUNS = ROOT / "runs"
# Follow-up task allowance: $1.5 on top of what the ledger already held (BASELINE) when the task began.
# The auto-stop triggers at 80% of the *allowance* (i.e. $1.20 of new spend), not of the old $2 test budget.
BUDGET_BASELINE = float(os.environ.get("TP_BUDGET_BASELINE", "0.14975"))  # USD already spent before this task
BUDGET_TOTAL = float(os.environ.get("TP_BUDGET_TOTAL", "1.50"))           # USD allowance for this task
BUDGET_STOP_FRAC = 0.8                                                    # stop at 80%
MAX_CALLS_PER_PROCESS = int(os.environ.get("TP_MAX_CALLS", "150"))  # runaway guard

SECRET_ENV_NAMES = (
    "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "CHATGPT_API_KEY",
    "GEMINI_API_KEY", "HANTOO_TEST_KEY", "HANTOO_TEST_SECRET",
)
_PATTERNS = re.compile(r"(sk-[A-Za-z0-9_\-]{10,}|AIza[0-9A-Za-z_\-]{20,}|Bearer\s+[A-Za-z0-9._\-]{12,})")


def scrub(text, limit=400):
    """Remove any secret-looking string from text and truncate."""
    s = str(text)
    for name in SECRET_ENV_NAMES:
        v = os.environ.get(name)
        if v and len(v) >= 8:
            s = s.replace(v, "***")
    s = _PATTERNS.sub("***", s)
    return s[:limit]
