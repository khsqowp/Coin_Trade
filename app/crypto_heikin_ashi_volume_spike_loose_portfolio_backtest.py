"""Offline loose hybrid standalone runner."""
from app.crypto_hybrid_drawdown_research import run_strategy


def run():
    return run_strategy('heikin_ashi_volume_spike_loose')


if __name__=='__main__':
    run()
