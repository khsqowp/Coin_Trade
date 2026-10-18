"""마켓 뉴트럴 페어 트레이딩(통계적 차익거래) 근사 — 지금까지 테스트한 전략들과 근본적으로
다른 메커니즘이다: 개별 자산의 방향(오를지 내릴지)을 맞힐 필요 없이, 두 자산의 상대가격
비율이 평균으로 회귀한다는 데만 베팅한다. app/pairs_data.py가 만든 합성 비율 시리즈를 그대로
거래한다.

레짐 변화로 스프레드가 영구적으로 벌어지는("pairs trade blowup") 리스크를 STOP_Z로 방어한다.
"""
from __future__ import annotations

import pandas as pd
from backtesting import Strategy


class PairsMeanReversionStrategy(Strategy):
    LOOKBACK = 60
    ENTRY_Z = 2.0
    EXIT_Z = 0.5
    STOP_Z = 3.5
    POSITION_FRACTION = 0.95
    WARMUP_BARS = 65

    def init(self):
        close = pd.Series(self.data.Close)
        rolling_mean = close.rolling(self.LOOKBACK).mean()
        rolling_std = close.rolling(self.LOOKBACK).std()
        self.zscore = self.I(lambda: ((close - rolling_mean) / rolling_std).values, name="zscore")

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        z = self.zscore[-1]
        if z != z:  # NaN
            return

        if self.position:
            if self.position.is_long and (z >= -self.EXIT_Z or z <= -self.STOP_Z):
                self.position.close()
            elif self.position.is_short and (z <= self.EXIT_Z or z >= self.STOP_Z):
                self.position.close()
            return

        if z <= -self.ENTRY_Z:
            self.buy(size=self.POSITION_FRACTION)
        elif z >= self.ENTRY_Z:
            self.sell(size=self.POSITION_FRACTION)
