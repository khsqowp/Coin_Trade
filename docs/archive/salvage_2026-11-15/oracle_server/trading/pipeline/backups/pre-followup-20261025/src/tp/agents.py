"""Agent A (Researcher), B (Engineer), C (Auditor): prompts + schema-validated JSON runner."""
import json
import re

from . import llm
from .schemas import AUDITOR, ENGINEER_FINAL, RESEARCHER, validate


class SchemaError(RuntimeError):
    pass


def extract_json(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        raise ValueError("no JSON object found")
    return json.loads(t[i:j + 1])


def run_json(role, model, system, user, schema, *, run_id="", purpose="", max_tokens=3000, repair=1):
    """One call (+ at most `repair` repair calls). Returns (obj, meta)."""
    msgs = [{"role": "user", "content": user}]
    meta = {"model": model, "in_tok": 0, "out_tok": 0, "cost": 0.0, "latency": 0.0, "calls": 0, "schema_failures": 0}
    last = ""
    for _ in range(repair + 1):
        res = llm.chat(model, system, msgs, max_tokens=max_tokens, json_mode=True, role=role,
                       run_id=run_id, purpose=purpose)
        for k in ("in_tok", "out_tok", "cost", "latency"):
            meta[k] += res[k]
        meta["calls"] += 1
        try:
            obj = validate(extract_json(res["text"]), schema)
            return obj, meta
        except Exception as e:
            meta["schema_failures"] += 1
            last = str(e).splitlines()[0][:200]
            msgs += [{"role": "assistant", "content": res["text"][:3000]},
                     {"role": "user", "content": "Invalid output (%s). Return ONLY the corrected JSON object." % last}]
    raise SchemaError("schema validation failed after repair: " + last)


def _schema_text(schema):
    return json.dumps(schema, separators=(",", ":"))


RESEARCHER_SYS = (
    "You are the Researcher agent in a small trading-research pipeline (research and paper/dry-run only; "
    "no live trading). From the provided market-data summary, propose 1-2 falsifiable, rule-based, long/flat "
    "strategy hypotheses on a whitelisted symbol, daily timeframe, using OHLCV only, with at most 3 fixed "
    "parameters chosen from first principles (do NOT tune on the data). Be honest about expected failure modes. "
    "Respond with exactly one JSON object and nothing else, conforming to this JSON Schema:\n")


def researcher(model, data_summary, run_id):
    sys_ = RESEARCHER_SYS + _schema_text(RESEARCHER)
    user = "Market data summary (deterministically computed, with provenance):\n" + json.dumps(data_summary, indent=1)
    return run_json("researcher", model, sys_, user, RESEARCHER, run_id=run_id, purpose="hypotheses", max_tokens=2500)


ENGINEER_SYS = """You are the Engineer agent. Implement ONE hypothesis as a Python strategy and verify it with tools.
Rules for strategy.py:
- Expose generate_signals(df: pandas.DataFrame) -> pandas.Series. df has a UTC DatetimeIndex and float columns open, high, low, close, volume.
- Return float values 0.0 (flat) or 1.0 (long), same index as df, no NaN. The signal at bar t may use ONLY bars <= t.
  The trusted engine executes it at the next bar's open and charges fees+slippage: do NOT shift for execution yourself.
- Forbidden: shift(-n), centered rolling, bfill, whole-sample statistics (mean/std/quantile of the full series), parameter search/fitting on the data, any I/O or network.
- Allowed imports: pandas, numpy. Parameters are fixed constants taken from the hypothesis.
Rules for test_strategy.py: pytest with seeded synthetic data (no files, no network). Test output type/index/values, warm-up behaviour, causality (signal at bar k unchanged when later bars are removed) and at least one rule-specific behaviour test.
Workflow: write_file strategy.py -> write_file test_strategy.py -> run_tests (fix until pass) -> run_backtest (max 2 calls; never tune parameters to improve backtest numbers) -> reply with the FINAL JSON object only (no tool call), conforming to this JSON Schema:
"""

TOOLS = [
    {"name": "write_file", "description": "Create or overwrite strategy.py or test_strategy.py in the work directory.",
     "parameters": {"type": "object", "required": ["path", "content"], "additionalProperties": False,
                    "properties": {"path": {"enum": ["strategy.py", "test_strategy.py"]},
                                   "content": {"type": "string"}}}},
    {"name": "run_tests", "description": "Run pytest on test_strategy.py in an offline sandbox. Returns pass/fail output.",
     "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "run_backtest", "description": "Run the trusted walk-forward backtest (IS/OOS split, 4 folds, fees+slippage, "
                                             "lookahead truncation test) on the real dataset. Max 2 calls.",
     "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
]


def engineer_system():
    return ENGINEER_SYS + _schema_text(ENGINEER_FINAL)


AUDITOR_SYS = """You are the Auditor agent. You are independent from the Researcher and Engineer and your job is to REFUTE the strategy, not to confirm it.
Inspect the code and evidence for: (1) look-ahead bias (negative shift, centered windows, bfill / backward reindex, using bar-t information that is not known at bar-t close), (2) data leakage (whole-sample statistics, parameters fitted on the full sample, test data influencing the signal), (3) overfitting (many tuned parameters, large IS->OOS degradation, inconsistent folds), (4) missing fees/slippage, (5) insufficient sample (few trades / short OOS), (6) logic errors.
Verdict rules: PASS only if you found no defect and the evidence is adequate. FAIL if you found a defect or the statistics disqualify the strategy. INCONCLUSIVE if evidence is missing. Quote concrete code lines as evidence. Do not invent problems that are not in the code.
For checks use: clean | suspected | found | not_assessable.
Respond with exactly one JSON object and nothing else, conforming to this JSON Schema:
"""


def auditor(model, hypothesis, strategy_code, test_code, backtest, test_output, run_id, code_only=False, purpose="audit"):
    sys_ = AUDITOR_SYS + _schema_text(AUDITOR)
    if code_only:
        user = ("Context: long/flat strategy on BTC/USDT daily OHLCV; the engine executes the signal at the NEXT bar open "
                "with 0.1% fee + 5bp slippage per side. Statistics are NOT provided in this task: judge ONLY the code's "
                "causal/data integrity (checks other than lookahead_bias and data_leakage may be not_assessable; "
                "FAIL only for a real integrity defect).\n\n--- strategy.py ---\n" + strategy_code)
    else:
        import inspect
        from . import bt as _bt
        engine_src = inspect.getsource(_bt.simulate) + "\nFEE=%s SLIP=%s (per side)" % (_bt.FEE, _bt.SLIP)
        user = ("Hypothesis (from Researcher):\n" + json.dumps(hypothesis, indent=1) +
                "\n\n--- strategy.py ---\n" + strategy_code + "\n\n--- test_strategy.py ---\n" + test_code +
                "\n\n--- unit test output ---\n" + test_output[-1500:] +
                "\n\n--- trusted engine execution/cost model (bt.simulate) ---\n" + engine_src +
                "\n\n--- backtest report (trusted engine; includes truncation-based lookahead test) ---\n" +
                json.dumps(backtest, separators=(",", ":")))
    return run_json("auditor", model, sys_, user, AUDITOR, run_id=run_id, purpose=purpose, max_tokens=2500)
