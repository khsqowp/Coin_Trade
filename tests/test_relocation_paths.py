"""Regression checks for source paths when this checkout is outside ~/Desktop."""

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEGACY_ROOT = str(Path.home() / "Desktop" / "CODE" / "Ochestration")


def _load_module(relative_path: str, module_name: str):
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not create import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_us_cache_default_follows_checkout_root(monkeypatch):
    monkeypatch.delenv("US_CACHE", raising=False)
    module = _load_module("trading/app/rs_us_engine.py", "relocation_rs_us_engine")

    assert module.PROJECT_ROOT == PROJECT_ROOT
    assert module.CACHE == PROJECT_ROOT / ".kis-cache"


def test_us_cache_environment_override_is_preserved(monkeypatch, tmp_path):
    monkeypatch.setenv("US_CACHE", str(tmp_path))
    module = _load_module(
        "trading/app/rs_us_engine.py", "relocation_rs_us_engine_override"
    )

    assert module.CACHE == tmp_path


def test_audit_engine_paths_follow_checkout_root():
    module = _load_module(
        "trading/app/rs_audit_engine.py", "relocation_rs_audit_engine"
    )

    assert module.ROOT == PROJECT_ROOT / "trading"
    assert module.CACHE == PROJECT_ROOT / "trading" / ".rs_cache" / "vision"


RELOCATABLE_SCRIPTS = (
    "trading/docs/research/tp_loop/review/diag_events.py",
    "trading/docs/research/tp_loop/review/confirm_run.py",
    "trading/docs/research/tp_loop/review/rerun_headlines.py",
    "trading/docs/research/lev_loop/B/check_v0.py",
    "trading/docs/research/lev_loop/R2C/r2c_samples.py",
    "trading/docs/research/lev_loop/R2C/r2c_smoke_lib.py",
    "trading/docs/research/lev_loop/R2C/r2c_events.py",
    "trading/docs/research/lev_loop/R2C/r2c_smoke_data.py",
    "trading/docs/research/lev_loop/R2C/r2c_universe_stats.py",
    "trading/docs/research/lev_loop/R2C/r2c_main.py",
    "trading/docs/research/lev_loop/R2C/r2c_power.py",
    "trading/docs/research/lev_loop/R2C/r2c_smoke_v0.py",
    "trading/docs/research/lev_loop/R2C/hash_log.sh",
    "trading/docs/research/lev_loop/review2/rerun/r2b_liq_rerun.py",
    "trading/docs/research/lev_loop/review2/rerun/r2a_repro.py",
    "trading/docs/research/lev_loop/review2/rerun/r2b_live_rerun.py",
    "trading/docs/research/lev_loop/review2/audit/aud_stress_exposure.py",
    "trading/docs/research/lev_loop/review2/audit/aud_norm_live.py",
)


TRADING_ROOT_PARENT_INDEX = {
    "trading/docs/research/lev_loop/B/check_v0.py": 4,
    "trading/docs/research/lev_loop/R2C/r2c_samples.py": 4,
    "trading/docs/research/lev_loop/R2C/r2c_smoke_lib.py": 4,
    "trading/docs/research/lev_loop/R2C/r2c_events.py": 4,
    "trading/docs/research/lev_loop/R2C/r2c_smoke_data.py": 4,
    "trading/docs/research/lev_loop/R2C/r2c_universe_stats.py": 4,
    "trading/docs/research/lev_loop/R2C/r2c_main.py": 4,
    "trading/docs/research/lev_loop/R2C/r2c_power.py": 4,
    "trading/docs/research/lev_loop/R2C/r2c_smoke_v0.py": 4,
    "trading/docs/research/lev_loop/review2/rerun/r2b_liq_rerun.py": 5,
    "trading/docs/research/lev_loop/review2/rerun/r2a_repro.py": 5,
    "trading/docs/research/lev_loop/review2/audit/aud_stress_exposure.py": 5,
    "trading/docs/research/lev_loop/review2/audit/aud_norm_live.py": 5,
}

RELATIVE_PATH_EXPECTATIONS = {
    "trading/docs/research/tp_loop/review/diag_events.py": (
        "REVIEW_DIR = Path(__file__).resolve().parent",
        0,
        PROJECT_ROOT / "trading/docs/research/tp_loop/review",
    ),
    "trading/docs/research/tp_loop/review/confirm_run.py": (
        "REVIEW_DIR = Path(__file__).resolve().parent",
        0,
        PROJECT_ROOT / "trading/docs/research/tp_loop/review",
    ),
    "trading/docs/research/tp_loop/review/rerun_headlines.py": (
        'Path(__file__).resolve().parent.parent / "A"',
        1,
        PROJECT_ROOT / "trading/docs/research/tp_loop",
    ),
    "trading/docs/research/lev_loop/review2/rerun/r2b_live_rerun.py": (
        'Path(__file__).resolve().parent / "_out_r2b_live"',
        0,
        PROJECT_ROOT / "trading/docs/research/lev_loop/review2/rerun",
    ),
    "trading/docs/research/lev_loop/R2C/hash_log.sh": (
        "SCRIPT_DIR/../../../..",
        4,
        PROJECT_ROOT / "trading",
    ),
}


@pytest.mark.parametrize("relative_path", RELOCATABLE_SCRIPTS)
def test_research_scripts_do_not_pin_the_old_checkout(relative_path):
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    assert LEGACY_ROOT not in source


@pytest.mark.parametrize(
    "relative_path,parent_index", TRADING_ROOT_PARENT_INDEX.items()
)
def test_research_script_root_expression_resolves_to_this_checkout(
    relative_path, parent_index
):
    script_path = PROJECT_ROOT / relative_path
    source = script_path.read_text(encoding="utf-8")

    assert f".parents[{parent_index}]" in source
    assert script_path.resolve().parents[parent_index] == PROJECT_ROOT / "trading"


@pytest.mark.parametrize(
    "relative_path,expression,parent_index,expected_directory",
    [(path, *expectation) for path, expectation in RELATIVE_PATH_EXPECTATIONS.items()],
)
def test_nested_research_paths_resolve_from_their_script(
    relative_path, expression, parent_index, expected_directory
):
    script_path = PROJECT_ROOT / relative_path
    source = script_path.read_text(encoding="utf-8")

    assert expression in source
    assert script_path.resolve().parents[parent_index] == expected_directory
