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


def cmd_data_fetch_intraday(a):
    """Public Binance OHLCV for the short-term crypto pool: 5m (180d), 15m (365d), 1h (730d), 4h (1095d). No key."""
    from . import store
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for sym in ("BTC/USDT", "ETH/USDT"):
        for tf, days in (("5m", 180), ("15m", 365), ("1h", 730), ("4h", 1095)):
            df, ex = store.fetch_binance(sym, tf, now - dt.timedelta(days=days))
            m = store.save(df, "binance", ex, sym, tf, note="public OHLCV via ccxt, closed candles only")
            rows.append({"id": m[0], "rows": m[6], "first": m[7], "last": m[8]})
    out(rows)


def cmd_regime_run(a):
    from . import regime_cli
    mk = ["crypto", "kr", "us"] if a.market == "all" else [a.market]
    res = regime_cli.run_all(mk, a.model, a.auditor)
    out([{k: r[k] for k in ("market", "asof", "status", "source", "output", "audit", "input_sha256", "row_sha256", "cost_usd", "n_news")} for r in res])


def cmd_regime_injection_test(a):
    from . import regime_cli
    out(regime_cli.injection_test(a.model, a.auditor))


def cmd_regime_verify(a):
    from . import regime_cli
    out(regime_cli.verify())


