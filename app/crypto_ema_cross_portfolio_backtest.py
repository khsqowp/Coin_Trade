"""Cached daily perpetual portfolio research runner for ema_cross."""
from app.crypto_technical_ict_research import run_strategy


def run():
    return run_strategy("ema_cross")


if __name__ == "__main__":
    run()
