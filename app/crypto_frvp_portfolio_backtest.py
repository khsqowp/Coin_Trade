"""Cached daily perpetual portfolio research runner for frvp."""
from app.crypto_technical_ict_research import run_strategy


def run():
    return run_strategy("frvp")


if __name__ == "__main__":
    run()
