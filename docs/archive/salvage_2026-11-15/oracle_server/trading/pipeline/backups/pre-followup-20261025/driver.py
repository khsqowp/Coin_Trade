#!/usr/bin/env python3
"""Host-side orchestrator (stdlib only, no secrets, no network). Python 3.9 compatible.

It launches one short-lived, locked-down container per step:
  agent   container: network + LLM keys (no KIS, no exchange keys), data read-only
  sandbox container: NO network, NO env secrets; executes LLM-written code
  offline container: Risk Engine gate
"""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_SH = os.path.join(HERE, "run.sh")
RUNS = os.path.join(HERE, "runs")


def sh(role, args, stdin=None, timeout=300):
    name = "tp-" + uuid.uuid4().hex[:8]
    env = dict(os.environ, TP_NAME=name)
    try:
        p = subprocess.run([RUN_SH, role] + args, input=(stdin or "").encode() if stdin is not None else None,
                           stdin=None if stdin is not None else subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 124, "", "timeout"
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def provider(model):
    return {"claude": "anthropic", "deepseek": "deepseek", "gpt": "openai"}[model.split("-")[0]]


def tool_result_msgs(model, results):
    if provider(model) == "anthropic":
        return [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": i, "content": t} for i, t in results]}]
    return [{"role": "tool", "tool_call_id": i, "content": t} for i, t in results]


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


TOOLS = None


def engineer_loop(model, run_id, hyp, symbol, max_steps=10):
    from importlib import util  # noqa
    run_dir = os.path.join(RUNS, run_id)
    work = os.path.join(run_dir, "work")
    cwork = "/app/runs/%s/work" % run_id
    os.makedirs(work, exist_ok=True)
    # tool defs + system prompt come from the agent container's source of truth
    rc, so, se = sh("agent", ["print-engineer-config"])
    cfg = json.loads(so)
    system, tools = cfg["system"], cfg["tools"]
    task = ("Implement hypothesis %s for %s (daily bars). Hypothesis JSON:\n%s\nUse the tools; end with the final JSON."
            % (hyp["id"], symbol, json.dumps(hyp, indent=1)))
    messages = [{"role": "user", "content": task}]
    trace, bt_calls, tool_fail, final, final_errors = [], 0, 0, None, 0
    for step in range(max_steps):
        req = {"model": model, "system": system, "messages": messages, "tools": tools, "max_tokens": 4000,
               "role": "engineer", "run_id": run_id, "purpose": "engineer-step-%d" % step, "final_schema": True}
        rc, so, se = sh("agent", ["llm-turn"], stdin=json.dumps(req), timeout=180)
        if rc != 0:
            log("engineer llm-turn failed rc=%s: %s" % (rc, se[-300:]))
            trace.append({"step": step, "error": se[-300:]})
            break
        resp = json.loads(so)
        trace.append({"step": step, "in_tok": resp["in_tok"], "out_tok": resp["out_tok"], "cost": resp["cost"],
                      "latency": resp["latency"], "tool_calls": [c["name"] for c in resp["tool_calls"]]})
        messages.append(resp["assistant_msg"])
        if resp["tool_calls"]:
            results = []
            for c in resp["tool_calls"]:
                n, a = c["name"], c["args"]
                if n == "write_file" and a.get("path") in ("strategy.py", "test_strategy.py") \
                        and isinstance(a.get("content"), str) and len(a["content"]) < 20000:
                    with open(os.path.join(work, a["path"]), "w") as f:
                        f.write(a["content"])
                    r = "written %s (%d bytes)" % (a["path"], len(a["content"]))
                elif n == "run_tests":
                    rc2, o, e = sh("sandbox", ["sandbox-pytest", "--dir", cwork], timeout=150)
                    r = o[-2500:] if rc2 == 0 else "tool failure: " + (e or o)[-400:]
                    tool_fail += rc2 != 0
                elif n == "run_backtest":
                    bt_calls += 1
                    if bt_calls > 2:
                        r = "refused: run_backtest limit (2) reached; finalize now."
                    else:
                        rc2, o, e = sh("sandbox", ["sandbox-backtest", "--dir", cwork, "--symbol", symbol, "--tf", "1d"], timeout=200)
                        r = json.dumps(json.loads(o), separators=(",", ":"))[:3500] if rc2 == 0 else "tool failure: " + (e or o)[-500:]
                        tool_fail += rc2 != 0
                else:
                    r = "invalid tool call"
                    tool_fail += 1
                results.append((c["id"], r))
                log("  tool %s -> %s" % (n, r[:90].replace("\n", " ")))
            messages += tool_result_msgs(model, results)
            continue
        if "final" in resp:
            final = resp["final"]
            break
        final_errors += 1
        if final_errors > 2:
            break
        messages.append({"role": "user", "content": "Final output invalid (%s). Return ONLY the final JSON object." % resp.get("final_error")})
    with open(os.path.join(run_dir, "03_engineer_trace.json"), "w") as f:
        json.dump({"model": model, "steps": trace, "tool_failures": tool_fail, "backtest_calls": bt_calls}, f, indent=1)
    return final, trace, tool_fail


def pipeline(a):
    if provider(a.auditor) == provider(a.researcher):
        sys.exit("Auditor must be a different provider than Researcher")
    run_id = a.run_id or time.strftime("run-%Y%m%d-%H%M%S")
    run_dir = os.path.join(RUNS, run_id)
    os.makedirs(run_dir, exist_ok=True)
    log("run %s | researcher=%s engineer=%s auditor=%s" % (run_id, a.researcher, a.engineer, a.auditor))
    rc, so, se = sh("agent", ["agent", "--role", "researcher", "--model", a.researcher, "--run-dir", "/app/runs/" + run_id], timeout=240)
    if rc != 0:
        sys.exit("researcher failed: " + se[-500:])
    log("researcher: " + so.replace("\n", " ")[:300])
    r = json.load(open(os.path.join(run_dir, "02_researcher.json")))["output"]
    hyp = r["hypotheses"][0]
    symbol = hyp["symbol"]
    final, trace, tf = engineer_loop(a.engineer, run_id, hyp, symbol)
    if not final:
        sys.exit("engineer produced no valid final output (see 03_engineer_trace.json)")
    json.dump(final, open(os.path.join(run_dir, "03_engineer_final.json"), "w"), indent=1)
    log("engineer final: tests_passed=%s backtest_run=%s" % (final["tests_passed"], final["backtest_run"]))
    cwork = "/app/runs/%s/work" % run_id
    # authoritative evidence, produced by the driver (not trusting the Engineer's claims)
    sh("sandbox", ["sandbox-pytest", "--dir", cwork], timeout=150)
    rc, so, se = sh("sandbox", ["sandbox-backtest", "--dir", cwork, "--symbol", symbol, "--tf", "1d"], timeout=200)
    if rc != 0:
        sys.exit("final backtest failed: " + (se or so)[-500:])
    rc, so, se = sh("agent", ["agent", "--role", "auditor", "--model", a.auditor, "--run-dir", "/app/runs/" + run_id], timeout=240)
    if rc != 0:
        sys.exit("auditor failed: " + se[-500:])
    log("auditor: " + so.replace("\n", " ")[:200])
    rc, so, se = sh("offline", ["risk-gate", "--run-dir", "/app/runs/" + run_id], timeout=60)
    log("risk gate: " + so.replace("\n", " ")[:600])
    rc, so, se = sh("agent", ["budget"])
    log("budget: " + so.replace("\n", " ")[:400])


def bench(a):
    for m in a.models.split(","):
        log("bench model %s" % m)
        rc, so, se = sh("agent", ["bench-run", "--model", m, "--reps", str(a.reps)], timeout=3000)
        print(so[-300:], se[-300:])
        if rc == 3:
            log("BUDGET STOP"); break
        rc, so, se = sh("sandbox", ["sandbox-codecheck", "--root", "/app/runs/bench/%s/codegen" % m,
                                    "--out", "/app/runs/bench/%s/codecheck.json" % m], timeout=900)
        log("codecheck rc=%s %s" % (rc, se[-200:]))
    rc, so, se = sh("offline", ["bench-finalize", "--models", a.models], timeout=120)
    print(so[-6000:], se[-500:])


def demo(a):
    """Push deliberately defective strategies through Auditor + Risk gate (no Researcher/Engineer LLM calls)."""
    sys.path.insert(0, os.path.join(HERE, "src"))
    from tp.fixtures import FIXTURES
    for name in a.fixtures.split(","):
        run_id = "demo-" + name
        run_dir = os.path.join(RUNS, run_id)
        os.makedirs(os.path.join(run_dir, "work"), exist_ok=True)
        hyp = {"id": "H1", "name": "demo " + name, "rationale": "synthetic demo", "symbol": "BTC/USDT", "timeframe": "1d",
               "entry_rule": "see code", "exit_rule": "see code", "parameters": {}, "expected_failure_modes": ["n/a"]}
        json.dump({"output": {"hypotheses": [hyp]}}, open(os.path.join(run_dir, "02_researcher.json"), "w"))
        json.dump({"hypothesis_id": "H1"}, open(os.path.join(run_dir, "03_engineer_final.json"), "w"))
        open(os.path.join(run_dir, "work", "strategy.py"), "w").write(FIXTURES[name]["code"])
        open(os.path.join(run_dir, "work", "test_strategy.py"), "w").write("# (demo) no unit tests supplied\n")
        cw = "/app/runs/" + run_id
        rc, so, se = sh("sandbox", ["sandbox-backtest", "--dir", cw + "/work", "--symbol", "BTC/USDT", "--tf", "1d"], timeout=200)
        if rc != 0:
            log("demo backtest failed %s" % se[-300:]); continue
        rc, so, se = sh("agent", ["agent", "--role", "auditor", "--model", a.auditor, "--run-dir", cw], timeout=240)
        rc, so, se = sh("offline", ["risk-gate", "--run-dir", cw], timeout=60)
        log("%s -> %s" % (name, so.replace("\n", " ")[:500]))


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="c", required=True)
    s = sp.add_parser("pipeline")
    s.add_argument("--researcher", default="deepseek-flash")
    s.add_argument("--engineer", default="claude-haiku-5-5")
    s.add_argument("--auditor", default="claude-haiku-5-5")
    s.add_argument("--run-id", default=None)
    s.set_defaults(f=pipeline)
    dm = sp.add_parser("demo")
    dm.add_argument("--fixtures", default="B1_shift_neg,B5_weekly_bfill")
    dm.add_argument("--auditor", default="claude-haiku-5-5")
    dm.set_defaults(f=demo)
    b = sp.add_parser("bench")
    b.add_argument("--models", default="deepseek-flash,claude-haiku-5-5,gpt-5.4-mini")
    b.add_argument("--reps", type=int, default=3)
    b.set_defaults(f=bench)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
