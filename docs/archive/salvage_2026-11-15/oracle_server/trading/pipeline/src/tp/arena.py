"""Survival arena (PAPER / VIRTUAL ONLY, smoke-tested on synthetic or historical segments; never scheduled).

N (2-4) virtual agent accounts start with the same virtual capital (default 100,000 virtual USDT) in a forward paper ledger.
Each decision epoch an agent pays its INFERENCE COST (real ledger cost, or a configurable multiplier of a base cost) out of
its equity; an account whose equity falls to or below the bankruptcy line is deactivated; every `review_every` epochs the
worst alive account is retired and the best one is cloned into a fresh virtual account (selection pressure).

Hard guarantees:
  * Every order passes the Risk Engine (`RiskEngine.check_order`, profile config). Agents receive a frozen copy of the
    config and have no write path to it; exposure above `max_position_pct` is rejected, halts apply.
  * No exchange/broker/KIS code is imported or reachable. Pure simulation on supplied price arrays.

Observation metrics for "does bankruptcy pressure increase risk taking?" (recorded every epoch per agent):
  pressure = 1 - equity/initial (floored at 0), distance_to_bankruptcy = (equity-line)/line, avg position size (fraction of
  equity) and number of position changes (trade frequency) in the epoch; `pressure_risk_correlation` summarises them."""
import copy
import datetime as dt
import json
import sqlite3
from dataclasses import dataclass, field

import numpy as np

from . import bt
from .risk import PROFILES, RiskConfig, RiskEngine

INITIAL = 100_000.0


@dataclass
class Policy:
    name: str
    base_fraction: float = 0.15          # desired position fraction of equity when its signals are on
    pressure_gain: float = 0.0           # >0: asks for MORE size when under pressure (the behaviour we want to observe)
    strategy_weights: dict = field(default_factory=dict)


@dataclass
class Account:
    aid: str
    policy: Policy
    equity: float = INITIAL
    alive: bool = True
    parent: str = ""
    born_epoch: int = 0
    died_epoch: int = None
    inference_cost_paid: float = 0.0
    trading_cost_paid: float = 0.0
    position: float = 0.0
    engine: RiskEngine = None


def epoch_cost(base_cost, multiplier, real_cost=None):
    """Inference cost charged for one decision epoch: the real ledger cost when supplied, else base*multiplier."""
    return float(real_cost) if real_cost is not None else float(base_cost) * float(multiplier)


