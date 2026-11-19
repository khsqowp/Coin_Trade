import ast
from pathlib import Path

from chart_predictor import path_method_oracle
from scripts.research.validate_crypto_ohlc_path_method import (
    _make_path, _run_sentinels,
)
import random


def test_scalar_oracle_has_no_production_execution_imports_or_calls():
    source = Path(path_method_oracle.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    called = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.append(node.func.attr)
    assert not any("crypto_divergence_engine" in module for module in imported)
    assert not {"evaluate_divergence_event", "_resolve_path", "_net_r"}.intersection(called)


def test_seeded_path_generation_is_repeatable():
    first = _make_path(random.Random(20261127), 5, 10)
    second = _make_path(random.Random(20261127), 5, 10)
    assert first == second
    assert len(first[0]) == 5 * (3 + 10)


def test_all_preregistered_sentinels_match_fixed_expected_values():
    results = _run_sentinels()
    assert len(results) == 17
    assert all(item["actual_match"] for item in results)
    assert all(item["oracle_match"] for item in results)
    assert all(item["actual_oracle_match"] for item in results)
