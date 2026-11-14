"""Deterministic Risk Engine. NO LLM, no network, no randomness.

Two layers:
  1. gate_strategy(): promotion gate. Nothing moves to dry-run unless the Auditor said PASS *and*
     deterministic checks on the backtest evidence also hold.
  2. RiskEngine: runtime order checks (whitelist, position cap, daily loss, drawdown halt, trade-count cap).
Live trading is structurally impossible: mode must be dry_run/paper.
"""
import datetime as dt
from dataclasses import dataclass, field

from .schemas import AUDITOR, validate


@dataclass(frozen=True)
class RiskConfig:
    whitelist: tuple = ("BTC/USDT", "ETH/USDT")
    allowed_modes: tuple = ("dry_run", "paper")
    max_position_pct: float = 0.25          # of equity, per symbol
    daily_loss_limit_pct: float = 0.03
    max_drawdown_halt_pct: float = 0.15
    max_trades_per_day: int = 10
    # promotion-gate thresholds
    min_total_trades: int = 30
    min_oos_trades: int = 10
    min_oos_bars: int = 250
    max_backtest_mdd: float = 0.35
    min_oos_sharpe: float = 0.5
    min_oos_to_is_sharpe: float = 0.5       # OOS Sharpe must keep >=50% of IS Sharpe (overfit guard)
    min_fee: float = 0.0005
    min_slippage: float = 0.0002


@dataclass
class Decision:
    allowed: bool
    reasons: list = field(default_factory=list)


# ---------------------------------------------------------------- promotion gate
def gate_strategy(audit, backtest, symbol, cfg=RiskConfig()):
    r = []
    try:
        validate(audit, AUDITOR)
    except Exception as e:  # schema violation or non-dict
        return Decision(False, ["AUDIT_SCHEMA_INVALID: %s" % str(e).splitlines()[0][:120]])
    if audit["verdict"] != "PASS":
        r.append("AUDIT_NOT_PASS: verdict=%s" % audit["verdict"])
    if any(f["severity"] in ("high", "critical") for f in audit["findings"]):
        r.append("AUDIT_HIGH_SEVERITY_FINDING")
    if any(v in ("found", "suspected") for k, v in audit["checks"].items()
           if k in ("lookahead_bias", "data_leakage")):
        r.append("AUDIT_LEAKAGE_FLAG")
    if symbol not in cfg.whitelist:
        r.append("SYMBOL_NOT_WHITELISTED: %s" % symbol)
    try:
        p, full, is_, oos = backtest["params"], backtest["full"], backtest["in_sample"], backtest["out_of_sample"]
        la = backtest["lookahead_check"]
    except (KeyError, TypeError):
        return Decision(False, r + ["BACKTEST_EVIDENCE_MISSING"])
    if not la.get("passed"):
        r.append("ENGINE_LOOKAHEAD_CHECK_FAILED: mismatches=%s errors=%s" % (la.get("mismatches"), la.get("errors")))
    if backtest.get("invalid_signal_values", 0) > 0:
        r.append("INVALID_SIGNAL_VALUES")
    if p.get("fee", 0) < cfg.min_fee or p.get("slippage", 0) < cfg.min_slippage:
        r.append("COSTS_TOO_LOW_OR_MISSING")
    if full["trades"] < cfg.min_total_trades:
        r.append("TOO_FEW_TRADES: %d < %d" % (full["trades"], cfg.min_total_trades))
    if oos["trades"] < cfg.min_oos_trades:
        r.append("TOO_FEW_OOS_TRADES: %d < %d" % (oos["trades"], cfg.min_oos_trades))
    if oos["bars"] < cfg.min_oos_bars:
        r.append("OOS_TOO_SHORT: %d < %d bars" % (oos["bars"], cfg.min_oos_bars))
    if full["mdd"] > cfg.max_backtest_mdd:
        r.append("BACKTEST_MDD_TOO_HIGH: %.3f > %.3f" % (full["mdd"], cfg.max_backtest_mdd))
    if oos["sharpe"] < cfg.min_oos_sharpe:
        r.append("OOS_SHARPE_TOO_LOW: %.2f < %.2f" % (oos["sharpe"], cfg.min_oos_sharpe))
    if is_["sharpe"] > 0 and oos["sharpe"] < cfg.min_oos_to_is_sharpe * is_["sharpe"]:
        r.append("OOS_DEGRADATION: oos %.2f vs is %.2f" % (oos["sharpe"], is_["sharpe"]))
    return Decision(not r, r)


# ---------------------------------------------------------------- runtime engine
class RiskEngine:
    def __init__(self, cfg=RiskConfig(), equity=10_000.0, mode="dry_run", now=None):
        self.cfg, self.mode = cfg, mode
        now = now or dt.datetime.now(dt.timezone.utc)
        self.day = now.date()
        self.peak = self.day_start = self.equity = float(equity)
        self.trades_today = 0
        self.halted_day = False
        self.halted_dd = False

    @property
    def halted(self):
        return self.halted_day or self.halted_dd

    def _roll(self, ts):
        if ts.date() != self.day:
            self.day, self.trades_today, self.halted_day = ts.date(), 0, False
            self.day_start = self.equity

    def on_equity(self, equity, ts):
        self._roll(ts)
        self.equity = float(equity)
        self.peak = max(self.peak, self.equity)
        if self.day_start > 0 and (self.day_start - self.equity) / self.day_start >= self.cfg.daily_loss_limit_pct:
            self.halted_day = True
        if self.peak > 0 and (self.peak - self.equity) / self.peak >= self.cfg.max_drawdown_halt_pct:
            self.halted_dd = True  # sticky until manual_reset()

    def manual_reset(self):
        self.halted_dd = False
        self.peak = self.equity

    def check_order(self, symbol, side, notional, ts, current_position=0.0, mode=None):
        self._roll(ts)
        c, r = self.cfg, []
        if (mode or self.mode) not in c.allowed_modes:
            r.append("MODE_FORBIDDEN: %s" % (mode or self.mode))
        if symbol not in c.whitelist:
            r.append("SYMBOL_NOT_WHITELISTED")
        if side not in ("buy", "sell"):
            r.append("BAD_SIDE")
        if not (notional > 0):
            r.append("BAD_NOTIONAL")
        if self.trades_today >= c.max_trades_per_day:
            r.append("MAX_TRADES_PER_DAY")
        if side == "buy":
            if self.halted:
                r.append("HALTED_%s" % ("DRAWDOWN" if self.halted_dd else "DAILY_LOSS"))
            if self.equity <= 0 or (current_position + notional) / self.equity > c.max_position_pct:
                r.append("MAX_POSITION_PCT")
        return Decision(not r, r)

    def record_fill(self, ts):
        self._roll(ts)
        self.trades_today += 1
