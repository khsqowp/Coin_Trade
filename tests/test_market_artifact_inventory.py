"""Focused tests for the metadata-only market inventory helper."""

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).parents[1] / "scripts/research/inventory_market_artifacts.py"
SPEC = importlib.util.spec_from_file_location("market_artifact_inventory", SCRIPT)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def test_market_hints_use_project_relative_path():
    assert inventory.infer_market(Path("/Users/test/Coin_Trade/chart_predictor/data/candles.sqlite"))[0] == "crypto"
    assert inventory.infer_market(Path("/Users/test/Ochestration/trading-tick-archive/2026/11/kr.jsonl"))[0] == "kr"
    assert inventory.infer_market(Path("/Users/test/Ochestration/trading-tick-archive/2026/11/crypto_perp.jsonl"))[0] == "crypto"
    assert inventory.infer_market(Path("/Users/test/Coin_Trade/docs/research/agent_strategy_research.md"))[0] == "unclassified"


def test_kind_hints_separate_tick_data_reports_and_scripts():
    assert inventory.infer_kind(Path("/tmp/trading-tick-archive/2026/11/kr.jsonl")) == "market_data_or_derived_data"
    assert inventory.infer_kind(Path("/tmp/Coin_Trade/docs/research/report.md")) == "research_document_or_spec"
    assert inventory.infer_kind(Path("/tmp/Coin_Trade/scripts/research/probe.py")) == "code_or_script"


def test_sensitive_extensions_and_components_are_excluded():
    assert not inventory.safe_path(Path("/repo/.env"))
    assert not inventory.safe_path(Path("/repo/certs/private.key"))
    assert inventory.safe_path(Path("/repo/docs/research/report.md"))


def test_relative_parts_do_not_mistag_equity_as_crypto_from_repo_name():
    assert inventory.relative_parts(Path("/Users/test/Coin_Trade/docs/research/stocks_kr.md")) == (
        "docs", "research", "stocks_kr.md"
    )
    assert inventory.infer_market(Path("/Users/test/Coin_Trade/docs/research/stocks_kr.md"))[0] == "kr"


def test_registry_market_hints_use_market_tokens_not_substrings():
    with TemporaryDirectory() as temp:
        path = Path(temp) / "registry.jsonl"
        path.write_text("\n".join([
            json.dumps({"id": 1, "track": "stock", "title": "US momentum", "scope": "US"}),
            json.dumps({"id": 2, "track": "stock", "title": "Cross-market", "scope": "KR and US"}),
            json.dumps({"id": 3, "track": "stock", "title": "Korean stocks", "scope": "KR"}),
            json.dumps({"id": 4, "track": "coin", "title": "Crypto setup", "scope": "crypto"}),
        ]) + "\n", encoding="utf-8")
        result = inventory.registry_rows(path)
    assert [row["market_hint"] for row in result] == ["us", "kr+us", "kr", "crypto"]


def test_large_untracked_tree_is_aggregated_and_virtualenv_excluded():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "scratchpad/results").mkdir(parents=True)
        (root / "scratchpad/results/run.csv").write_bytes(b"abc")
        (root / "scratchpad/.venv/site-packages").mkdir(parents=True)
        (root / "scratchpad/.venv/site-packages/package.py").write_bytes(b"ignored")
        row = inventory.scan_aggregate(root, "scratchpad")[0]
    assert row["file_count"] == 1
    assert row["bytes"] == 3
    assert row["git_status"] == "untracked_or_ignored"
