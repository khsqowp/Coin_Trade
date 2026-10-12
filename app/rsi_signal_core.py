"""rsi: causal signal core and shared portfolio engine."""
from app.technical_signal_common import find
from app.technical_portfolio_engine import simulate_portfolio


def find_signals(frame):
    return find(frame, "rsi")
