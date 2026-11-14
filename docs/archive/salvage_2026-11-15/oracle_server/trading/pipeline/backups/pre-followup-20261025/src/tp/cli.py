"""Single CLI entrypoint for every container role (python -m tp.cli <command>)."""
import argparse
import datetime as dt
import json
import signal
import subprocess
import sys
from pathlib import Path

from . import budget, config
from .config import RUNS, scrub


def out(obj):
    print(json.dumps(obj, indent=1, ensure_ascii=False, default=str))


def cmd_data_fetch(a):
    from . import store
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for sym in ("BTC/USDT", "ETH/USDT"):
        for tf, since in (("1d", dt.datetime(2018, 1, 1, tzinfo=dt.timezone.utc)),
                          ("1h", now - dt.timedelta(days=365))):
            df, ex = store.fetch_binance(sym, tf, since)
            m = store.save(df, "binance", ex, sym, tf, note="public OHLCV via ccxt, closed candles only")
            rows.append({"id": m[0], "rows": m[6], "first": m[7], "last": m[8], "sha256": m[9][:16]})
    out(rows)


def cmd_data_list(a):
    from . import store
    out([{k: v for k, v in m.items() if k != "versions"} for m in store.list_datasets()])


def cmd_data_verify(a):
    from . import store
    out(store.verify_all())


def cmd_data_get(a):
    from . import store
    df = store.get_ohlcv(a.symbol, a.tf, source=a.source, start=a.start, end=a.end)
    print(df.tail(a.tail).to_csv())


def cmd_summary(a):
    from . import summary
    out(summary.market_summary())


def cmd_kis_fetch(a):
    from . import kis, store
    res = {}
    for code in a.codes.split(","):
        try:
            df = kis.fetch_daily(code, days=a.days)
            m = store.save(df, "kis-paper", "KRX(via KIS paper API)", code, "1d", note="KIS mock-investing quotation API")
            res[code] = {"ok": True, "rows": m[6], "first": m[7], "last": m[8]}
        except Exception as e:
            res[code] = {"ok": False, "reason": scrub(e, 300)}
    kis.write_status(any(v["ok"] for v in res.values()), res)
    out(res)


def cmd_llm_turn(a):
    from . import agents, llm
    req = json.load(sys.stdin)
    r = llm.chat(req["model"], req.get("system"), req["messages"], tools=req.get("tools"),
                 max_tokens=req.get("max_tokens", 3000), role=req.get("role", "engineer"),
                 run_id=req.get("run_id", ""), purpose=req.get("purpose", "turn"))
    resp = {k: r[k] for k in ("text", "tool_calls", "assistant_msg", "in_tok", "out_tok", "cost", "latency", "stop")}
    if req.get("final_schema") and not r["tool_calls"]:
        from .schemas import ENGINEER_FINAL, validate
        try:
            resp["final"] = validate(agents.extract_json(r["text"]), ENGINEER_FINAL)
        except Exception as e:
            resp["final_error"] = str(e).splitlines()[0][:200]
    out(resp)


def cmd_agent(a):
    from . import agents
    d = Path(a.run_dir)
    if a.role == "researcher":
        from . import summary
        s = summary.market_summary()
        (d / "01_data_summary.json").write_text(json.dumps(s, indent=1))
        obj, meta = agents.researcher(a.model, s, d.name)
        (d / "02_researcher.json").write_text(json.dumps({"output": obj, "meta": meta, "model": a.model}, indent=1))
        out({"hypotheses": [h["id"] + ": " + h["name"] for h in obj["hypotheses"]], "meta": meta})
    else:
        hyp = json.loads((d / "02_researcher.json").read_text())["output"]
        hid = json.loads((d / "03_engineer_final.json").read_text())["hypothesis_id"]
        h = next(x for x in hyp["hypotheses"] if x["id"] == hid)
        w = d / "work"
        bt = json.loads((d / "03_backtest.json").read_text())
        tests = (d / "03_tests_output.txt").read_text() if (d / "03_tests_output.txt").exists() else ""
        obj, meta = agents.auditor(a.model, h, (w / "strategy.py").read_text(), (w / "test_strategy.py").read_text(),
                                   bt, tests, d.name)
        (d / "04_auditor.json").write_text(json.dumps({"output": obj, "meta": meta, "model": a.model}, indent=1))
        out({"verdict": obj["verdict"], "n_findings": len(obj["findings"]), "meta": meta})


def _timeout(sec):
    def h(*_):
        raise TimeoutError("sandbox timeout")
    signal.signal(signal.SIGALRM, h)
    signal.alarm(sec)


def cmd_sandbox_pytest(a):
    w = Path(a.dir)
    p = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "test_strategy.py"],
                       cwd=w, capture_output=True, text=True, timeout=90,
                       env={"PYTHONPATH": str(w), "PATH": "/usr/local/bin:/usr/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"})
    text = (p.stdout + p.stderr)[-3000:]
    (w.parent / "03_tests_output.txt").write_text(text)
    out({"returncode": p.returncode, "passed": p.returncode == 0, "output": text})


