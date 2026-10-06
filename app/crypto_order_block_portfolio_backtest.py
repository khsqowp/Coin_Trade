"""Cached daily perpetual portfolio research runner for order_block."""
from app.crypto_technical_ict_research import run_strategy


def run():
    return run_strategy("order_block")


if __name__ == "__main__":
    run()
