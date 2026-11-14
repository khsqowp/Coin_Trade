"""Replays the previous defect on REAL data (run in the sandbox role: no network).
run-main-002/work/strategy.py (original, untouched) vs the same logic with ablation toggles (SMA 200, ATR 14, x3):
1) toggled full strategy == original signals  2) ablation flags atr_trailing_exit as DEAD  3) gate blocks."""
import sys
import types

sys.path.insert(0, "/app/src")
sys.path.insert(0, "/app/tests")
from fixtures_ablation import FIXED, PRIOR_DEFECT  # noqa: E402
from tp import ablation, bt, store  # noqa: E402
from tp.risk import gate_strategy  # noqa: E402

df = store.get_ohlcv("BTC/USDT", "1d")
orig = bt.load_signal_fn("/app/runs/run-main-002/work/strategy.py")(df.copy())


def load(src):
    mod = types.ModuleType("m")
    exec(compile(src.replace("SMA_LENGTH = 50", "SMA_LENGTH = 200"), "fixture", "exec"), mod.__dict__)  # test fixture, our own code
    return mod


for name, src in (("PRIOR_DEFECT(200)", PRIOR_DEFECT), ("FIXED(200)", FIXED)):
    m = load(src)
    full = m.generate_signals(df.copy())
    rep = ablation.run_ablation(df, m.generate_signals, m.RULES, 365)
    print(name, "identical to original run-002 signals:", bool((full == orig).all()),
          "| plain close>SMA200 identical:", bool((full == (df["close"] > df["close"].rolling(200).mean()).astype(float)).all()))
    print("  ", ablation.summarize(rep))
    for r in rep["rules"]:
        print("   rule %-20s %-9s diff_bars=%d trades %d->%d ret %.3f->%.3f" % (
            r["rule"], r["verdict"], r["diff_bars"], r["trades_full"], r["trades_without"], r["return_full"], r["return_without"]))
