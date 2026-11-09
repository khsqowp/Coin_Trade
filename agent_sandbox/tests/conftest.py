"""Project imports and deterministic offline fixtures."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from config import Config
from state import StateStore
from generation import initialize
from ledger import Ledger


@pytest.fixture
def cfg(tmp_path):
    return Config(state_dir=str(tmp_path / "state"))


@pytest.fixture
def ledger(cfg):
    store = StateStore(cfg.state_dir)
    initialize(store, cfg, 1704067200.0)
    result = Ledger(store, cfg)
    result.now = 1704067200.0
    result.prices = {"BTCUSDT": 100.0, "ETHUSDT": 100.0}
    result.symbol_info = {
        s: {"stepSize": "0.001", "tickSize": "0.01", "minQty": 0.001, "minNotional": 5}
        for s in result.prices
    }
    return result
