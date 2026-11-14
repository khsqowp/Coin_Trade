"""Cost models. All figures are fractions of notional. mult scales every cost component (2x sensitivity).

KR sell-side tax (증권거래세 + 농어촌특별세), effective 2026-01-01:
  KOSPI : 증권거래세 0.05% + 농특세 0.15% = 0.20%
  KOSDAQ: 증권거래세 0.20% (농특세 none)  = 0.20%
Source: 증권거래세법 시행령 제5조 (탄력세율; 2025 세제개편 -> 2026 rate step 0.15% -> 0.20%); schedule
(2024 0.18%, 2025 0.15%, 2026 0.20%) cross-checked 2026-11-13 on namu.wiki/w/증권거래세 table because
law.go.kr/KRX pages are JS-rendered and not fetchable from the server. Re-verify against law.go.kr / NTS.
Plan sensitivity: also test 0.18% (the 2024 level).

KR commission: 0.015%/side (KRX incl. fees). Toss Prime (5,900 KRW/month): commission incl. 유관기관 fees
refunded up to 1e8 KRW cumulative monthly turnover; above the cap 0.015%/side again.
  Scenario A = Prime, B = no Prime.
US: Toss 0.1%/side commission; SEC Sec.31 fee on sells (rate varies by fiscal year, FY2024 $27.80/M = 0.00278%;
kept as conservative default); FX spread ~0.1% round trip (with 우대); slippage 0.05%/side.
KR capital-gains tax on US stocks (22% above 2.5M KRW/yr) is NOT modelled.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

KR_SELL_TAX_2026 = 0.0020
KR_SELL_TAX_2024 = 0.0018
KR_SELL_TAX_SENS = (0.0018, 0.0020)
KR_COMMISSION = 0.00015
PRIME_FEE_MONTH = 5900.0
PRIME_CAP = 1e8


@dataclass(frozen=True)
class KRCost:
    scenario: str = "B"                 # "A" Prime, "B" no Prime
    sell_tax: float = KR_SELL_TAX_2026
    commission: float = KR_COMMISSION
    slip_liquid: float = 0.0005         # per side, 20d traded value >= liquid_threshold
    slip_illiquid: float = 0.0010
    liquid_threshold: float = 2e10
    mult: float = 1.0

    def with_(self, **kw) -> "KRCost":
        d = dict(self.__dict__); d.update(kw); return KRCost(**d)

    def slip(self, value20):
        v = np.asarray(value20, dtype=float)
        return np.where(v >= self.liquid_threshold, self.slip_liquid, self.slip_illiquid)

    def roundtrip(self, value20):
        """Round-trip fraction per trade (array shaped like value20). NaN value20 -> illiquid slippage."""
        v = np.nan_to_num(np.asarray(value20, dtype=float), nan=0.0)
        comm = 0.0 if self.scenario == "A" else 2 * self.commission   # A: within monthly cap
        return self.mult * (self.sell_tax + comm + 2 * self.slip(v))

    def fixed_monthly_return(self, capital: float) -> float:
        """Prime subscription as fraction of capital per month (A only)."""
        return self.mult * PRIME_FEE_MONTH / capital if self.scenario == "A" else 0.0

    def excess_commission(self, monthly_turnover: float) -> float:
        """Extra commission (KRW) for A when monthly turnover (buy+sell notional) exceeds the cap."""
        if self.scenario != "A":
            return 0.0
        return max(0.0, monthly_turnover - PRIME_CAP) * self.commission * self.mult


@dataclass(frozen=True)
class USCost:
    commission: float = 0.001
    sec_sell: float = 0.0000278
    fx_roundtrip: float = 0.001
    slip: float = 0.0005
    mult: float = 1.0

    def with_(self, **kw) -> "USCost":
        d = dict(self.__dict__); d.update(kw); return USCost(**d)

    def roundtrip(self, value20=None):
        rt = 2 * self.commission + self.sec_sell + self.fx_roundtrip + 2 * self.slip
        r = self.mult * rt
        return r if value20 is None else np.full(np.shape(value20), r)

    def fixed_monthly_return(self, capital: float) -> float:
        return 0.0


def break_even_cost(gross_mean: float) -> float:
    """Max round-trip cost (fraction) at which mean trade return = 0, i.e. the gross mean."""
    return float(gross_mean)