def cmd_sandbox_backtest(a):
    from . import bt, store
    _timeout(120)
    w = Path(a.dir)
    df = store.get_ohlcv(a.symbol, a.tf)
    fn = bt.load_signal_fn(w / "strategy.py")
    rep = bt.evaluate(df, fn, store.PERIODS_PER_YEAR[a.tf])
    rep["dataset"] = {k: v for k, v in store.meta_of(a.symbol, a.tf).items() if k in ("id", "source", "fetched_at", "sha256", "rows")}
    rep["symbol"] = a.symbol
    (w.parent / "03_backtest.json").write_text(json.dumps(rep, indent=1))
    out(rep)


def cmd_sandbox_codecheck(a):
    from . import codecheck, store
    df = store.get_ohlcv("BTC/USDT", "1d")
    res = {}
    for d in sorted(Path(a.root).iterdir()):
        _timeout(60)
        try:
            res[d.name] = codecheck.run_checks(d / "strategy.py", d.name.rsplit("_r", 1)[0], df)
        except TimeoutError:
            res[d.name] = {"error": "timeout"}
        finally:
            signal.alarm(0)
    Path(a.out).write_text(json.dumps(res, indent=1))
    out(res)


def cmd_risk_gate(a):
    from .risk import gate_strategy
    d = Path(a.run_dir)
    audit = json.loads((d / "04_auditor.json").read_text())["output"]
    bt = json.loads((d / "03_backtest.json").read_text())
    dec = gate_strategy(audit, bt, bt.get("symbol", ""))
    res = {"decision": "ALLOW_DRY_RUN" if dec.allowed else "BLOCK", "reasons": dec.reasons,
           "note": "Gate output only; nothing is deployed to Freqtrade by this pipeline."}
    (d / "05_risk_gate.json").write_text(json.dumps(res, indent=1))
    out(res)


def cmd_bench_run(a):
    from . import bench
    try:
        bench.run_model(a.model, reps=a.reps, tasks=a.tasks.split(","))
    except budget.BudgetExceeded as e:
        print("STOPPED:", e)
        sys.exit(3)
    print("done", a.model, "spent so far $%.4f" % budget.total_cost())


def cmd_bench_finalize(a):
    from . import bench
    models = a.models.split(",")
    cc = {}
    for m in models:
        p = bench.BENCH / m / "codecheck.json"
        cc[m] = json.loads(p.read_text()) if p.exists() else {}
    rows = bench.finalize(models, cc, budget.entries())
    (bench.BENCH / "scores.json").write_text(json.dumps(rows, indent=1, default=str))
    out(rows)


def cmd_print_engineer_config(a):
    from . import agents
    out({"system": agents.engineer_system(), "tools": agents.TOOLS})


def cmd_budget(a):
    es = budget.entries()
    by = {}
    for e in es:
        b = by.setdefault(e["model"], {"calls": 0, "failed": 0, "in_tok": 0, "out_tok": 0, "cost": 0.0})
        b["calls"] += 1
        b["failed"] += 0 if e["ok"] else 1
        b["in_tok"] += e["in_tok"]
        b["out_tok"] += e["out_tok"]
        b["cost"] = round(b["cost"] + e["cost"], 6)
    out({"total_usd": round(budget.total_cost(), 6), "budget_usd": config.BUDGET_TOTAL,
         "stop_at_usd": config.BUDGET_TOTAL * config.BUDGET_STOP_FRAC, "by_model": by})


def main():
    p = argparse.ArgumentParser(prog="tp")
    sp = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **args):
        s = sp.add_parser(name)
        for k, v in args.items():
            s.add_argument("--" + k.replace("_", "-"), dest=k, **v)
        s.set_defaults(fn=fn)
    add("data-fetch", cmd_data_fetch)
    add("data-list", cmd_data_list)
    add("data-verify", cmd_data_verify)
    add("data-get", cmd_data_get, symbol={"required": True}, tf={"default": "1d"}, source={"default": "binance"},
        start={"default": None}, end={"default": None}, tail={"type": int, "default": 10})
    add("summary", cmd_summary)
    add("kis-fetch", cmd_kis_fetch, codes={"default": "005930,000660"}, days={"type": int, "default": 400})
    add("llm-turn", cmd_llm_turn)
    add("agent", cmd_agent, role={"choices": ["researcher", "auditor"], "required": True},
        model={"required": True}, run_dir={"required": True})
    add("sandbox-pytest", cmd_sandbox_pytest, dir={"required": True})
    add("sandbox-backtest", cmd_sandbox_backtest, dir={"required": True}, symbol={"required": True}, tf={"default": "1d"})
    add("sandbox-codecheck", cmd_sandbox_codecheck, root={"required": True}, out={"required": True})
    add("risk-gate", cmd_risk_gate, run_dir={"required": True})
    add("bench-run", cmd_bench_run, model={"required": True}, reps={"type": int, "default": 3},
        tasks={"default": "dataqa,codegen,audit"})
    add("bench-finalize", cmd_bench_finalize, models={"required": True})
    add("budget", cmd_budget)
    add("print-engineer-config", cmd_print_engineer_config)
    a = p.parse_args()
    try:
        a.fn(a)
    except budget.BudgetExceeded as e:
        print("BUDGET STOP:", e, file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
