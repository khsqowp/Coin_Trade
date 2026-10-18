"""app/broad_strategies.py의 19개 지표 함수가 합성 OHLCV에서 예외 없이 도는지만 빠르게 확인
(실제 KIS API 호출 없음, pandas_ta 버전별 컬럼명 차이 조기 발견용)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app import broad_strategies as bs

rng = np.random.default_rng(42)
n = 300
close = 100 + np.cumsum(rng.normal(0, 1, n))
high = close + rng.uniform(0, 2, n)
low = close - rng.uniform(0, 2, n)
open_ = close + rng.normal(0, 0.5, n)
volume = rng.uniform(1000, 5000, n)
frame = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
                      index=pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC"))

indicator_fns = [name for name in dir(bs) if name.startswith("add_")]
print(f"{len(indicator_fns)}개 지표 함수 검사")
failed = []
for name in indicator_fns:
    fn = getattr(bs, name)
    try:
        out = fn(frame)
        assert isinstance(out, pd.DataFrame)
        print(f"  OK {name} -> {[c for c in out.columns if c not in frame.columns]}")
    except Exception as exc:  # noqa: BLE001
        failed.append((name, exc))
        print(f"  FAIL {name}: {exc}")

print(f"\n{len(indicator_fns) - len(failed)}/{len(indicator_fns)} 통과")
if failed:
    raise SystemExit(1)