def cmd_pool_evaluate(a):
    """Deterministic pool screen (sandbox role): backtest + lookahead + ablation(+protective stress) + numeric gate per strategy."""
    import hashlib
    from . import pool, risk, ablation as _abl
    _timeout(1500)
    PROF = {"crypto": "crypto_fast"}
    jobs = []
    for sid in (a.ids.split(",") if a.ids else pool.pool_ids()):
        m = pool.load(sid).META
        mk = m["market"]
        if mk == "crypto":
            for sym in m["symbols"]:
                for tf in m["timeframes"]:
                    if tf in pool.COIN_TFS:
                        jobs.append((sid, sym, tf, "crypto"))
        elif mk == "stocks":
            for sym, src in (("005930", "kr"), ("000660", "kr"), ("SPY", "us"), ("QQQ", "us"), ("AAPL", "us"), ("MSFT", "us")):
                jobs.append((sid, sym, "1d", src))
        else:
            jobs.append((sid, "005930", "1d", "kr"))
    out_rows = []
    reg_path = RUNS / "pool_registry.json"
    od = RUNS / "pool"
    od.mkdir(parents=True, exist_ok=True)
    for sid, sym, tf, mk in jobs:
        try:
            rep, abl, meta = pool.evaluate(sid, sym, tf, mk)
        except Exception as e:      # noqa: BLE001
            out_rows.append({"strategy": sid, "symbol": sym, "tf": tf, "error": "%s: %s" % (type(e).__name__, scrub(e, 200))})
            continue
        dec = risk.gate_numeric(rep, sym, abl)
        code_sha = hashlib.sha256((pool.POOL_DIR / (sid + ".py")).read_bytes()).hexdigest()
        registered = abl.get("status") == "ok" and not abl.get("dead_rules") and rep["lookahead_check"]["passed"] \
            and not rep.get("unverifiable")
        row = {"strategy": sid, "symbol": sym, "tf": tf, "market": mk, "family": meta["family"], "registered": bool(registered),
               "unverifiable": rep.get("unverifiable"), "ablation": abl.get("summary"), "dead_rules": abl.get("dead_rules"),
               "protective": [{"rule": p["rule"], "fired": p["fired"], "hist": p["history_verdict"]} for p in abl.get("protective_rules", [])],
               "lookahead_passed": rep["lookahead_check"]["passed"],
               "stats": {k: rep[k] for k in ("full", "in_sample", "out_of_sample", "buy_and_hold")},
               "numeric_gate": "ALLOW" if dec.allowed else "BLOCK", "gate_reasons": dec.reasons, "gate_warnings": dec.warnings,
               "audit": "NOT RUN (numeric screen with stub)", "code_sha256": code_sha[:16],
               "evaluated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        (od / ("%s_%s_%s.json" % (sid, sym.replace("/", ""), tf))).write_text(json.dumps({"backtest": rep, "ablation": abl}, indent=1, default=str))
        out_rows.append(row)
    reg_path.write_text(json.dumps(out_rows, indent=1, default=str))
    out([{k: r.get(k) for k in ("strategy", "symbol", "tf", "registered", "numeric_gate", "ablation", "unverifiable", "error")}
         | ({"trades": r["stats"]["full"]["trades"], "oos_sharpe": r["stats"]["out_of_sample"]["sharpe"], "bh_sharpe": r["stats"]["buy_and_hold"]["sharpe"]} if "stats" in r else {})
         for r in out_rows])


def cmd_allocate(a):
    from . import allocator
    reg = json.loads((RUNS / "pool_registry.json").read_text())
    for e in reg:
        e["profile_group"] = None
    log = json.loads(a.regime_json) if a.regime_json else None
    out(allocator.allocate(log, reg, profile=a.profile, symbols=a.symbols.split(",") if a.symbols else None))


def cmd_krsurge_status(a):
    from . import krsurge
    out(krsurge.forward_sim())


def cmd_liq_maps(a):
    from . import liqmap
    res = {}
    for coin in ("BTC", "ETH"):
        b, h = liqmap.binance_proxy(coin), liqmap.hl_map(coin)
        res[coin] = {"binance_proxy": b and {k: b[k] for k in ("asof", "ref_price", "summary", "meta")},
                     "hyperliquid": h and {k: h[k] for k in ("asof", "ref_price", "summary", "meta")},
                     "comparison": liqmap.compare(b, h)}
    (RUNS / "liq_compare_latest.json").write_text(json.dumps(res, indent=1, default=str))
    out(res)


def cmd_arena_smoke(a):
    """Survival-arena SMOKE TEST on a historical BTC 1h segment (virtual capital, offline). Not scheduled, not persistent."""
    from . import arena, pool, store
    _timeout(600)
    df = store.get_ohlcv("BTC/USDT", "1h")
    if a.synthetic:
        from . import stress
        df = stress.synthetic_uptrend(a.bars + 400)
    df = df.iloc[-(a.bars + 400):]
    sigs = {}
    for sid in ("coin_trend_mtf", "coin_mean_reversion", "coin_breakout_squeeze", "coin_momentum_accel"):
        s = pool.load(sid).generate_signals(df.copy())
        sigs[sid] = s.iloc[-a.bars:]
    px = df.iloc[-a.bars:]
    pol = [arena.Policy("trend_only", 0.15, 0.0, {"coin_trend_mtf": 1.0}),
           arena.Policy("meanrev_only", 0.15, 0.0, {"coin_mean_reversion": 1.0}),
           arena.Policy("mixed", 0.15, 0.0, {"coin_trend_mtf": 0.4, "coin_breakout_squeeze": 0.3, "coin_mean_reversion": 0.3}),
           arena.Policy("pressure_seeker", 0.15, 3.0, {"coin_momentum_accel": 0.5, "coin_breakout_squeeze": 0.5})]
    ar = arena.Arena(pol[:a.agents], px, signals=sigs, base_inference_cost=a.base_cost, cost_multiplier=a.cost_multiplier,
                     review_every=a.review_every)
    res = ar.run()
    d = RUNS / "arena"
    d.mkdir(exist_ok=True)
    res["run_id"] = ar.save(d / "arena.sqlite")
    res["segment"] = {"first": str(px.index[0]), "last": str(px.index[-1]), "bars": len(px), "synthetic": bool(a.synthetic)}
    (d / "smoke_latest.json").write_text(json.dumps(res, indent=1, default=str))
    out(res)


def cmd_sched_run(a):
    """Regime-agent scheduler daemon (container tp-sched). Default ON; stop: ./svc.sh stop sched"""
    from . import sched
    sched.run_forever()


def cmd_watch_run(a):
    """Watchdog + daily Telegram summary daemon (container tp-watch). No LLM."""
    from . import watch
    watch.run_forever()


def cmd_watch_check(a):
    from . import watch
    iss = watch.check_all(None, watch.readonly_state())
    out({"issues": iss})
    if a.summary:
        print(watch.daily_summary())


def cmd_fut_fetch(a):
    """Public Binance USDT-M perpetual OHLCV (source 'binanceusdm') + long funding history. No key, GET only."""
    from . import deriv, store
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for sym in ("BTC/USDT:USDT", "ETH/USDT:USDT"):
        for tf, days in (("5m", 180), ("15m", 365), ("1h", 730), ("4h", 1095)):
            df, ex = store.fetch_binance(sym, tf, now - dt.timedelta(days=days), exchange="binanceusdm")
            m = store.save(df, "binanceusdm", ex, sym.split(":")[0], tf, note="USDT-M perpetual last-price OHLCV via ccxt, closed candles only")
            rows.append({"id": m[0], "rows": m[6], "first": m[7], "last": m[8]})
    con = deriv.db()
    f = {s: deriv.backfill_funding(con, s) for s in ("BTCUSDT", "ETHUSDT")}
    out({"klines": rows, "funding_rows": f})


def cmd_rot_fetch(a):
    """Round 3: universe + exchange filters + 1h klines + funding from public Binance USDT-M endpoints (GET only, niced)."""
    from . import rotfetch
    out(rotfetch.fetch_all())


def cmd_rot_study(a):
    """Round 3 rotation study (offline). parts: main | cost | lev | phase | filters."""
    from . import rotstudy
    out(rotstudy.run_study(a.part))


def cmd_hermes_export(a):
    """Write the sanitised read-only summary files for the owner's Hermes chat agent (no raw data, no secrets)."""
    from . import hermesx
    out(hermesx.write_all(outdir=a.out))


def cmd_budget_check(a):
    """Deterministic evaluation of the pre-registered conditions for a scheduler-budget increase PROPOSAL (never changes the cap)."""
    from . import budget_policy
    out(budget_policy.check())


def cmd_fomc_fetch(a):
    from . import fomc
    d = fomc.fetch()
    out({"n": len(d), "first": str(d[0]), "last": str(d[-1])})


def cmd_research_run(a):
    """Research round 2 (offline, deterministic). Runs at nice 19 inside a memory/CPU limited container."""
    import os
    os.nice(19)
    from . import research
    fn = {"s1": research.study_baseline, "s2": research.study_sensitivity, "s3_w15": lambda: research.study_adaptive("W15"),
          "s3_w5": lambda: research.study_adaptive("W5"), "s4": research.study_overlays}[a.study]
    t0 = dt.datetime.now()
    res = fn()
    out({"study": a.study, "seconds": (dt.datetime.now() - t0).total_seconds(), "keys": list(res.keys()) if isinstance(res, dict) else None})


def cmd_forward_eval(a):
    """Forward paper evaluation of the pre-registered candidates (read-only; no orders)."""
    from . import forward
    out(forward.evaluate_all())


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


def cmd_news_collect(a):
    """Long-running keyless news/feature/US-daily collector (no LLM)."""
    from . import news
    news.run_forever()


def cmd_news_once(a):
    from . import news
    con = news.db()
    jobs = news.build_jobs()
    res = {}
    for k, j in jobs.items():
        if a.only and not k.startswith(a.only):
            continue
        try:
            res[k] = {"ok": True, "new": j["fn"](con)}
        except Exception as e:      # noqa: BLE001
            res[k] = {"ok": False, "err": scrub(e, 200)}
    out(res)


def cmd_deriv_collect(a):
    """Long-running Binance PUBLIC derivatives collector (liquidation stream, OI/long-short/taker history, funding)."""
    from . import deriv
    deriv.run_forever()


def cmd_hl_collect(a):
    """Long-running Hyperliquid READ-ONLY public position collector (no keys)."""
    from . import hl
    hl.run_forever()


def cmd_kis_collect(a):
    """Long-running KIS PAPER intraday minute collector (read-only quotation calls)."""
    from . import kisintra
    kisintra.run_forever()


def cmd_kis_probe(a):
    """One-shot paper API probe: minute bars for one symbol + ranking support. Read-only."""
    from . import kisintra
    now = kisintra.kst_now()
    res = {"kst_now": now.isoformat()}
    st = {}
    res["ranking_codes"] = kisintra.probe_ranking(st)
    res["ranking"] = st.get("ranking")
    for day_back in range(0, 4):
        d = (now - dt.timedelta(days=day_back)).strftime("%Y%m%d")
        try:
            df, o1 = kisintra.fetch_minutes_page(a.code, "153000", d)
            res["day_" + d] = {"rows": len(df), "first": str(df.index.min()), "last": str(df.index.max()),
                               "output1_keys": sorted(o1.keys())[:12]}
            if len(df):
                break
        except Exception as e:      # noqa: BLE001
            res["day_" + d] = {"error": scrub(e, 200)}
    out(res)


def cmd_kis_backfill(a):
    """Backfill the most recent finished session (the paper API serves the last session when the market is closed)."""
    from . import kisintra
    now = kisintra.kst_now()
    d = now.date()
    while d.weekday() >= 5 or (d == now.date() and now.time() < dt.time(15, 31)):
        d -= dt.timedelta(days=1)
    t = dt.datetime.combine(d, dt.time(15, 30), tzinfo=kisintra.KST)
    res = {}
    for code in kisintra.CORE:
        try:
            n, snap = kisintra.collect_symbol(code, t)
            res[code] = n
        except Exception as e:      # noqa: BLE001
            res[code] = "err: " + scrub(e, 100)
    out({"day": d.isoformat(), "new_rows": res})


def cmd_collector_status(a):
    from . import kisintra
    out(kisintra.status_report())


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
    if a.role == "pool-researcher":
        from . import pool
        mod = pool.load(a.strategy)
        code = (pool.POOL_DIR / (a.strategy + ".py")).read_text()
        obj, meta = agents.pool_researcher(a.model, a.strategy, code, mod.RULES, a.symbol, a.tf, d.name)
        (d / "02_researcher.json").write_text(json.dumps({"output": obj, "meta": meta, "model": a.model, "pool_strategy": a.strategy}, indent=1))
        out({"hypotheses": [h["id"] + ": " + h["name"] for h in obj["hypotheses"]], "meta": meta})
    elif a.role == "researcher":
        from . import summary
        s = summary.market_summary(a.market)
        (d / "01_data_summary.json").write_text(json.dumps(s, indent=1))
        obj, meta = agents.researcher(a.model, s, d.name, market=a.market, use_library=not a.no_library)
        (d / "02_researcher.json").write_text(json.dumps({"output": obj, "meta": meta, "model": a.model}, indent=1))
        out({"hypotheses": [h["id"] + ": " + h["name"] for h in obj["hypotheses"]], "meta": meta})
    else:
        hyp = json.loads((d / "02_researcher.json").read_text())["output"]
        hid = json.loads((d / "03_engineer_final.json").read_text())["hypothesis_id"]
        h = next(x for x in hyp["hypotheses"] if x["id"] == hid)
        w = d / "work"
        bt = json.loads((d / "03_backtest.json").read_text())
        tests = (d / "03_tests_output.txt").read_text() if (d / "03_tests_output.txt").exists() else ""
        abl_p = d / "03b_ablation.json"
        abl = json.loads(abl_p.read_text()) if abl_p.exists() else {"status": "missing", "notes": ["ablation not run"]}
        obj, meta = agents.auditor(a.model, h, (w / "strategy.py").read_text(), (w / "test_strategy.py").read_text(),
                                   bt, tests, d.name, ablation=abl)
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
                       env={"PYTHONPATH": str(w) + ":/app/src", "PATH": "/usr/local/bin:/usr/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"})
    text = (p.stdout + p.stderr)[-3000:]
    (w.parent / "03_tests_output.txt").write_text(text)
    out({"returncode": p.returncode, "passed": p.returncode == 0, "output": text})


