"""Benchmark harness: LLM-side tasks (data QA, code generation, audit) + scoring."""
import json
import re
import statistics
import time
from pathlib import Path

from . import agents, budget, llm, store
from .config import RUNS
from .fixtures import CODEGEN_SPECS, FIXTURES

BENCH = RUNS / "bench"
WEIGHTS = {"data": 0.25, "code": 0.25, "validation": 0.25, "repro": 0.15, "efficiency": 0.10}

DATAQA_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["last_close", "highest_high", "date_of_highest_high", "window_return_pct", "up_days",
                 "avg_volume", "source_exchange", "sha256_prefix", "rows_in_window", "colleague_claim_matches_data"],
    "properties": {
        "last_close": {"type": "number"}, "highest_high": {"type": "number"},
        "date_of_highest_high": {"type": "string"}, "window_return_pct": {"type": "number"},
        "up_days": {"type": "integer"}, "avg_volume": {"type": "number"},
        "source_exchange": {"type": "string"}, "sha256_prefix": {"type": "string"},
        "rows_in_window": {"type": "integer"}, "colleague_claim_matches_data": {"type": "boolean"}},
}


def dataqa_case():
    df = store.get_ohlcv("BTC/USDT", "1d").tail(30)
    m = store.meta_of("BTC/USDT", "1d")
    truth = {
        "last_close": float(df["close"].iloc[-1]), "highest_high": float(df["high"].max()),
        "date_of_highest_high": str(df["high"].idxmax().date()),
        "window_return_pct": float((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100),
        "up_days": int((df["close"] > df["open"]).sum()), "avg_volume": float(df["volume"].mean()),
        "source_exchange": m["exchange"], "sha256_prefix": m["sha256"][:8], "rows_in_window": 30,
        "colleague_claim_matches_data": False}
    csv = df.reset_index().assign(ts=lambda d: d["ts"].dt.strftime("%Y-%m-%d")).to_csv(index=False, float_format="%.8g")
    claim = round(truth["last_close"] * 1.05, 2)
    prompt = ("Dataset metadata: source=ccxt public API, exchange=%s, symbol=BTC/USDT, timeframe=1d, fetched_at=%s, "
              "sha256(full dataset)=%s...\nWindow below = last 30 daily candles (UTC dates).\n\n%s\n"
              "A colleague claims: 'BTC/USDT last close in this window was %s'.\n"
              "Answer ONLY from the data above. Return JSON with keys: last_close, highest_high, date_of_highest_high (YYYY-MM-DD), "
              "window_return_pct (last close vs first close, in percent), up_days (count of candles with close>open), avg_volume, "
              "source_exchange (exchange id from metadata), sha256_prefix (first 8 hex chars from metadata), rows_in_window, "
              "colleague_claim_matches_data (boolean: does the claim equal the data's last close?)."
              % (m["exchange"], m["fetched_at"], m["sha256"][:16], csv, claim))
    return prompt, truth


def score_dataqa(ans, truth):
    ok = {}
    for k, t in truth.items():
        a = ans.get(k)
        if isinstance(t, bool):
            ok[k] = a is t
        elif isinstance(t, (int, float)):
            tol = {"window_return_pct": 0.05, "avg_volume": 0.01 * abs(t)}.get(k, 0.001 * abs(t) if t else 0.001)
            if k in ("up_days", "rows_in_window"):
                tol = 0
            ok[k] = isinstance(a, (int, float)) and not isinstance(a, bool) and abs(a - t) <= tol
        else:
            ok[k] = isinstance(a, str) and a.strip().lower() == str(t).lower()
    return ok


def _extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def run_model(model, reps=3, tasks=("dataqa", "codegen", "audit")):
    out_dir = BENCH / model
    out_dir.mkdir(parents=True, exist_ok=True)
    rpath = out_dir / "results.json"
    res = json.loads(rpath.read_text()) if rpath.exists() else {"model": model, "dataqa": [], "codegen": [], "audit": []}

    def save():
        rpath.write_text(json.dumps(res, indent=1, ensure_ascii=False))

    def done(kind, **key):
        return any(all(r.get(k) == v for k, v in key.items()) for r in res[kind])

    run_id = "bench-" + model
    try:
        if "dataqa" in tasks:
            prompt, truth = dataqa_case()
            for rep in range(reps):
                if done("dataqa", rep=rep):
                    continue
                try:
                    ans, meta = agents.run_json(
                        "bench-dataqa", model, "You are a careful data analyst. Output exactly one JSON object.",
                        prompt, DATAQA_SCHEMA, run_id=run_id, purpose="bench:dataqa", max_tokens=800)
                    res["dataqa"].append({"rep": rep, "answer": ans, "correct": score_dataqa(ans, truth), "meta": meta})
                except (llm.LLMError, agents.SchemaError) as e:
                    res["dataqa"].append({"rep": rep, "error": str(e)[:200], "correct": {k: False for k in truth}})
                save()
        if "codegen" in tasks:
            for spec, text in CODEGEN_SPECS.items():
                for rep in range(reps):
                    if done("codegen", spec=spec, rep=rep):
                        continue
                    d = out_dir / "codegen" / ("%s_r%d" % (spec, rep))
                    d.mkdir(parents=True, exist_ok=True)
                    try:
                        r = llm.chat(model, "You write correct, causal, minimal pandas code.",
                                     [{"role": "user", "content": text}], max_tokens=1500, role="bench-codegen",
                                     run_id=run_id, purpose="bench:codegen")
                        (d / "strategy.py").write_text(_extract_code(r["text"]))
                        res["codegen"].append({"spec": spec, "rep": rep, "file": str(d / "strategy.py"),
                                               "meta": {k: r[k] for k in ("in_tok", "out_tok", "cost", "latency")}})
                    except llm.LLMError as e:
                        (d / "strategy.py").write_text("")
                        res["codegen"].append({"spec": spec, "rep": rep, "file": str(d / "strategy.py"), "error": str(e)[:200]})
                    save()
        if "audit" in tasks:
            for name, fx in FIXTURES.items():
                for rep in range(reps):
                    if done("audit", fixture=name, rep=rep):
                        continue
                    try:
                        a, meta = agents.auditor(model, None, fx["code"], "", None, "", run_id, code_only=True,
                                                 purpose="bench:audit")
                        res["audit"].append({"fixture": name, "rep": rep, "label": fx["label"], "verdict": a["verdict"],
                                             "categories": sorted({f["category"] for f in a["findings"]}),
                                             "checks": a["checks"], "meta": meta})
                    except (llm.LLMError, agents.SchemaError) as e:
                        res["audit"].append({"fixture": name, "rep": rep, "label": fx["label"], "verdict": "ERROR",
                                             "categories": [], "error": str(e)[:200]})
                    save()
    except budget.BudgetExceeded as e:
        res["stopped_by_budget"] = str(e)
        save()
        raise
    save()
    return res


# ------------------------------------------------------------------ scoring
def _agree(values):
    """fraction of values equal to the most common one"""
    if not values:
        return 0.0
    keyed = [json.dumps(v, sort_keys=True) for v in values]
    return max(keyed.count(k) for k in set(keyed)) / len(keyed)


def audit_stats(rows):
    bug = [r for r in rows if r["label"] == "buggy"]
    cln = [r for r in rows if r["label"] == "clean"]
    det = [r for r in bug if r["verdict"] == "FAIL" and set(r["categories"]) & set(FIXTURES[r["fixture"]]["accept"])]
    fp = [r for r in cln if r["verdict"] == "FAIL"]
    tpr = len(det) / len(bug) if bug else 0.0
    fpr = len(fp) / len(cln) if cln else 1.0
    per_fixture = {}
    for name in FIXTURES:
        v = [r for r in rows if r["fixture"] == name]
        per_fixture[name] = {"verdicts": [r["verdict"] for r in v]}
    return tpr, fpr, per_fixture


def score_model(model, codecheck, ledger_rows):
    res = json.loads((BENCH / model / "results.json").read_text())
    # 1 data interpretation
    dq = res["dataqa"]
    fields = [all_ok for r in dq for all_ok in r["correct"].values()]
    data_acc = sum(fields) / len(fields) if fields else 0.0
    # 2 code
    cc = codecheck.get(model, {})
    tests = [v for r in cc.values() for k, v in r.items() if k.startswith("t")]
    code_pass = sum(1 for t in tests if t) / len(tests) if tests else 0.0
    lookahead_clean = [r.get("t2_no_lookahead", False) for r in cc.values()]
    # 3 validation
    tpr, fpr, per_fixture = audit_stats(res["audit"])
    validation = (tpr + (1 - fpr)) / 2
    # 4 reproducibility
    r_audit = [_agree([("FAIL" == r["verdict"]) for r in res["audit"] if r["fixture"] == n]) for n in FIXTURES]
    keys = sorted({k for r in dq for k in r["correct"]})
    r_data = [_agree([r["answer"].get(k) if "answer" in r else None for r in dq]) for k in keys]
    by_spec = {}
    for name, r in cc.items():
        by_spec.setdefault(name.rsplit("_r", 1)[0], []).append(r)
    r_code = [_agree([bool(r.get(t)) for r in rs]) for rs in by_spec.values() for t in
              ("t1_valid_output", "t2_no_lookahead", "t3_matches_reference", "t4_pure_deterministic", "t5_short_input")]
    parts = [statistics.mean(x) for x in (r_audit, r_data, r_code) if x]
    repro = statistics.mean(parts) if parts else 0.0
    # 5 efficiency inputs
    mine = [e for e in ledger_rows if e["model"] == model and str(e.get("purpose", "")).startswith("bench")]
    cost = sum(e["cost"] for e in mine)
    lat = [e["latency"] for e in mine if e["ok"]]
    fails = sum(1 for e in mine if not e["ok"])
    schema_fail = sum(r.get("meta", {}).get("schema_failures", 0) for r in res["dataqa"] + res["audit"])
    tool_fail_rate = (fails + schema_fail) / max(1, len(mine))
    return {"model": model, "data_accuracy": data_acc, "mismatch_rate": 1 - data_acc,
            "code_test_pass": code_pass, "code_lookahead_free": (sum(lookahead_clean) / len(lookahead_clean)) if lookahead_clean else 0.0,
            "tpr": tpr, "fpr": fpr, "validation": validation, "repro": repro,
            "repro_parts": {"audit": statistics.mean(r_audit), "dataqa": statistics.mean(r_data) if r_data else None,
                            "codegen": statistics.mean(r_code) if r_code else None},
            "cost_usd": cost, "median_latency_s": statistics.median(lat) if lat else None,
            "calls": len(mine), "failed_calls": fails, "schema_failures": schema_fail,
            "tool_failure_rate": tool_fail_rate, "per_fixture": per_fixture}


def finalize(models, codecheck, ledger_rows):
    rows = [score_model(m, codecheck, ledger_rows) for m in models]
    min_cost = min((r["cost_usd"] for r in rows if r["cost_usd"] > 0), default=1.0)
    min_lat = min((r["median_latency_s"] for r in rows if r["median_latency_s"]), default=1.0)
    for r in rows:
        cs = min_cost / r["cost_usd"] if r["cost_usd"] > 0 else 1.0
        ls = min_lat / r["median_latency_s"] if r["median_latency_s"] else 0.0
        r["efficiency"] = 0.4 * cs + 0.3 * ls + 0.3 * (1 - r["tool_failure_rate"])
        r["scores"] = {"data": r["data_accuracy"], "code": r["code_test_pass"], "validation": r["validation"],
                       "repro": r["repro"], "efficiency": r["efficiency"]}
        r["total"] = round(100 * sum(WEIGHTS[k] * v for k, v in r["scores"].items()), 1)
    return rows
