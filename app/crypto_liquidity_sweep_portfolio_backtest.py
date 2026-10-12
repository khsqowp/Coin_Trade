"""Cached daily perpetual portfolio research runner for liquidity_sweep."""
from app.crypto_technical_ict_research import run_strategy


def run():
    return run_strategy("liquidity_sweep")


if __name__ == "__main__":
    run()
