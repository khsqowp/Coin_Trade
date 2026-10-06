"""Cached daily perpetual portfolio research runner for heikin_ashi."""
from app.crypto_technical_ict_research import run_strategy


def run():
    return run_strategy("heikin_ashi")


if __name__ == "__main__":
    run()
