"""Gate-passed strategy -> Freqtrade dry-run CANDIDATE registration. Never restarts or modifies a running bot.

What this does (only when every condition holds: Auditor PASS, ablation ok with no dead rule, Risk Engine
ALLOW re-computed from the raw evidence, evidence hashes match the current strategy.py, static code check ok):
  1. backs up the current Freqtrade strategies directory (copy) under candidates/backups/
  2. writes <cls>.py (generated signal code + a thin IStrategy wrapper, timeframe 1d, dry-run semantics) and
     <cls>.config.json (config overlay: dry_run=true, timeframe, single pair; NO secrets) into strategies dir.
     Existing files are never overwritten (name contains a hash of the code -> no collision with other strategies)
  3. writes candidates/<id>/compose.override.yml (separate DB, extra overlay config) and registry.json entry
  4. returns the swap / rollback commands. Executing them is the owner's decision.
"""
import ast
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

from . import ablation as abl
from .risk import RiskConfig, gate_strategy

ALLOWED_IMPORTS = {"pandas", "numpy", "math", "typing", "__future__"}
BANNED_CALLS = {"eval", "exec", "compile", "open", "__import__", "input", "getattr", "setattr", "delattr", "globals",
                "locals", "vars", "breakpoint", "exit", "quit", "memoryview"}
BANNED_ATTRS = {"to_csv", "to_parquet", "to_pickle", "to_json", "to_excel", "to_hdf", "to_sql", "to_feather",
                "to_clipboard", "to_stata", "to_orc", "to_xml", "to_html", "to_latex", "load", "save", "savetxt",
                "loadtxt", "fromfile", "tofile", "memmap", "genfromtxt", "system", "popen", "eval", "query"}
SAFE_TOP_CALLS = {"frozenset", "tuple", "dict", "list", "set", "int", "float", "str", "abs", "min", "max"}
MAX_CODE_BYTES = 20000


