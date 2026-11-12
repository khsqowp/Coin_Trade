import numpy as np
import pandas as pd

from app.aw_regime import apply_hysteresis


def test_score_threshold_hysteresis_and_crash_override():
    f = pd.DataFrame({"raw": ["BULL", "BULL", "BULL", "RANGE", "BEAR", "BEAR", "BEAR"],
                      "crash": [False, False, False, False, True, False, False],
                      "crash_release": [False] * 7})
    out = apply_hysteresis(f, 3)
    assert out.regime.tolist() == ["RANGE", "RANGE", "BULL", "BULL", "BEAR", "BEAR", "BEAR"]


def test_crash_releases_only_after_nonnegative_14d_return():
    f = pd.DataFrame({"raw": ["BEAR", "BEAR", "BULL", "BULL", "BULL"],
                      "crash": [True, False, False, False, False],
                      "crash_release": [False, False, True, False, False]})
    assert apply_hysteresis(f, 2).regime.tolist() == ["BEAR", "BEAR", "BULL", "BULL", "BULL"]


def test_missing_macro_and_breadth_do_not_blank_score():
    from app.aw_regime import score_regime
    dates = pd.date_range('2010-01-01', periods=260)
    close = pd.DataFrame({'IDX': np.linspace(100, 160, 260), 'SEC': np.linspace(80, 120, 260),
                          'MAC': np.r_[np.repeat(np.nan, 80), np.linspace(100, 120, 180)]}, index=dates)
    out = score_regime(close, 'KR', 'IDX', ['SEC'], 'MAC')
    assert out.score.iloc[-1] == out[['T','S','M','B','X']].sum(axis=1).iloc[-1]
    assert out.score.iloc[-1] == out.score.iloc[-1]
    assert out.score.isna().sum() < 200


def test_crash_release_uses_same_day_raw_regime():
    f = pd.DataFrame({'raw':['BEAR','BULL','RANGE'], 'crash':[True,False,False],
                      'crash_release':[False,True,False]})
    assert apply_hysteresis(f, 5).regime.tolist() == ['BEAR','BULL','BULL']
