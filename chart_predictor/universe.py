"""Select the highest-volume crypto USDT perpetual contracts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import requests

BASE_URL = "https://fapi.binance.com"
DATA_DIR = Path(__file__).parent / "data"


def eligible_symbols(exchange_info: dict) -> set[str]:
    """Return symbols satisfying the P1 crypto USDT-M contract rules."""
    return {item["symbol"] for item in exchange_info.get("symbols", [])
            if item.get("contractType") == "PERPETUAL"
            and item.get("quoteAsset") == "USDT" and item.get("status") == "TRADING"
            and item.get("underlyingType") == "COIN"}


def select_universe(exchange_info: dict, tickers: list[dict], top_n: int = 100) -> list[dict]:
    """Rank eligible symbols by 24h quote volume, descending."""
    eligible = eligible_symbols(exchange_info)
    rows = [{"symbol": row["symbol"], "quoteVolume": float(row["quoteVolume"])}
            for row in tickers if row.get("symbol") in eligible]
    return sorted(rows, key=lambda row: row["quoteVolume"], reverse=True)[:top_n]


def fetch_universe(top_n: int = 100, session=requests) -> list[dict]:
    """Fetch public contract metadata and ticker volume, then persist selection."""
    info = session.get(f"{BASE_URL}/fapi/v1/exchangeInfo", timeout=20).json()
    tickers = session.get(f"{BASE_URL}/fapi/v1/ticker/24hr", timeout=20).json()
    selected = select_universe(info, tickers, top_n)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc)
    payload = {"timestamp": stamp.isoformat(), "symbols": selected}
    (DATA_DIR / f"universe_{stamp:%Y%m%d}.json").write_text(json.dumps(payload, indent=2))
    return selected
