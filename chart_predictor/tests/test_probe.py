import numpy as np
import pandas as pd
import pytest

from chart_predictor.features import FeatureStream, _digest
from chart_predictor.probe import (_context_at, _context_series, _eval_split, _market_stats,
    _feature_for_anchor, _feature_row, _fit_models)
from chart_predictor.p3a import _PrefixDigester


def _candles(n=180):
    rng = np.random.default_rng(19)
    close = 100 + np.cumsum(rng.normal(0, .15, n))
    return pd.DataFrame({"t_open_ms": np.arange(n) * 60_000, "o": close,
        "h": close + .2, "l": close - .2, "c": close,
        "v": rng.uniform(1, 5, n), "quote_v": rng.uniform(10, 20, n), "trades": np.ones(n)})


def test_builder_features_do_not_change_when_future_is_mutated():
    full = _candles()
    changed = full.copy()
    changed.loc[100:, ["o", "h", "l", "c", "v", "quote_v"]] *= 5
    digester_a, digester_b = _PrefixDigester(full), _PrefixDigester(changed)
    a = _feature_for_anchor(full, 99, "1m", digester_a, FeatureStream(full))
    b = _feature_for_anchor(changed, 99, "1m", digester_b, FeatureStream(changed))
    assert a == b
    assert a["input_sha256"] == _digest(full.iloc[:100].reset_index(drop=True))
    assert "swing_counts" in a["levels"]
    assert isinstance(_feature_row(a)["rsi14"], float)


def test_market_context_is_prefix_invariant_after_future_mutation():
    original = _candles(180)
    changed = original.copy()
    changed.loc[100:, ["o", "h", "l", "c", "v", "quote_v"]] *= 7
    before = {name: _context_series(original) for name in ("AAA", "BBB", "BTCUSDT", "ETHUSDT")}
    after = {name: _context_series(changed) for name in before}
    stats_a=_market_stats(before,["AAA","BBB"],60_000); stats_b=_market_stats(after,["AAA","BBB"],60_000)
    assert _context_at("AAA", 94, before, stats_a) == _context_at("AAA", 94, after, stats_b)


def test_streaming_snapshots_match_full_builder():
    from chart_predictor.features import build_features
    frame = _candles(220)
    stream, digest = FeatureStream(frame), _PrefixDigester(frame)
    for pos in (80, 99, 140, 219):
        prefix = frame.iloc[:pos + 1].reset_index(drop=True)
        actual = _feature_for_anchor(frame, pos, "1m", digest, stream)
        expected = build_features(prefix, "1m")
        assert actual == expected


def test_models_detect_planted_signal_and_stay_near_chance_on_noise():
    pytest.importorskip("sklearn")
    from chart_predictor.p4c import _fit_models as p4c_fit
    rng = np.random.default_rng(7)
    x = rng.normal(size=(1200, 6))
    y = (x[:, 0] + .5 * x[:, 1] > 0).astype(int)
    fit = p4c_fit(x[:800], y[:800], x[800:], 17)
    assert all(np.mean((p >= .5) == y[800:]) > .75 for _, p in fit.values())
    noise = rng.normal(size=(1200, 6)); labels = rng.integers(0, 2, len(noise))
    fit_noise = p4c_fit(noise[:800], labels[:800], noise[800:], 17)
    assert all(abs(np.mean((p >= .5) == labels[800:]) - .5) < .10 for _, p in fit_noise.values())


def test_temporal_evaluation_accepts_horizon_metadata(monkeypatch):
    def fake_fit(x_train, y_train, x_test, seed):
        probability = np.linspace(.35, .65, len(x_test))
        return {"stub": (None, probability)}
    monkeypatch.setattr("chart_predictor.probe._fit_models", fake_fit)
    times = np.arange(40, dtype=np.int64) * 20 * 60_000
    meta = (np.array([f"S{i % 4}" for i in range(40)]), times, [0.0] * 40, ["x"], 20)
    result = _eval_split(meta, np.arange(40).reshape(-1, 1), np.arange(40) % 2, "temporal", 9)
    assert result["n_train"] > 0 and result["n_test"] > 0
    assert "stub" in result["models"]


def test_double_holdout_separates_late_symbols_and_time(monkeypatch):
    def fake_fit(x_train, y_train, x_test, seed):
        return {"stub": (None, np.linspace(.3, .7, len(x_test)))}
    monkeypatch.setattr("chart_predictor.probe._fit_models", fake_fit)
    symbols=np.repeat([f"S{i:02d}" for i in range(10)],20)
    times=np.tile(np.arange(20,dtype=np.int64)*60_000,10)
    meta=(symbols,times,[0.0]*len(times),["x"],2)
    result=_eval_split(meta,np.arange(len(times)).reshape(-1,1),np.arange(len(times))%2,"double_holdout",3)
    assert result["n_train"]==98 and result["n_test"]==12


def test_p4c_bootstrap_holm_and_expanding_purge():
    from chart_predictor.p4c import _cluster_bootstrap, _fast_weighted_auc, _fold_masks, _holm, _expansion_target
    assert _holm([.01, .04, .03]) == pytest.approx([.03, .06, .06])
    times=np.repeat(np.arange(100,dtype=np.int64)*60_000,2)
    symbols=np.tile(["A", "B"],100)
    train,test=_fold_masks(times,0,"temporal",symbols,set(),5*60_000)
    assert train.any() and test.any() and times[train].max() < times[test].min()-5*60_000
    held={"B"}; train_d,test_d=_fold_masks(times,0,"double_holdout",symbols,held,5*60_000)
    assert train_d.any() and test_d.any() and set(symbols[test_d]) == held and not (set(symbols[train_d]) & held)
    y=np.array([0,1,0,1]); p=np.array([.1,.9,.2,.8]); days=np.array([1,1,2,2])
    boot=_cluster_bootstrap(y,p,days,.5,4,n=20)
    assert boot["independent_days"] == 2 and boot["auc_ci95"] == [1.0,1.0]
    assert _fast_weighted_auc(y, np.array([.2,.2,.8,.8]), np.ones(4)) == pytest.approx(.5)
    train_mask=np.arange(10)<6; test_mask=~train_mask
    train_y,test_y,threshold=_expansion_target(np.arange(10,dtype=float),train_mask,test_mask)
    assert threshold == 2.5 and train_y.mean() == pytest.approx(.5) and np.all(test_y == 1)


def test_p4c_strategy_stop_cost_and_mae_accounting():
    from chart_predictor.p4c import _strategy_trade, _strategy_summary
    frame=pd.DataFrame({"o":[100,100,100,100],"h":[101,101,101,101],
        "l":[99,99,95,99],"c":[100,100,99,100]})
    trade=_strategy_trade(frame,0,1,2,2)
    assert trade["reason"] == "stop"
    assert trade["net"] == pytest.approx(-.0414)
    summary=_strategy_summary([trade])
    assert summary["n_trades"] == 1 and summary["max_adverse_excursion"] == pytest.approx(.05)
