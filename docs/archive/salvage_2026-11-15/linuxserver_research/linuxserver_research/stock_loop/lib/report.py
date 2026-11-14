"""Report helpers: markdown tables, LEDGER rows, JSON dumps."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

LEDGER = Path(__file__).resolve().parent.parent / "LEDGER.md"
LEDGER_HEADER = "| id | market | idea | stage | dev net mean/trade, t, Sharpe | holdout | verdict | next |\n|---|---|---|---|---|---|---|---|\n"


def pct(x, d=3):
    return "nan" if x is None or not np.isfinite(x) else f"{100 * x:.{d}f}%"


def md_table(rows, cols):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out) + "\n"


def ledger_row(id, market, idea, stage, mean, t, sharpe, holdout="locked", verdict="", nxt=""):
    sh = "nan" if sharpe is None or not np.isfinite(sharpe) else f"{sharpe:.2f}"
    tt = "nan" if t is None or not np.isfinite(t) else f"{t:.2f}"
    return f"| {id} | {market} | {idea} | {stage} | {pct(mean)}, t={tt}, Sh={sh} | {holdout} | {verdict} | {nxt} |\n"


def append_ledger(row: str, path: Path = LEDGER):
    path = Path(path)
    if not path.exists() or not path.read_text().strip():
        path.write_text("# LEDGER\n\n" + LEDGER_HEADER)
    with open(path, "a") as f:
        f.write(row)


def dump_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    def conv(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)
    Path(path).write_text(json.dumps(obj, indent=1, default=conv, ensure_ascii=False))