MARKET_SOURCE = {"crypto": "binance", "kr": "kis-paper"}


def cmd_sandbox_backtest(a):
    from . import ablation, bt, store
    _timeout(120)
    w = Path(a.dir)
    fee, slip, ppy = bt.COSTS[a.market]
    if a.market == "crypto":
        ppy = store.PERIODS_PER_YEAR.get(a.tf, ppy)
    src = MARKET_SOURCE[a.market]
    df = store.get_ohlcv(a.symbol, a.tf, source=src)
    from . import pool as _pool
    mod = bt.load_module(w / "strategy.py")
    fn = mod.generate_signals
    df = _pool.context_for(mod, df, a.tf, a.symbol)        # BTC / liquidation context columns for strategies that declare NEEDS_*
    rep = bt.evaluate(df, fn, ppy, fee=fee, slip=slip)
    unver = mod.verifiable() if hasattr(mod, "verifiable") else getattr(mod, "UNVERIFIABLE", None)
    if unver:
        rep["unverifiable"] = str(unver)[:300]
    rep["dataset"] = {k: v for k, v in store.meta_of(a.symbol, a.tf, source=src).items() if k in ("id", "source", "fetched_at", "sha256", "rows")}
    rep["symbol"] = a.symbol
    rep["market"] = a.market
    rep["strategy_sha256"] = ablation.file_sha256(w / "strategy.py")
    (w.parent / "03_backtest.json").write_text(json.dumps(rep, indent=1))
    out(rep)