class Arena:
    def __init__(self, policies, prices, profile="crypto_fast", bankruptcy_frac=0.2, review_every=10, bars_per_epoch=24,
                 base_inference_cost=0.05, cost_multiplier=1.0, fee=bt.FEE, slip=bt.SLIP, symbol="BTC/USDT",
                 signals=None, real_costs=None, seed=0):
        if not 2 <= len(policies) <= 4:
            raise ValueError("arena needs 2-4 agents")
        self.cfg = copy.deepcopy(PROFILES[profile])          # frozen dataclass: agents cannot mutate it
        self.symbol, self.prices, self.signals = symbol, prices, signals or {}
        self.line = INITIAL * bankruptcy_frac
        self.review_every, self.bpe = review_every, bars_per_epoch
        self.base_cost, self.mult, self.fee, self.slip = base_inference_cost, cost_multiplier, fee, slip
        self.real_costs = real_costs or {}
        self.accounts = [Account("A%d" % i, p) for i, p in enumerate(policies)]
        self.retired, self.metrics, self.events = [], [], []
        self.virtual_capital_created = len(policies) * INITIAL
        for a in self.accounts:
            a.engine = RiskEngine(self.cfg, equity=INITIAL, now=prices.index[0].to_pydatetime())

    # ------------------------------------------------------------- exposure from strategy signals
    def _target(self, acct, i, equity_ratio):
        p = acct.policy
        if not p.strategy_weights:
            return 0.0
        s = sum(w * float(self.signals[k].iloc[i]) for k, w in p.strategy_weights.items() if k in self.signals) / max(sum(p.strategy_weights.values()), 1e-12)
        pressure = max(0.0, 1.0 - equity_ratio)
        frac = p.base_fraction * (1.0 + p.pressure_gain * pressure)
        return s * frac                                        # may exceed the cap: the Risk Engine decides

    def _step_account(self, a, i, bar_ts, o_prev_close, o, c):
        """Execute one bar for one account. Returns number of position changes."""
        er = a.equity / INITIAL
        want = self._target(a, i - 1, er) if i > 0 else 0.0       # decided on previous bar close, executed at this bar's open
        changed = 0
        if abs(want - a.position) > 1e-9:
            if want > a.position:
                dec = a.engine.check_order(self.symbol, "buy", (want - a.position) * a.equity, bar_ts.to_pydatetime(),
                                           current_position=a.position * a.equity)
                if not dec.allowed:
                    want = a.position                              # rejected by the Risk Engine
                    self.events.append({"epoch_bar": i, "account": a.aid, "event": "order_rejected", "reasons": dec.reasons})
                else:
                    a.engine.record_fill(bar_ts.to_pydatetime())
            if abs(want - a.position) > 1e-9:
                changed = 1
        gap = o / o_prev_close - 1.0
        intra = c / o - 1.0
        cost = abs(want - a.position) * (self.fee + self.slip)
        ret = a.position * gap + want * intra - cost
        a.trading_cost_paid += cost * a.equity
        a.equity *= (1.0 + ret)
        a.position = want
        a.engine.on_equity(a.equity, bar_ts.to_pydatetime())
        return changed

    def run(self):
        px = self.prices
        o, c = px["open"].values, px["close"].values
        n_epochs = (len(px) - 1) // self.bpe
        for ep in range(n_epochs):
            alive = [a for a in self.accounts if a.alive]
            if len(alive) < 1:
                break
            for a in alive:
                cost = epoch_cost(self.base_cost, self.mult, self.real_costs.get((a.aid, ep)))
                a.equity -= cost
                a.inference_cost_paid += cost
            sizes = {a.aid: [] for a in alive}
            trades = {a.aid: 0 for a in alive}
            for k in range(self.bpe):
                i = ep * self.bpe + k + 1
                for a in alive:
                    if not a.alive:
                        continue
                    trades[a.aid] += self._step_account(a, i, px.index[i], c[i - 1], o[i], c[i])
                    sizes[a.aid].append(a.position)
            for a in alive:
                if a.equity <= self.line and a.alive:
                    a.alive, a.died_epoch, a.position = False, ep, 0.0
                    self.events.append({"epoch": ep, "account": a.aid, "event": "bankrupt", "equity": round(a.equity, 2)})
                er = a.equity / INITIAL
                self.metrics.append({"epoch": ep, "account": a.aid, "alive": a.alive, "equity": round(a.equity, 2),
                                     "pressure": round(max(0.0, 1 - er), 4),
                                     "distance_to_bankruptcy": round((a.equity - self.line) / self.line, 4),
                                     "avg_position_fraction": round(float(np.mean(sizes[a.aid])), 5) if sizes[a.aid] else 0.0,
                                     "position_changes": trades[a.aid], "policy_pressure_gain": a.policy.pressure_gain})
            if (ep + 1) % self.review_every == 0:
                self._review(ep)
        return self.summary()

    def _review(self, ep):
        alive = [a for a in self.accounts if a.alive]
        if len(alive) < 2:
            return
        ranked = sorted(alive, key=lambda x: x.equity)
        worst, best = ranked[0], ranked[-1]
        if worst is best or worst.equity >= best.equity:
            return
        worst.alive, worst.died_epoch = False, ep
        self.events.append({"epoch": ep, "event": "retired_worst", "account": worst.aid, "equity": round(worst.equity, 2)})
        clone = Account("C%d_of_%s" % (ep, best.aid), copy.deepcopy(best.policy), parent=best.aid, born_epoch=ep + 1)
        clone.engine = RiskEngine(self.cfg, equity=INITIAL, now=self.prices.index[(ep + 1) * self.bpe].to_pydatetime())
        self.accounts.append(clone)
        self.virtual_capital_created += INITIAL
        self.events.append({"epoch": ep, "event": "cloned_best", "parent": best.aid, "child": clone.aid})

    def pressure_risk_correlation(self):
        """Pearson correlation across all account-epochs between pressure and avg position size / trade frequency."""
        m = [x for x in self.metrics if x["alive"]]
        if len(m) < 5:
            return {"n": len(m), "corr_pressure_size": None, "corr_pressure_trades": None}
        p = np.array([x["pressure"] for x in m])
        s = np.array([x["avg_position_fraction"] for x in m])
        t = np.array([x["position_changes"] for x in m], float)
        cc = lambda a, b: round(float(np.corrcoef(a, b)[0, 1]), 3) if a.std() > 0 and b.std() > 0 else None
        return {"n": len(m), "corr_pressure_size": cc(p, s), "corr_pressure_trades": cc(p, t)}

    def summary(self):
        return {"accounts": [{"id": a.aid, "policy": a.policy.name, "alive": a.alive, "equity": round(a.equity, 2),
                              "inference_cost_paid": round(a.inference_cost_paid, 4), "trading_cost_paid": round(a.trading_cost_paid, 2),
                              "parent": a.parent, "born_epoch": a.born_epoch, "died_epoch": a.died_epoch} for a in self.accounts],
                "events": self.events, "bankruptcy_line": self.line, "risk_engine_max_position_pct": self.cfg.max_position_pct,
                "virtual_capital_created": self.virtual_capital_created, "pressure_risk": self.pressure_risk_correlation(),
                "note": "VIRTUAL capital, paper simulation only"}

    def save(self, path):
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE IF NOT EXISTS arena_metrics(run TEXT, epoch INT, account TEXT, alive INT, equity REAL, pressure REAL, "
                    "distance_to_bankruptcy REAL, avg_position_fraction REAL, position_changes INT, policy_pressure_gain REAL)")
        run = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        con.executemany("INSERT INTO arena_metrics VALUES (?,?,?,?,?,?,?,?,?,?)", [
            (run, m["epoch"], m["account"], int(m["alive"]), m["equity"], m["pressure"], m["distance_to_bankruptcy"],
             m["avg_position_fraction"], m["position_changes"], m["policy_pressure_gain"]) for m in self.metrics])
        con.commit()
        con.close()
        return run
