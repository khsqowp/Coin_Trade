import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import momentum_rotation_exec as ex

PRICE = 10.0


class Fake:
    def __init__(self, avail=1000.0, min_cost=5, fail=()):
        self.pos = {}
        self.orders = []
        self.avail = avail
        self.min_cost = min_cost
        self.fail = set(fail)

    def add(self, base, side, notional):
        self.pos[base] = dict(symbol=f"{base}/USDT:USDT", contracts=notional / PRICE, side=side,
                              notional=notional, entryPrice=PRICE, markPrice=PRICE, unrealizedPnl=0.0)

    def market(self, symbol):
        return {"limits": {"cost": {"min": self.min_cost}, "amount": {"min": 0}}}

    def set_leverage(self, lev, symbol):
        pass

    def amount_to_precision(self, symbol, amount):
        return f"{amount:.4f}"

    def fetch_balance(self):
        return {"info": {"availableBalance": self.avail}}

    def fetch_positions(self):
        return list(self.pos.values())

    def _order(self, symbol, amount, side, params):
        base = symbol.split("/")[0]
        if base in self.fail:
            raise RuntimeError("boom")
        reduce = bool((params or {}).get("reduceOnly"))
        self.orders.append((base, side, amount, reduce))
        p = self.pos[base] if base in self.pos else None
        signed = amount if side == "buy" else -amount
        cur = 0.0 if p is None else (p["contracts"] if p["side"] == "long" else -p["contracts"])
        new = cur + signed
        if reduce and cur * new < 0:
            raise AssertionError("flip")
        if abs(new) < 1e-9:
            self.pos.pop(base, None)
            return
        self.pos[base] = dict(symbol=symbol, contracts=abs(new), side="long" if new > 0 else "short",
                              notional=abs(new) * PRICE, entryPrice=PRICE, markPrice=PRICE, unrealizedPnl=0.0)

    def create_market_buy_order(self, symbol, amount, params=None):
        self._order(symbol, amount, "buy", params)

    def create_market_sell_order(self, symbol, amount, params=None):
        self._order(symbol, amount, "sell", params)


def run(c, targets, notional=30.0, **kw):
    prices = {b: PRICE for b in targets}
    return ex.apply_targets(c, prices, targets, notional, 4, lambda m: None, resize_tolerance=0.15, **kw)


def test_topup_long_and_short():
    c = Fake()
    c.add("A", "long", 16)
    c.add("B", "short", 16)
    r = run(c, {"A": "long", "B": "short"})
    assert len(r["resized"]) == 2
    assert ("A", "buy", 1.4, False) in c.orders
    assert ("B", "sell", 1.4, False) in c.orders
    assert abs(c.pos["A"]["notional"] - 30) < 1e-6


def test_trim_reduce_only_no_flip():
    c = Fake()
    c.add("A", "long", 60)
    c.add("B", "short", 60)
    r = run(c, {"A": "long", "B": "short"})
    assert ("A", "sell", 3.0, True) in c.orders
    assert ("B", "buy", 3.0, True) in c.orders
    assert c.pos["A"]["side"] == "long" and abs(c.pos["A"]["notional"] - 30) < 1e-6
    assert not r["errors"]


def test_within_tolerance_noop():
    c = Fake()
    c.add("A", "long", 33)
    c.add("B", "short", 26)
    assert run(c, {"A": "long", "B": "short"})["resized"] == []
    assert c.orders == []


def test_below_min_skip():
    c = Fake(min_cost=50)
    c.add("A", "long", 16)
    r = run(c, {"A": "long"})
    assert c.orders == [] and r["skipped"]


def test_insufficient_margin_skip():
    c = Fake(avail=2.0)  # need 14/4=3.5 > 1.8
    c.add("A", "long", 16)
    r = run(c, {"A": "long"})
    assert c.orders == [] and r["resized"] == [] and r["skipped"]


def test_error_isolated():
    c = Fake(fail={"A"})
    c.add("A", "long", 16)
    c.add("B", "long", 16)
    r = run(c, {"A": "long", "B": "long"})
    assert any("A 리사이즈" in e for e in r["errors"])
    assert len(r["resized"]) == 1 and abs(c.pos["B"]["notional"] - 30) < 1e-6


def test_second_run_noop_and_order_sequence():
    c = Fake()
    c.add("A", "long", 16)
    c.add("T", "long", 80)
    c.add("X", "short", 30)
    run(c, {"A": "long", "T": "long", "N": "short"})
    seq = [(o[0], o[3]) for o in c.orders]
    # close X, trim T, open N, top-up A last
    assert [s[0] for s in seq] == ["X", "T", "N", "A"]
    n = len(c.orders)
    r = run(c, {"A": "long", "T": "long", "N": "short"})
    assert len(c.orders) == n and r["resized"] == []
