"""Runs INSIDE the freqtrade image (no network, read-only mounts): loads the exported candidate via Freqtrade's own
strategy resolver and compares its entry/exit columns with the pipeline's signals."""
import sys
import pathlib
import pandas as pd
cls = open("/selftest/class.txt").read().strip()
from freqtrade.resolvers import StrategyResolver
cfg = {"strategy": cls, "strategy_path": "/selftest/strategies", "user_data_dir": pathlib.Path("/tmp/ud"), "dry_run": True,
       "timeframe": "1d", "stake_currency": "USDT", "runmode": "dry_run", "datadir": "/tmp/ud/data",
       "exchange": {"name": "binance", "pair_whitelist": ["BTC/USDT"]}, "stake_amount": 100, "max_open_trades": 1}
strat = StrategyResolver.load_strategy(cfg)
print("loaded:", type(strat).__name__, "timeframe", strat.timeframe, "can_short", strat.can_short, "stoploss", strat.stoploss)
df = pd.read_csv("/selftest/btc.csv", parse_dates=["date"])
df["date"] = pd.to_datetime(df["date"], utc=True)
out = strat.populate_indicators(df.copy(), {"pair": "BTC/USDT"})
out = strat.populate_entry_trend(out, {"pair": "BTC/USDT"})
out = strat.populate_exit_trend(out, {"pair": "BTC/USDT"})
sys.path.insert(0, "/selftest/strategies")
import importlib
mod = importlib.import_module(cls)
ref = mod.generate_signals(df.set_index("date")[["open", "high", "low", "close", "volume"]])
enter = out["enter_long"].fillna(0).astype(int).values
exit_ = out["exit_long"].fillna(0).astype(int).values
print("rows", len(out), "| enter==signal:", bool((enter == (ref.values >= 1)).all()), "| exit==flat:", bool((exit_ == (ref.values <= 0)).all()))
print("entries", int(enter.sum()), "exits", int(exit_.sum()))
