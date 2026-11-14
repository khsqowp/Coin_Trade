"""Generate prediction-only replay feature batches."""
import json
from pathlib import Path
import sqlite3
import pandas as pd
from .collector import DB_PATH
from .features import build_features
from .splits import build_anchors, split_anchors, symbol_split


def replay(split, symbols, timeframe, db_path=DB_PATH, output=None, registry_path=None):
    """Write anchor-only JSON batches and manifests for selected symbols."""
    db_path = db_path or DB_PATH
    output = Path(output or Path(__file__).parent / "data" / "batches")
    output.mkdir(parents=True, exist_ok=True)
    manifest, count = [], 0
    for symbol in symbols:
        if split == "dev" and symbol_split(symbol) != "dev":
            continue
        if split == "validation" and symbol_split(symbol) != "heldout":
            continue
        anchors = build_anchors(symbol, timeframe, db_path, registry_path) if registry_path else build_anchors(symbol, timeframe, db_path)
        selected = split_anchors(anchors, split)
        db = sqlite3.connect(db_path)
        raw = pd.read_sql_query("SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles WHERE symbol=? ORDER BY t_open_ms",
                                db, params=(symbol,))
        db.close()
        for row in selected.itertuples():
            width = {"1m": 60_000, "5m": 300_000, "30m": 1_800_000, "60m": 3_600_000}[timeframe]
            prefix = raw[raw.t_open_ms + width <= int(row.anchor_time_ms)]
            features = build_features(prefix, timeframe)
            name = f"{split}_{symbol}_{timeframe}_{int(row.anchor_time_ms)}.json"
            payload = {"symbol": symbol, "timeframe": timeframe, "anchor_time_ms": int(row.anchor_time_ms),
                       "features": features}
            (output / name).write_text(json.dumps(payload, allow_nan=False, indent=2))
            manifest.append({"file": name, "anchor_time_ms": int(row.anchor_time_ms), "symbol": symbol,
                             "timeframe": timeframe, "input_sha256": features["input_sha256"]})
            count += 1
    (output / f"manifest_{split}_{timeframe}.json").write_text(json.dumps(manifest, indent=2))
    return {"split": split, "count": count, "manifest": str(output / f"manifest_{split}_{timeframe}.json")}
