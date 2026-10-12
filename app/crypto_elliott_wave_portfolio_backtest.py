"""Cached daily perpetual portfolio research runner for elliott_wave."""
from app.crypto_technical_ict_research import run_strategy


def run():
    return run_strategy("elliott_wave")


if __name__ == "__main__":
    run()