def static_check(code):
    """Return a list of violations ([] = ok). Pure AST allowlist; the code is never executed here."""
    if len(code.encode()) > MAX_CODE_BYTES:
        return ["code too large"]
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ["syntax error: %s" % e.msg]
    v = []
    for node in tree.body:  # top level: only imports, docstring, simple constants, function definitions
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.FunctionDef) and not node.decorator_list:
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Call) and not (isinstance(sub.func, ast.Name) and sub.func.id in SAFE_TOP_CALLS):
                    v.append("top-level call not allowed (line %d)" % node.lineno)
                if isinstance(sub, (ast.Attribute, ast.Lambda, ast.ListComp, ast.GeneratorExp, ast.DictComp, ast.SetComp)):
                    v.append("top-level expression too complex (line %d)" % node.lineno)
            continue
        v.append("top-level statement not allowed: %s (line %d)" % (type(node).__name__, node.lineno))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    v.append("import not allowed: %s" % a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                v.append("import not allowed: %s" % node.module)
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in BANNED_CALLS:
                v.append("banned call: %s" % f.id)
            if isinstance(f, ast.Attribute) and (f.attr in BANNED_ATTRS or f.attr.startswith("read_")):
                v.append("banned attribute call: %s" % f.attr)
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in BANNED_ATTRS or node.attr.startswith("read_"):
                v.append("banned attribute: %s" % node.attr)
        elif isinstance(node, (ast.Global, ast.Nonlocal, ast.ClassDef, ast.AsyncFunctionDef, ast.Await)):
            v.append("construct not allowed: %s" % type(node).__name__)
    return sorted(set(v))


def _load(run_dir):
    d = Path(run_dir)

    def j(name):
        p = d / name
        return json.loads(p.read_text()) if p.exists() else None
    return {"audit": (j("04_auditor.json") or {}).get("output"), "bt": j("03_backtest.json"),
            "abl": j("03b_ablation.json"), "gate": j("05_risk_gate.json"),
            "research": (j("02_researcher.json") or {}).get("output"), "final": j("03_engineer_final.json"),
            "code": (d / "work" / "strategy.py").read_text() if (d / "work" / "strategy.py").exists() else None}


def check_eligibility(run_dir, cfg=RiskConfig()):
    """Independent re-check from raw evidence. Returns (ok, reasons, ctx)."""
    c = _load(run_dir)
    r = []
    if not (c["audit"] and c["bt"] and c["code"]):
        return False, ["EVIDENCE_FILES_MISSING"], c
    if c["audit"].get("verdict") != "PASS":
        r.append("AUDIT_NOT_PASS")
    if not isinstance(c["abl"], dict) or c["abl"].get("status") != "ok":
        r.append("ABLATION_UNAVAILABLE")
    elif c["abl"].get("dead_rules"):
        r.append("DEAD_RULE")
    sha = hashlib.sha256(c["code"].encode()).hexdigest()
    for name, rep in (("backtest", c["bt"]), ("ablation", c["abl"] or {})):
        if rep.get("strategy_sha256") != sha:
            r.append("EVIDENCE_HASH_MISMATCH: %s" % name)
    dec = gate_strategy(c["audit"], c["bt"], c["bt"].get("symbol", ""), cfg, ablation=c["abl"])
    if not dec.allowed:
        r.extend("GATE: " + x for x in dec.reasons)
    if (c["gate"] or {}).get("decision") != "ALLOW_DRY_RUN":
        r.append("GATE_FILE_NOT_ALLOW")
    viol = static_check(c["code"])
    r.extend("CODE_CHECK: " + x for x in viol)
    c["sha"], c["warnings"] = sha, dec.warnings
    return not r, r, c


WRAPPER = '''

# ---------------------------------------------------------------------------- Freqtrade wrapper (generated)
from freqtrade.strategy import IStrategy  # noqa: E402


class {cls}(IStrategy):
    """Pipeline candidate {cid}: run {run_id}, symbol {symbol}. DRY-RUN ONLY. Daily long/flat from generate_signals().
    Signal on a completed daily candle -> Freqtrade acts at the next candle (same as the pipeline's next-open model).
    ROI/stoploss/trailing are deliberately disabled so the behaviour is exactly the backtested signal."""
    INTERFACE_VERSION = 3
    timeframe = "1d"
    can_short = False
    minimal_roi = {{"0": 100}}
    stoploss = -0.99
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    process_only_new_candles = True
    startup_candle_count = 400

    def populate_indicators(self, dataframe, metadata):
        df = dataframe.set_index("date")[["open", "high", "low", "close", "volume"]].astype(float)
        sig = generate_signals(df)
        dataframe["tp_signal"] = sig.reindex(df.index).fillna(0.0).values
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        dataframe.loc[dataframe["tp_signal"] >= 1.0, ["enter_long", "enter_tag"]] = (1, "tp_signal")
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        dataframe.loc[dataframe["tp_signal"] <= 0.0, ["exit_long", "exit_tag"]] = (1, "tp_signal_flat")
        return dataframe
'''

COMPOSE = '''# Candidate override for the existing 'freqtrade' service. NOT applied automatically.
services:
  freqtrade:
    command: >
      trade
      --logfile /freqtrade/user_data/logs/freqtrade.log
      --db-url sqlite:////freqtrade/user_data/tradesv3_{cid}.sqlite
      --config /freqtrade/user_data/config.json
      --config /freqtrade/user_data/strategies/{cls}.config.json
      --strategy {cls}
'''


def safe_name(symbol):
    return "".join(ch for ch in symbol if ch.isalnum())


def export_candidate(run_dir, strategies_dir, candidates_dir, host_root="~/trading", cfg=RiskConfig(), now=None):
    ok, reasons, c = check_eligibility(run_dir, cfg)
    if not ok:
        return {"exported": False, "reasons": reasons}
    now = now or dt.datetime.now(dt.timezone.utc)
    run_id = Path(run_dir).name
    hid = (c["final"] or {}).get("hypothesis_id", "H1")
    symbol = c["bt"]["symbol"]
    cid = "%s_%s_%s" % (safe_name(symbol), hid, c["sha"][:8])
    cls = "TPC_" + cid
    sdir, cdir = Path(strategies_dir), Path(candidates_dir)
    target, overlay = sdir / (cls + ".py"), sdir / (cls + ".config.json")
    reg_path = cdir / "registry.json"
    registry = json.loads(reg_path.read_text()) if reg_path.exists() else []
    if target.exists():
        same = target.read_text().count(c["code"].strip()[:200]) > 0
        existing = next((x for x in registry if x["id"] == cid), None)
        if same and existing:
            return {"exported": False, "reasons": ["ALREADY_REGISTERED"], "candidate": existing}
        return {"exported": False, "reasons": ["NAME_COLLISION: %s exists and is not a registered candidate" % target.name]}
    bdir = cdir / "backups" / ("strategies-" + now.strftime("%Y%m%dT%H%M%SZ"))
    bdir.mkdir(parents=True, exist_ok=False)
    for p in sdir.glob("*"):
        if p.is_file():
            shutil.copy2(p, bdir / p.name)
    header = ("# AUTO-GENERATED by tp-pipeline (candidate %s). Source run: %s. strategy.py sha256: %s\n"
              "# LLM-written signal code, statically checked (imports limited to pandas/numpy). DRY-RUN ONLY.\n\n" % (cid, run_id, c["sha"]))
    target.write_text(header + c["code"].rstrip() + "\n" + WRAPPER.format(cls=cls, cid=cid, run_id=run_id, symbol=symbol))
    overlay.write_text(json.dumps({"dry_run": True, "timeframe": "1d", "bot_name": "freqtrade-dryrun-" + cid,
                                   "max_open_trades": 1, "exchange": {"pair_whitelist": [symbol]}}, indent=1))
    ddir = cdir / cid
    ddir.mkdir(parents=True, exist_ok=True)
    (ddir / "compose.override.yml").write_text(COMPOSE.format(cid=cid, cls=cls))
    hr = host_root.rstrip("/")
    cand = {
        "id": cid, "class": cls, "run_id": run_id, "symbol": symbol, "status": "candidate_registered",
        "created": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "strategy_sha256": c["sha"],
        "strategy_file": "freqtrade/user_data/strategies/%s.py" % cls, "backup_dir": str(bdir.relative_to(cdir)),
        "gate_warnings": c["warnings"],
        "swap_command": "cd %s && docker compose -f docker-compose.yml -f pipeline/candidates/%s/compose.override.yml up -d --force-recreate freqtrade" % (hr, cid),
        "rollback_command": "cd %s && docker compose -f docker-compose.yml up -d --force-recreate freqtrade" % hr,
        "note": "Registered only. The running dry-run bot was not touched; swapping is the owner's decision.",
    }
    registry.append(cand)
    reg_path.write_text(json.dumps(registry, indent=1))
    return {"exported": True, "candidate": cand}
