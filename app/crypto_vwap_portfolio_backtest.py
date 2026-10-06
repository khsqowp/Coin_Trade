"""Cached daily perpetual portfolio research runner for vwap."""
from app.crypto_technical_ict_research import run_strategy


def run():
    return run_strategy("vwap")


if __name__ == "__main__":
    run()
