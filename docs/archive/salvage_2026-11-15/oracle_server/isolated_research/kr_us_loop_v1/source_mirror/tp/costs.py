"""Cost models, SPOT and USDT-M FUTURES kept separate. Fee, slippage, funding, leverage and maintenance margin are separate parameters.

VERIFIED against Binance official support articles (read 2026-10-25 via the support-centre article API
https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode=<code>, which serves the pages below):
  * Futures fee structure  https://www.binance.com/en/support/faq/detail/360033544231  (articleCode 360033544231)
      worked example for a "Regular User": USDS-M maker 0.02%, taker 0.05%; "Users will receive a 10% discount on standard trading
      fees when they use BNB ... for USDS-M Futures". The article calls these rates "hypothetical": the owner's real tier (VIP level,
      fee-rate table) may differ -> all numbers are parameters and the sensitivity grid varies them.
  * Spot + BNB discount    https://www.binance.com/en/support/faq/detail/115000583311  (articleCode 115000583311)
      regular spot fee 0.1% (worked example: 10 ETH * 0.1%); with BNB deduction 0.075% (25% discount); "up to 10% on Futures".
  * Liquidation protocol   https://www.binance.com/en/support/faq/detail/360033525271 : liquidation is triggered on MARK price when
      collateral (initial + realised + unrealised PnL) < maintenance margin; "Smart Liquidation" tries a partial reduction first;
      smaller positions can be fully liquidated; Futures Insurance Fund takes over bankrupt positions.
  * Leverage and margin    https://www.binance.com/en/support/faq/detail/360033162192 : MM = notional * MM rate - maintenance amount, bracketed
      by notional; the bracket TABLE itself is a JS page that could not be read here -> maintenance margin rate is a PARAMETER
      (default 0.5%, sensitivity 0.4%/1.0%); leverage >20x is not offered to accounts younger than 30 days.
  * Funding                https://www.binance.com/en/support/faq/detail/360033525031 : settled every 8h at 00:00/08:00/16:00 UTC (default),
      payment = position notional (mark price) * funding rate; longs pay when the rate is positive; Binance charges no fee on funding.
      Real funding history is applied from public GET /fapi/v1/fundingRate (collected in deriv.sqlite).
  * exchangeInfo (public) https://fapi.binance.com/fapi/v1/exchangeInfo reports liquidationFee=0.0125 for BTCUSDT/ETHUSDT (clearance fee
      rate); our model conservatively treats a liquidation as loss of the whole position margin, which already exceeds it.
SLIPPAGE has no official number: it is an assumption (default 0.02% per side for BTC/ETH market orders at next-bar open, scenarios
0.01% / 0.05%), optionally scaled by the executing bar's range (slip_range_frac)."""
from dataclasses import dataclass, replace

SOURCES = {
    "futures_fee": "https://www.binance.com/en/support/faq/detail/360033544231",
    "spot_bnb": "https://www.binance.com/en/support/faq/detail/115000583311",
    "liquidation": "https://www.binance.com/en/support/faq/detail/360033525271",
    "margin": "https://www.binance.com/en/support/faq/detail/360033162192",
    "funding": "https://www.binance.com/en/support/faq/detail/360033525031",
    "exchange_info": "https://fapi.binance.com/fapi/v1/exchangeInfo",
}
FEE_TABLE = {   # Regular-user rates from the worked examples in the official articles above
    "spot": {"maker": 0.0010, "taker": 0.0010, "bnb_discount": 0.25},
    "futures": {"maker": 0.0002, "taker": 0.0005, "bnb_discount": 0.10},
}


@dataclass(frozen=True)
class CostModel:
    market: str = "futures"          # 'spot' | 'futures'
    maker: float = 0.0002
    taker: float = 0.0005
    taker_share: float = 1.0         # 1.0 = every fill is a market (taker) order; 0.0 = every fill rests as maker
    bnb: bool = False
    bnb_discount: float = 0.10
    slip: float = 0.0002             # per side, adverse
    slip_range_frac: float = 0.0     # extra slippage = frac * (high-low)/open of the executing bar
    mmr: float = 0.005               # maintenance margin rate (futures)
    name: str = "base"

    @property
    def fee_side(self):
        f = self.taker_share * self.taker + (1.0 - self.taker_share) * self.maker
        return f * (1.0 - (self.bnb_discount if self.bnb else 0.0))

    @property
    def side_cost(self):
        return self.fee_side + self.slip


def make(market="futures", **kw):
    t = FEE_TABLE[market]
    base = CostModel(market=market, maker=t["maker"], taker=t["taker"], bnb_discount=t["bnb_discount"], slip=0.0002)
    return replace(base, **kw)


def scenarios(market="futures"):
    """Sensitivity grid (maker/taker mix x BNB discount x slippage). 'base' = taker, no BNB, 0.02% slippage (pre-registered primary)."""
    out = {}
    for mix_name, share in (("taker", 1.0), ("half_maker", 0.5), ("maker", 0.0)):
        for bnb in (False, True):
            for slip in (0.0001, 0.0002, 0.0005):
                n = "%s|%s|slip%.2f%%" % (mix_name, "bnb" if bnb else "nobnb", slip * 100)
                out[n] = make(market, taker_share=share, bnb=bnb, slip=slip, name=n)
    return out


BASE_FUT = make("futures", name="base_futures")      # primary, pre-registered
BASE_SPOT = make("spot", name="base_spot")