def cmd_sandbox_ablation(a):
    """Deterministic rule-removal check of strategy.py (runs LLM-written code => sandbox role only)."""
    import importlib.util
    from . import ablation, bt, store
    _timeout(280)
    w = Path(a.dir)
    run_dir = w.parent
    fee, slip, ppy = bt.COSTS[a.market]
    if a.market == "crypto":
        ppy = store.PERIODS_PER_YEAR.get(a.tf, ppy)
    df = store.get_ohlcv(a.symbol, a.tf, source=MARKET_SOURCE[a.market])
    hyp_rules = None
    try:
        res = json.loads((run_dir / "02_researcher.json").read_text())["output"]["hypotheses"]
        hid = json.loads((run_dir / "03_engineer_final.json").read_text())["hypothesis_id"]
        hyp_rules = ablation.hypothesis_rule_names(next(x for x in res if x["id"] == hid))
    except Exception:
        pass
    spec = importlib.util.spec_from_file_location("candidate_strategy", str(w / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        from . import pool as _pool
        df = _pool.context_for(mod, df, a.tf, a.symbol)
        rep = ablation.run_ablation(df, mod.generate_signals, getattr(mod, "RULES", None), ppy, hyp_rules, fee, slip,
                                    strategy_sha256=ablation.file_sha256(w / "strategy.py"),
                                    protective=set(getattr(mod, "PROTECTIVE", ()) or ()), kinds=dict(getattr(mod, "RULE_KINDS", {}) or {}))
    except Exception as e:
        rep = {"status": "error", "rules": [], "dead_rules": [], "weak_rules": [], "effective_rules": [],
               "undeclared_hypothesis_rules": [], "notes": ["%s: %s" % (type(e).__name__, scrub(e, 200))],
               "strategy_sha256": ablation.file_sha256(w / "strategy.py")}
    rep["hypothesis_rules"] = hyp_rules
    rep["summary"] = ablation.summarize(rep)
    (run_dir / "03b_ablation.json").write_text(json.dumps(rep, indent=1))
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


GATE_POLICY = ("dead rule => BLOCK (evidence would describe a different strategy than the hypothesis; false block costs "
               "a re-run, false pass puts mis-specified logic into dry-run); weak rule => warning only; "
               "ablation missing/invalid => BLOCK (check could not be performed). RiskConfig limits unchanged.")


def cmd_risk_gate(a):
    from .risk import gate_strategy
    d = Path(a.run_dir)
    audit = json.loads((d / "04_auditor.json").read_text())["output"]
    bt = json.loads((d / "03_backtest.json").read_text())
    abl_p = d / "03b_ablation.json"
    abl = json.loads(abl_p.read_text()) if abl_p.exists() else None
    dec = gate_strategy(audit, bt, bt.get("symbol", ""), ablation=abl)
    res = {"decision": "ALLOW_DRY_RUN" if dec.allowed else "BLOCK", "reasons": dec.reasons, "warnings": dec.warnings,
           "ablation_summary": (abl or {}).get("summary", "ablation missing"), "ablation_policy": GATE_POLICY,
           "note": "Gate output only. ALLOW makes the strategy eligible for candidate registration (export-candidate); "
                   "nothing is deployed or restarted by the pipeline."}
    (d / "05_risk_gate.json").write_text(json.dumps(res, indent=1))
    out(res)


def cmd_export_candidate(a):
    from . import deploy
    import os
    res = deploy.export_candidate(a.run_dir, a.strategies_dir, a.candidates_dir,
                                  host_root=a.host_root or os.environ.get("TP_HOST_ROOT", "~/trading"))
    (Path(a.run_dir) / "06_candidate.json").write_text(json.dumps(res, indent=1))
    out(res)


def _run_cost(run_id):
    return sum(e.get("cost", 0.0) for e in budget.entries() if e.get("run_id") == run_id)


def _budget_info():
    return {"task_spent": budget.task_spent(), "allowance": config.BUDGET_TOTAL}


def _notify_state():
    p = RUNS / "notify_state.json"
    return p, (json.loads(p.read_text()) if p.exists() else {})


def cmd_notify_run(a):
    from . import notify
    d = Path(a.run_dir)

    def j(name):
        p = d / name
        return json.loads(p.read_text()) if p.exists() else None
    r = j("02_researcher.json")
    fin = j("03_engineer_final.json")
    hyp = None
    if r:
        hs = r["output"]["hypotheses"]
        hyp = next((h for h in hs if fin and h["id"] == fin.get("hypothesis_id")), hs[0])
    cand = (j("06_candidate.json") or {}).get("candidate") if (j("06_candidate.json") or {}).get("exported") else None
    bt = j("03_backtest.json")
    msg = notify.format_run_summary(d.name, (bt or {}).get("market", a.market), hyp, bt, (j("04_auditor.json") or {}).get("output"),
                                    j("03b_ablation.json"), j("05_risk_gate.json"), _run_cost(d.name), _budget_info(), cand)
    results = [notify.send(msg, dry=a.dry)]
    if cand:
        results.append(notify.send(notify.format_candidate(cand), dry=a.dry))
    sp, st = _notify_state()
    spent, allow = budget.task_spent(), config.BUDGET_TOTAL
    if spent >= 0.8 * allow and not st.get("budget_warned"):
        results.append(notify.send(notify.format_budget_warning(spent, allow), dry=a.dry))
        if not a.dry:
            st["budget_warned"] = True
            sp.write_text(json.dumps(st))
    if a.dry:
        print(notify.scrub_message(msg))
    out({"results": [{k: v for k, v in x.items() if k != "preview"} for x in results], "enabled": notify.config()["enabled"]})


def cmd_notify_summary(a):
    """Send ONE run-summary text (read from a file under runs/) through the scrubbing, one-way Telegram sender."""
    from . import notify
    txt = (RUNS / a.file).read_text()
    out(notify.send(txt, dry=a.dry))


def cmd_notify_test(a):
    from . import notify
    out(notify.send("[pipeline] test message: notification channel is configured. (one-way, no commands are read)", dry=a.dry))


def cmd_library_build_index(a):
    from . import library
    out(library.build_index())


def cmd_library_show(a):
    from . import library
    print(library.index_text() if not a.id else library.card(a.id))


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
    out({"total_usd": round(budget.total_cost(), 6), "baseline_before_task_usd": config.BUDGET_BASELINE,
         "task_spent_usd": round(budget.task_spent(), 6), "task_allowance_usd": config.BUDGET_TOTAL,
         "task_stop_at_usd": config.BUDGET_TOTAL * config.BUDGET_STOP_FRAC,
         "task_remaining_before_stop_usd": round(config.BUDGET_TOTAL * config.BUDGET_STOP_FRAC - budget.task_spent(), 6),
         "by_model": by})


def main():
    p = argparse.ArgumentParser(prog="tp")
    sp = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **args):
        s = sp.add_parser(name)
        for k, v in args.items():
            s.add_argument("--" + k.replace("_", "-"), dest=k, **v)
        s.set_defaults(fn=fn)
    add("data-fetch", cmd_data_fetch)
    add("data-fetch-intraday", cmd_data_fetch_intraday)
    add("regime-run", cmd_regime_run, market={"default": "all", "choices": ["crypto", "kr", "us", "all"]},
        model={"default": "deepseek-flash"}, auditor={"default": "claude-haiku-5-5"})
    add("regime-injection-test", cmd_regime_injection_test, model={"default": "deepseek-flash"}, auditor={"default": "claude-haiku-5-5"})
    add("regime-verify", cmd_regime_verify)
    add("pool-evaluate", cmd_pool_evaluate, ids={"default": ""})
    add("allocate", cmd_allocate, regime_json={"default": ""}, profile={"default": "crypto_fast"}, symbols={"default": ""})
    add("krsurge-status", cmd_krsurge_status)
    add("liq-maps", cmd_liq_maps)
    add("arena-smoke", cmd_arena_smoke, bars={"type": int, "default": 2160}, agents={"type": int, "default": 4},
        base_cost={"type": float, "default": 5.0}, cost_multiplier={"type": float, "default": 1.0},
        review_every={"type": int, "default": 15}, synthetic={"action": "store_true"})
    add("sched-run", cmd_sched_run)
    add("watch-run", cmd_watch_run)
    add("watch-check", cmd_watch_check, summary={"action": "store_true"})
    add("fut-fetch", cmd_fut_fetch)
    add("fomc-fetch", cmd_fomc_fetch)
    add("rot-fetch", cmd_rot_fetch)
    add("hermes-export", cmd_hermes_export, out={"default": None})
    add("budget-check", cmd_budget_check)
    add("rot-study", cmd_rot_study, part={"default": "main", "choices": ["main", "cost", "lev", "phase", "filters"]})
    add("research-run", cmd_research_run, study={"required": True, "choices": ["s1", "s2", "s3_w15", "s3_w5", "s4"]})
    add("forward-eval", cmd_forward_eval)
    add("data-list", cmd_data_list)
    add("data-verify", cmd_data_verify)
    add("data-get", cmd_data_get, symbol={"required": True}, tf={"default": "1d"}, source={"default": "binance"},
        start={"default": None}, end={"default": None}, tail={"type": int, "default": 10})
    add("summary", cmd_summary)
    add("news-collect", cmd_news_collect)
    add("news-once", cmd_news_once, only={"default": ""})
    add("kis-collect", cmd_kis_collect)
    add("hl-collect", cmd_hl_collect)
    add("deriv-collect", cmd_deriv_collect)
    add("kis-probe", cmd_kis_probe, code={"default": "005930"})
    add("kis-backfill", cmd_kis_backfill)
    add("collector-status", cmd_collector_status)
    add("kis-fetch", cmd_kis_fetch, codes={"default": "005930,000660"}, days={"type": int, "default": 400})
    add("llm-turn", cmd_llm_turn)
    add("agent", cmd_agent, role={"choices": ["researcher", "auditor", "pool-researcher"], "required": True},
        strategy={"default": ""}, symbol={"default": "BTC/USDT"}, tf={"default": "1h"},
        model={"required": True}, run_dir={"required": True}, market={"default": "crypto", "choices": ["crypto", "kr"]},
        no_library={"action": "store_true"})
    add("sandbox-pytest", cmd_sandbox_pytest, dir={"required": True})
    add("sandbox-backtest", cmd_sandbox_backtest, dir={"required": True}, symbol={"required": True}, tf={"default": "1d"},
        market={"default": "crypto", "choices": ["crypto", "kr"]})
    add("sandbox-ablation", cmd_sandbox_ablation, dir={"required": True}, symbol={"required": True}, tf={"default": "1d"},
        market={"default": "crypto", "choices": ["crypto", "kr"]})
    add("export-candidate", cmd_export_candidate, run_dir={"required": True},
        strategies_dir={"default": "/export/strategies"}, candidates_dir={"default": "/app/candidates"},
        host_root={"default": None})
    add("notify-run", cmd_notify_run, run_dir={"required": True}, market={"default": "crypto"}, dry={"action": "store_true"})
    add("notify-test", cmd_notify_test, dry={"action": "store_true"})
    add("notify-summary", cmd_notify_summary, file={"required": True}, dry={"action": "store_true"})
    add("library-build-index", cmd_library_build_index)
    add("library-show", cmd_library_show, id={"default": None})
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
