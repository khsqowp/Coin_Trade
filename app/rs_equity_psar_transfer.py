"""Transfer the pinned pandas-ta Parabolic SAR strategy signal to US/KR stocks.

This is a supplemental daily-signal transfer using the shared next-open engine.
It does not claim parity with backtesting.py's intrabar trailing-stop fills or
the source strategy's risk-sized order quantities.
"""
from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-cache")

from app.rs_equity_round12_13_portfolio import _costs, _run_config
from app.rs_equity_round13_runner import market_context
from app.rs_equity_transfer import load_equity_panel


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/psar_native_transfer.json"
START = pd.Timestamp("2019-01-01")


def prepare_psar(panel, dates: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    # pandas-ta 0.4.71b0 compiles one helper with Numba disk caching on import.
    os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-cache")
    import pandas_ta as ta

    prepared = {}
    for j, symbol in enumerate(panel.symbols):
        raw = pd.DataFrame({
            "Open": panel.o[:, j], "High": panel.h[:, j],
            "Low": panel.l[:, j], "Close": panel.c[:, j],
            "Volume": panel.v[:, j],
        }, index=panel.dates)
        valid = np.isfinite(raw[["Open", "High", "Low", "Close", "Volume"]]).all(axis=1)
        valid &= raw[["Open", "High", "Low", "Close"]].gt(0).all(axis=1)
        bars = raw.loc[valid]
        frame = pd.DataFrame(index=panel.dates)
        for column in ("Open", "High", "Low", "Close"):
            frame[column] = raw[column]
        frame["SIGNAL"] = False
        frame["EXIT_SIGNAL"] = False
        frame["VOL_RATIO"] = 0.0
        frame["ATR14"] = 0.0
        frame["STOP_LEVEL"] = np.nan
        if len(bars) >= 2:
            psar = ta.psar(bars.High, bars.Low, bars.Close, af0=0.02, af=0.02, max_af=0.2)
            long_col = next(c for c in psar if c.startswith("PSARl_"))
            short_col = next(c for c in psar if c.startswith("PSARs_"))
            bullish = psar[long_col].notna()
            signal = bullish & bars.Close.gt(psar[long_col])
            frame.loc[bars.index, "SIGNAL"] = signal.to_numpy(bool)
            frame.loc[bars.index, "EXIT_SIGNAL"] = (~bullish).to_numpy(bool)
            frame.loc[bars.index, "STOP_LEVEL"] = psar[long_col].to_numpy(float)
        frame["SIGNAL"] = frame["SIGNAL"].fillna(False).astype(bool)
        frame["EXIT_SIGNAL"] = frame["EXIT_SIGNAL"].fillna(False).astype(bool)
        frame["Open"] = raw.Open.where(panel.tradable[:, j])
        if not panel.eligible[:, j].all():
            frame["SIGNAL"] &= pd.Series(panel.eligible[:, j], index=panel.dates)
        prepared[symbol] = frame.loc[dates].copy()
    return prepared


def run_market(market: str) -> dict:
    panel = load_equity_panel(market)
    dates = panel.dates[int(panel.dates.searchsorted(START)):]
    gate, breadth = market_context(panel)
    prepared = prepare_psar(panel, dates)
    config = {
        "phase": "PSAR-TA-0.4.71b0",
        "policy_group": "native Parabolic SAR signal; common next-open portfolio execution",
        "top_k": 8,
        "hold_days": 10000,
        "stop": "none",
        "sizing": "inverse_vol",
        "target_vol": 0.40,
        "weight_cap": 0.25,
        "selection": "rank",
    }
    rows = []
    for cost in _costs(panel):
        row = _run_config(panel, config, dates, gate, breadth, cost, prepared_override=prepared)
        rows.append(row)
    return {
        "market": market,
        "symbols": len(panel.symbols),
        "date_range": [str(dates[0].date()), str(dates[-1].date())],
        "trading_dates": [str(d.date()) for d in dates],
        "source_library": "pandas-ta",
        "source_library_version": importlib.metadata.version("pandas-ta"),
        "execution_difference": "shared next-open portfolio engine, bearish reversal exits next open; no intrabar dynamic PSAR trailing-stop fill; common inverse-vol/top_k sizing replaces source risk_per_trade sizing",
        "rows": rows,
    }


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    payload = {
        "source": "app/broad_strategies.py ParabolicSarStrategy + requirements.txt pandas-ta pin",
        "timeframe": "1d only; no stock intraday OHLCV available in the adapter",
        "parameters": {"af0": 0.02, "af": 0.02, "max_af": 0.2, "warmup_bars": 20},
        "markets": {m: run_market(m) for m in ("US", "KR")},
        "note": "Signal-level transfer, not exact account/execution reproduction. No synthesized 4h bars.",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps({m: {"rows": len(v["rows"]), "version": v["source_library_version"]}
                      for m, v in payload["markets"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
