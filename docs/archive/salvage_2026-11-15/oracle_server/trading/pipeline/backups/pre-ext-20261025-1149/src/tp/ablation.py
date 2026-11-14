"""Deterministic ablation (rule-removal) check. NO LLM, no network, no randomness.

Why: in run-main-002 the hypothesis listed two rules (close > SMA200 entry, ATR trailing exit) but the
generated signal series was bit-identical to plain "close > SMA200". The Engineer's unit tests and the LLM
Auditor both missed that the ATR rule never changed anything. This module catches that class of defect:
every declared rule is switched off, one at a time, and the resulting signals/trades/returns are compared
with the full strategy. A rule whose removal changes nothing is a DEAD rule.

Strategy contract (documented in the Engineer prompt):
    RULES = {"sma_entry": "close > SMA(200)", "atr_trail_exit": "close < highest_close - 3*ATR(14)"}
    def generate_signals(df, disabled=frozenset()): ...
`disabled` is a set of rule names that must behave as if the rule did not exist:
  entry/filter rule disabled -> its condition counts as always satisfied
  exit rule disabled         -> that exit condition never fires
With disabled=() the function is the full strategy.
"""
import hashlib
import inspect
import re

import numpy as np
import pandas as pd

from . import bt

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")

# A rule that changes fewer than this fraction of bars AND leaves trade count and return essentially
# unchanged is "weak" (warning, not blocking).
WEAK_DIFF_FRAC = 0.005
WEAK_RET_DELTA = 0.01          # |log change of terminal wealth|
DEAD_EPS = 1e-9


def file_sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def declared_rules(rules):
    """Normalise RULES (dict name->desc or list of names) to a list of names; raise ValueError if invalid."""
    if isinstance(rules, dict):
        names = list(rules.keys())
    elif isinstance(rules, (list, tuple)):
        names = list(rules)
    else:
        raise ValueError("RULES must be a dict or list of rule names")
    if not names:
        raise ValueError("RULES is empty")
    bad = [n for n in names if not isinstance(n, str) or not NAME_RE.match(n)]
    if bad:
        raise ValueError("invalid rule names: %s" % bad[:5])
    if len(set(names)) != len(names):
        raise ValueError("duplicate rule names")
    return names


def hypothesis_rule_names(hyp):
    """Rule names the Researcher declared in the hypothesis ('rules': [{name, kind, description}])."""
    rules = (hyp or {}).get("rules") or []
    return [r["name"] for r in rules if isinstance(r, dict) and r.get("name")]


def _supports_disabled(fn):
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    return "disabled" in sig.parameters or any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())


def _summ(df, sig, ppy, fee, slip):
    ret, h = bt.simulate(df, sig, fee, slip)
    st = bt._stats(ret, h, ppy)
    return {"trades": st["trades"], "total_return": st["total_return"], "sharpe": st["sharpe"],
            "mdd": st["mdd"], "exposure": st["exposure"]}


def compare(df, base, var, ppy, fee=bt.FEE, slip=bt.SLIP):
    """Metrics describing how much `var` differs from `base` (both aligned 0/1 signal Series)."""
    diff = (base.values != var.values)
    n_diff = int(diff.sum())
    b, v = _summ(df, base, ppy, fee, slip), _summ(df, var, ppy, fee, slip)
    out = {
        "diff_bars": n_diff,
        "diff_frac": round(n_diff / max(len(df), 1), 6),
        "signals_identical": n_diff == 0,
        "trades_full": b["trades"], "trades_without": v["trades"], "trades_delta": v["trades"] - b["trades"],
        "return_full": b["total_return"], "return_without": v["total_return"],
        "return_delta": round(v["total_return"] - b["total_return"], 6),
        # scale-free effect on terminal wealth (the absolute delta grows with the compounding that follows the change)
        "log_return_delta": round(float(np.log1p(v["total_return"]) - np.log1p(b["total_return"])), 6)
        if b["total_return"] > -1 and v["total_return"] > -1 else None,
        "sharpe_full": b["sharpe"], "sharpe_without": v["sharpe"],
        "mdd_full": b["mdd"], "mdd_without": v["mdd"],
    }
    return out


