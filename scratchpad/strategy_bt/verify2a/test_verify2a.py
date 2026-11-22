import json, numpy as np, pandas as pd, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from lib import load_summary, CANDS, candidate_row, run_row, total_pct, delay_signals, SYMS, HERE
import a2345, a1_stats

def test_plugin_rerun_matches_frozen_summary():
    rows = load_summary()
    for sid in CANDS:
        tf, p, r = candidate_row(sid, rows)
        res, _ = run_row(sid, tf, p)
        assert abs(total_pct(res) - float(r["test_return"])) < 1e-6

def test_delay_shifts_signals():
    s = pd.DataFrame({"long_entry": [True, False, False], "short_entry": [False] * 3, "long_exit": [False] * 3, "short_exit": [False] * 3})
    assert list(delay_signals(s, 1).long_entry) == [False, True, False]

def test_a5_equals_pooled_sum_when_cap_never_binds():
    tf, p, r = candidate_row("btc-bollinger-37-16")
    res, _ = run_row("btc-bollinger-37-16", tf, p)
    out = a2345.a5("btc-bollinger-37-16", tf, p, res)
    assert out["trades_skipped_capital"] == 0 and abs(out["port_return"] - total_pct(res)) < 1e-6

def test_stationary_bootstrap_indices_in_range():
    idx = a1_stats.stationary_idx(50, 20, 5, np.random.default_rng(0))
    assert idx.min() >= 0 and idx.max() < 50

def test_funding_files_present_and_sane():
    for s in SYMS:
        d = pd.read_csv(HERE / "funding" / f"{s}.csv"); assert len(d) > 1000 and d.fundingRate.abs().max() < 0.05
