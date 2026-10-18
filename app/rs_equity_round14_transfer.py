"""Inventory Round14's predeclared portfolio configurations for equity transfer."""
from __future__ import annotations

from typing import Any

from app.crypto_round14_research import plans


def round14_configs() -> list[dict[str, Any]]:
    source = plans()
    configs = []
    for index, config in enumerate(source, start=1):
        if "params" in config:
            group = "Donchian lookback × holding period"
        elif "rank" in config:
            group = "cross-sectional rank × holding period"
        elif config.get("btc_hysteresis") != 0.03:
            group = "BTC-proxy hysteresis width × holding period"
        else:
            group = "holding-period sensitivity"
        configs.append(
            {
                **config,
                "phase": f"R14-{index:02d}",
                "policy_group": group,
            }
        )
    keys = [repr(sorted(config.items())) for config in configs]
    if len(keys) != len(set(keys)):
        raise ValueError("Round14 source plans contain duplicate configurations")
    return configs
