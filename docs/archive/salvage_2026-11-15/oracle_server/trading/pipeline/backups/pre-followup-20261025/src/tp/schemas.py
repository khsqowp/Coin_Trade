"""Fixed JSON schemas for inter-agent I/O (validated with jsonschema)."""
import jsonschema

SYMS = ["BTC/USDT", "ETH/USDT"]
_str = {"type": "string", "minLength": 1}

RESEARCHER = {
    "type": "object", "additionalProperties": False,
    "required": ["market_summary", "hypotheses", "research_plan"],
    "properties": {
        "market_summary": _str,
        "hypotheses": {"type": "array", "minItems": 1, "maxItems": 2, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "name", "rationale", "symbol", "timeframe", "entry_rule", "exit_rule",
                         "parameters", "expected_failure_modes"],
            "properties": {
                "id": {"enum": ["H1", "H2"]}, "name": _str, "rationale": _str,
                "symbol": {"enum": SYMS}, "timeframe": {"enum": ["1d"]},
                "entry_rule": _str, "exit_rule": _str, "parameters": {"type": "object"},
                "expected_failure_modes": {"type": "array", "items": _str}}}},
        "research_plan": {"type": "object", "additionalProperties": False,
                          "required": ["steps", "validation", "success_criteria"],
                          "properties": {"steps": {"type": "array", "minItems": 1, "items": _str},
                                         "validation": _str,
                                         "success_criteria": {"type": "object"}}},
    },
}

ENGINEER_FINAL = {
    "type": "object", "additionalProperties": False,
    "required": ["hypothesis_id", "strategy_file", "test_file", "summary", "tests_passed",
                 "backtest_run", "known_limitations"],
    "properties": {"hypothesis_id": {"enum": ["H1", "H2"]}, "strategy_file": _str, "test_file": _str,
                   "summary": _str, "tests_passed": {"type": "boolean"}, "backtest_run": {"type": "boolean"},
                   "known_limitations": {"type": "array", "items": _str}},
}

CATEGORIES = ["lookahead_bias", "data_leakage", "overfitting", "costs_missing", "sample_insufficient",
              "logic_error", "other"]
CHECK_STATE = {"enum": ["clean", "suspected", "found", "not_assessable"]}
AUDITOR = {
    "type": "object", "additionalProperties": False,
    "required": ["verdict", "findings", "checks", "stats_assessment", "confidence", "rationale"],
    "properties": {
        "verdict": {"enum": ["PASS", "FAIL", "INCONCLUSIVE"]},
        "findings": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["category", "severity", "evidence", "location"],
            "properties": {"category": {"enum": CATEGORIES},
                           "severity": {"enum": ["info", "low", "medium", "high", "critical"]},
                           "evidence": _str, "location": _str}}},
        "checks": {"type": "object", "additionalProperties": False,
                   "required": ["lookahead_bias", "data_leakage", "overfitting", "costs_slippage",
                                "sample_size"],
                   "properties": {k: CHECK_STATE for k in
                                  ["lookahead_bias", "data_leakage", "overfitting", "costs_slippage",
                                   "sample_size"]}},
        "stats_assessment": _str,
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": _str,
    },
}


def validate(obj, schema):
    jsonschema.validate(obj, schema)
    return obj
