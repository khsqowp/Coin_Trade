"""Cached daily perpetual portfolio research runner for fibonacci."""
from app.crypto_technical_ict_research import run_strategy


def run():
    return run_strategy("fibonacci")


if __name__ == "__main__":
    run()
