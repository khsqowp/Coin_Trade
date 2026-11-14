"""Strategy library: summarised ideas (NOT code) from public/owner sources, for the Researcher.

Context-explosion guard: the Researcher only sees `index_text()` (one short line per entry, hard cap) and may
ask for at most MAX_LOOKUPS full cards by id. Entries are data files (strategy_library/entries/*.json) written
from reading untrusted repositories; nothing in them is ever executed, and card text is length-capped and
stripped of control characters before it reaches a prompt.
"""
import json
import re

from .config import ROOT

LIB = ROOT / "strategy_library"
MAX_LOOKUPS = 2
INDEX_MAX_CHARS = 4500
CARD_MAX_CHARS = 2600
REQUIRED = ("id", "name", "family", "one_line", "source", "idea", "rules", "parameters", "evidence", "limitations",
            "pipeline_fit")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _clean(s):
    return _CTRL.sub("", str(s))


def load_all(lib=None):
    d = (lib or LIB) / "entries"
    out = []
    for p in sorted(d.glob("*.json")):
        e = json.loads(p.read_text())
        missing = [k for k in REQUIRED if k not in e]
        if missing:
            raise ValueError("%s missing %s" % (p.name, missing))
        if e["id"] != p.stem:
            raise ValueError("%s: id/filename mismatch" % p.name)
        for k in ("url", "license"):
            if not e["source"].get(k):
                raise ValueError("%s: source.%s required" % (p.name, k))
        out.append(e)
    return out


def index_entries(entries):
    return [{"id": e["id"], "family": e["family"], "fit": e["pipeline_fit"]["single_asset_daily_long_flat"],
             "status": e["status_in_source"].split(" (")[0].split(";")[0][:40], "one_line": e["one_line"][:150]}
            for e in entries]


def build_index(lib=None):
    lib = lib or LIB
    idx = index_entries(load_all(lib))
    (lib / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    return idx


def index_text(lib=None, max_chars=INDEX_MAX_CHARS):
    """Compact index for the prompt: id | family | fit | status | one_line."""
    idx = index_entries(load_all(lib))
    lines = ["%s | %s | fit=%s | %s | %s" % (i["id"], i["family"], i["fit"], i["status"], i["one_line"]) for i in idx]
    text = _clean("\n".join(lines))
    return text if len(text) <= max_chars else text[:max_chars - 20] + "\n...(truncated)"


def card(entry_id, lib=None):
    """Compact full card for one entry (text, capped)."""
    ids = {e["id"]: e for e in load_all(lib)}
    if entry_id not in ids:
        return None
    e = ids[entry_id]
    s = e["source"]
    rules = "; ".join("%s[%s]: %s" % (r["name"], r["kind"], r["description"]) for r in e["rules"]) or "(none listed)"
    t = ("ID: %s\nNAME: %s\nSOURCE: %s (license: %s)\nMARKET/TF/DIRECTION: %s | %s | %s\nIDEA: %s\nRULES: %s\n"
         "PARAMETERS: %s\nEVIDENCE: %s\nLIMITATIONS: %s\nPIPELINE FIT: %s - %s") % (
        e["id"], e["name"], s["url"], s["license"], ", ".join(e["markets"]), e["timeframe"], e["direction"], e["idea"],
        rules, json.dumps(e["parameters"], ensure_ascii=False), e["evidence"], " | ".join(e["limitations"]),
        e["pipeline_fit"]["single_asset_daily_long_flat"], e["pipeline_fit"]["notes"])
    t = _clean(t)
    return t if len(t) <= CARD_MAX_CHARS else t[:CARD_MAX_CHARS - 15] + "...(truncated)"


def valid_ids(lib=None):
    return {e["id"] for e in load_all(lib)}
