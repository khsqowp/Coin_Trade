"""Validated configuration without environment-variable discovery."""

from dataclasses import dataclass, field, fields
from pathlib import Path
import json
import math


@dataclass
class Config:
    tick_minutes: int = 60
    start_equity: float = 1000.0
    weekly_target: float = 100.0
    max_leverage: int = 10
    max_positions: int = 5
    max_risk_per_trade_pct: float = 5.0
    max_gross_exposure_x: float = 3.0
    daily_loss_limit_pct: float = 15.0
    stale_data_seconds: int = 300
    throttle_per_minute: int = 20
    taker_fee_rate: float = 0.0005
    watchlist: list[str] = field(
        default_factory=lambda: [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "BNBUSDT",
            "XRPUSDT",
            "DOGEUSDT",
            "ADAUSDT",
            "AVAXUSDT",
            "LINKUSDT",
            "TRXUSDT",
        ]
    )
    core_symbols: list[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    decisions_history_n: int = 10
    codex_model: str | None = None
    codex_timeout_seconds: int = 600
    codex_web_search: bool = True
    state_dir: str = "state"
    random_benchmark_runs: int = 200


def load_config(path: str | Path | None = None) -> Config:
    target = Path(path or "config.json")
    data = json.loads(target.read_text()) if target.exists() else {}
    if not isinstance(data, dict) or set(data) - {f.name for f in fields(Config)}:
        raise ValueError("Configuration must be an object with known keys")
    cfg = Config(**data)
    for f in fields(cfg):
        value = getattr(cfg, f.name)
        default = getattr(Config(), f.name)
        if isinstance(default, bool):
            valid = isinstance(value, bool)
        elif isinstance(default, int):
            valid = type(value) is int and value > 0
        elif isinstance(default, float):
            valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
        elif isinstance(default, list):
            valid = isinstance(value, list) and all(
                isinstance(x, str) and x.isalnum() for x in value
            )
        else:
            valid = (
                isinstance(value, str)
                if default is not None
                else value is None or isinstance(value, str)
            )
        if not valid:
            raise ValueError(f"Invalid configuration field: {f.name}")
    if cfg.start_equity <= 0 or cfg.max_gross_exposure_x <= 0:
        raise ValueError("Equity and exposure limit must be positive")
    # All persistent writes remain under the project, including custom configurations.
    root = Path(__file__).resolve().parent
    resolved = Path(cfg.state_dir).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("state_dir must be inside the project directory")
    return cfg
