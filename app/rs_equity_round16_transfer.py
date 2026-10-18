"""Round16 equity adaptation with explicitly synthetic OHLC liquidation tiers."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.crypto_bucket_ensemble_research import volume_prep
from app.crypto_round16_liquidation_research import FAMILIES, plans
from app.liquidation_proximity_signal_core import TIER_SETS, find_signals as proximity_signals
from app.round12_signals import find_signals as round12_signals


ROOT = Path(__file__).resolve().parents[1]
CRYPTO_RESULT = ROOT / "docs/round16-results-2026-10-08.json"


def round16_configs() -> list[dict[str, Any]]:
    """Return all 397 source plans with source execution provenance attached."""
    result = json.loads(CRYPTO_RESULT.read_text(encoding="utf-8"))
    provenance = result["donor_provenance"]
    configs = []
    for index, source_config in enumerate(plans(), start=1):
        variant = source_config["variant"]
        family = source_config.get("family", "volume")
        execution = dict(provenance[family]["config"]) if variant == "control_C" else {}
        execution.setdefault("family", family)
        if variant == "reference":
            execution["hold_days"] = 20
        elif variant == "control_D":
            execution["hold_days"] = source_config["hold_days"]
        elif variant in ("A", "B", "D"):
            execution["family"] = "volume"
            execution["hold_days"] = source_config["hold_days"]
        configs.append(
            {
                **source_config,
                "phase": f"R16-{index:03d}",
                "policy_group": f"{variant} liquidation-tier proxy" if "tier_set" in source_config else f"{variant} control",
                "execution": execution,
            }
        )
    serialized = [json.dumps(config, sort_keys=True) for config in configs]
    if len(configs) != 397 or len(serialized) != len(set(serialized)):
        raise ValueError("Round16 source plan count or uniqueness changed")
    return configs


def _base_signals(raw: pd.DataFrame, family: str, execution: dict[str, Any], symbol: str) -> pd.DataFrame:
    if family == "volume":
        multiple = float(execution.get("volume_multiple", 3.0))
        return volume_prep({symbol: raw}, multiple=multiple)[symbol].copy()
    if family == "donchian":
        return round12_signals(raw, family, **execution.get("params", {})).copy()
    module = importlib.import_module(f"app.{family}_signal_core")
    signal_input = raw
    if family == "ema_cross" and raw.index.tz is None:
        signal_input = raw.copy()
        signal_input.index = signal_input.index.tz_localize("UTC")
    result = module.find_signals(signal_input).copy()
    if result.index.tz is not None and raw.index.tz is None:
        result.index = result.index.tz_convert(None)
    return result


def prepare_round16(
    panel, config: dict[str, Any], dates: pd.DatetimeIndex,
    cache: dict[tuple, pd.DataFrame] | None = None,
) -> dict[str, pd.DataFrame]:
    """Build causal entry/exit fields using the source's fixed tier/window rules."""
    execution = config["execution"]
    family = execution["family"]
    variant = config["variant"]
    cache = {} if cache is None else cache
    prepared = {}
    for index, symbol in enumerate(panel.symbols):
        raw = pd.DataFrame(
            {
                "Open": panel.o[:, index], "High": panel.h[:, index],
                "Low": panel.l[:, index], "Close": panel.c[:, index],
                "Volume": panel.v[:, index],
            },
            index=panel.dates,
        )
        valid_bars = np.isfinite(raw[["Open", "High", "Low", "Close", "Volume"]]).all(axis=1)
        valid_bars &= raw["Open"].gt(0) & raw["High"].gt(0) & raw["Low"].gt(0) & raw["Close"].gt(0)
        signal_bars = raw.loc[valid_bars]
        base_key = ("base", symbol, family, json.dumps(execution, sort_keys=True))
        if base_key not in cache:
            cache[base_key] = _base_signals(signal_bars, family, execution, symbol)
        frame = cache[base_key].copy()
        if variant in ("A", "B", "C", "D"):
            tiers = TIER_SETS[int(config["tier_set"])]
            proxy_key = ("proxy", symbol, int(config["window"]), tuple(tiers))
            if proxy_key not in cache:
                cache[proxy_key] = proximity_signals(
                    signal_bars, window=int(config["window"]), tiers=tiers,
                    threshold=1.0,
                )
            proxy = cache[proxy_key]
            near = proxy["DOWN_DISTANCE"].le(float(config["threshold"]))
            if variant == "A":
                frame["SIGNAL"] = near
                frame["VOL_RATIO"] = proxy["VOL_RATIO"]
            elif variant == "B":
                frame["SIGNAL"] = frame["SIGNAL"].astype(bool) & near
            elif variant == "D":
                momentum = signal_bars["Close"].pct_change(30, fill_method=None)
                frame["SIGNAL"] = momentum.gt(0)
                frame["VOL_RATIO"] = momentum * np.where(near, 2.0, 1.0)
            if variant in ("A", "C"):
                frame["EXIT_SIGNAL"] = proxy["EXIT_SIGNAL"].astype(bool)
        if variant == "control_D":
            momentum = signal_bars["Close"].pct_change(30, fill_method=None)
            frame["SIGNAL"] = momentum.gt(0)
            frame["VOL_RATIO"] = momentum
        frame = frame.reindex(panel.dates)
        frame["SIGNAL"] = frame["SIGNAL"].fillna(False).astype(bool)
        frame["VOL_RATIO"] = frame["VOL_RATIO"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if "EXIT_SIGNAL" in frame:
            frame["EXIT_SIGNAL"] = frame["EXIT_SIGNAL"].fillna(False).astype(bool)
        frame["SIGNAL"] = frame["SIGNAL"].fillna(False).astype(bool)
        if not panel.eligible[:, index].all():
            frame["SIGNAL"] &= pd.Series(panel.eligible[:, index], index=panel.dates)
        frame["Open"] = frame["Open"].where(panel.tradable[:, index])
        prepared[symbol] = frame.loc[dates].copy()
    return prepared
