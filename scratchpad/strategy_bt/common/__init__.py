"""Shared, strategy-agnostic historical backtest harness."""

from .engine import simulate, metrics
from .protocol import evaluate

__all__ = ["simulate", "metrics", "evaluate"]
