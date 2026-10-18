"""Cached daily perpetual portfolio research runner for rsi."""
from app.crypto_technical_ict_research import run_strategy


def run():
    return run_strategy("rsi")


if __name__ == "__main__":
    run()