def classify(c):
    if c["signals_identical"]:
        return "dead"
    if (c["trades_delta"] == 0 and abs(c["return_delta"]) < DEAD_EPS
            and abs(c["sharpe_without"] - c["sharpe_full"]) < DEAD_EPS):
        return "dead"
    lrd = c["log_return_delta"] if c["log_return_delta"] is not None else c["return_delta"]
    if c["diff_frac"] < WEAK_DIFF_FRAC and c["trades_delta"] == 0 and abs(lrd) < WEAK_RET_DELTA:
        return "weak"
    return "effective"


def _clean(fn, df, disabled):
    out = fn(df.copy(), disabled=frozenset(disabled)) if disabled is not None else fn(df.copy())
    sig, bad = bt.clean_signals(out, df.index)
    return sig, bad


def run_ablation(df, signal_fn, rules, ppy, hyp_rule_names=None, fee=bt.FEE, slip=bt.SLIP, strategy_sha256=None):
    """Return a JSON-serialisable report. report['status'] is 'ok' only when every check could be performed.

    status: ok | no_rules | invalid_rules | unsupported | error | nondeterministic
    """
    rep = {"status": "ok", "rules": [], "dead_rules": [], "weak_rules": [], "effective_rules": [],
           "undeclared_hypothesis_rules": [], "extra_declared_rules": [], "n_bars": len(df),
           "thresholds": {"weak_diff_frac": WEAK_DIFF_FRAC, "weak_return_delta": WEAK_RET_DELTA},
           "strategy_sha256": strategy_sha256, "notes": []}
    if rules is None:
        rep["status"], rep["notes"] = "no_rules", ["strategy.py defines no RULES"]
        return rep
    try:
        names = declared_rules(rules)
    except ValueError as e:
        rep["status"], rep["notes"] = "invalid_rules", [str(e)]
        return rep
    rep["declared_rules"] = names
    if not _supports_disabled(signal_fn):
        rep["status"], rep["notes"] = "unsupported", ["generate_signals has no 'disabled' parameter"]
        return rep
    if hyp_rule_names:
        rep["undeclared_hypothesis_rules"] = [n for n in hyp_rule_names if n not in names]
        rep["extra_declared_rules"] = [n for n in names if n not in hyp_rule_names]
    try:
        base, _ = _clean(signal_fn, df, ())
        base2, _ = _clean(signal_fn, df, ())
        if not np.array_equal(base.values, base2.values):
            rep["status"], rep["notes"] = "nondeterministic", ["full strategy gives different signals on repeated calls"]
            return rep
        rep["base"] = _summ(df, base, ppy, fee, slip)
        for n in names:
            var, _ = _clean(signal_fn, df, (n,))
            c = compare(df, base, var, ppy, fee, slip)
            c["rule"] = n
            c["verdict"] = classify(c)
            rep["rules"].append(c)
    except Exception as e:  # strategy code raised while a rule was disabled -> evidence unusable
        rep["status"] = "error"
        rep["notes"].append("%s: %s" % (type(e).__name__, str(e)[:200]))
        return rep
    rep["dead_rules"] = [r["rule"] for r in rep["rules"] if r["verdict"] == "dead"]
    rep["weak_rules"] = [r["rule"] for r in rep["rules"] if r["verdict"] == "weak"]
    rep["effective_rules"] = [r["rule"] for r in rep["rules"] if r["verdict"] == "effective"]
    return rep


def summarize(rep):
    """One-line human summary (also used in notifications)."""
    if not rep or rep.get("status") != "ok":
        return "ablation unavailable (%s)" % (rep or {}).get("status", "missing")
    s = "rules=%d effective=%d" % (len(rep["rules"]), len(rep["effective_rules"]))
    if rep["dead_rules"]:
        s += " DEAD=%s" % ",".join(rep["dead_rules"])
    if rep["weak_rules"]:
        s += " weak=%s" % ",".join(rep["weak_rules"])
    if rep["undeclared_hypothesis_rules"]:
        s += " NOT_IMPLEMENTED=%s" % ",".join(rep["undeclared_hypothesis_rules"])
    return s
