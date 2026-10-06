"""Offline baseline runner using the Round 2 common engine."""
from app.crypto_hybrid_drawdown_research import run_strategy


def run():
    return run_strategy('heikin_ashi_volume_spike')


if __name__=='__main__':
    run()
