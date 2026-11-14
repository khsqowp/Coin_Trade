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


# Market profiles. Initial values are IDENTICAL to the owner-decided RiskConfig defaults (rule 7: never relax on our own).
# Recommended per-profile adjustments are PROPOSALS in the report only; changing a value here is an owner decision.
# Owner decision (round 2): forward PAPER simulation whitelists = every symbol already collected. Only the whitelist differs;
# every LIMIT value is identical to the RiskConfig defaults (tests assert this field by field).
KR_WHITELIST = ("005930", "000660", "373220", "207940", "005380", "000270", "068270", "105560", "035420", "055550", "005490",
                "012330", "028260", "035720", "051910", "006400", "086790", "066570", "034730", "017670", "015760", "033780",
                "010130", "329180", "012450", "316140")
US_WHITELIST = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V", "UNH", "XOM", "LLY", "AVGO",
                "WMT", "COST", "SPY", "QQQ")


def _small_rotation_whitelist():
    """Universe symbols of the round-3 rotation study (data/research/rot_universe.json, written by rot-fetch); BTC/ETH if the file is absent."""
    import json
    from .config import DATA
    try:
        u = json.loads((DATA / "research" / "rot_universe.json").read_text())
        return tuple(sorted("%s/USDT" % v["base"] for v in u["symbols"].values()))
    except (OSError, ValueError, KeyError):
        return ("BTC/USDT", "ETH/USDT")


def _profiles():
    import dataclasses
    # crypto_small_rotation (round 3, OWNER DECISION: small account, all-in single position allowed): ONLY max_position_pct differs from the
    # defaults; whitelist = rotation universe. Every other limit (daily loss, MDD halt, trades/day, gate thresholds) is inherited unchanged.
    return {"crypto_fast": RiskConfig(),
            "crypto_small_rotation": dataclasses.replace(RiskConfig(), max_position_pct=1.0, whitelist=_small_rotation_whitelist()),
            "kr_equity": dataclasses.replace(RiskConfig(), whitelist=KR_WHITELIST),
            "us_equity": dataclasses.replace(RiskConfig(), whitelist=US_WHITELIST)}


PROFILES = _profiles()


@dataclass
class Decision:
    allowed: bool
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)   # non-blocking, always recorded/notified


# ---------------------------------------------------------------- promotion gate
def ablation_findings(ablation):
    """Translate a tp.ablation report into (blocking reasons, warnings).

    Policy (decided here, recorded in the gate output): a DEAD rule BLOCKS promotion. A dead rule means the
    code the backtest/Auditor evaluated is not the strategy the hypothesis describes (one stated rule does
    nothing), so every statistic is evidence about a different strategy. A false block only costs a re-run;
    a false pass puts mis-specified logic into dry-run. WEAK rules (tiny effect) only warn: they can be
    legitimate protective rules that rarely fire. Missing/invalid ablation evidence also blocks, because the
    check itself could not be performed.
    """
    r, w = [], []
    if not isinstance(ablation, dict):
        return ["ABLATION_UNAVAILABLE: missing"], w
    if ablation.get("status") != "ok":
        return ["ABLATION_UNAVAILABLE: %s" % ablation.get("status", "missing")], w
    if ablation.get("dead_rules"):
        r.append("DEAD_RULE: %s (removing it changes nothing)" % ",".join(ablation["dead_rules"]))
    if ablation.get("undeclared_hypothesis_rules"):
        r.append("HYPOTHESIS_RULE_NOT_IMPLEMENTED: %s" % ",".join(ablation["undeclared_hypothesis_rules"]))
    if ablation.get("weak_rules"):
        w.append("WEAK_RULE: %s (<%.1f%% of bars changed, same trade count)" %
                 (",".join(ablation["weak_rules"]), 100 * ablation.get("thresholds", {}).get("weak_diff_frac", 0.005)))
    return r, w


def gate_strategy(audit, backtest, symbol, cfg=RiskConfig(), ablation="skip"):
    """ablation='skip' keeps the legacy behaviour (no ablation input); pass a report dict (or None = missing)."""
    r = []
    warnings = []
    if ablation != "skip":
        ar, warnings = ablation_findings(ablation)
        r.extend(ar)
    try:
        validate(audit, AUDITOR)
    except Exception as e:  # schema violation or non-dict
        return Decision(False, r + ["AUDIT_SCHEMA_INVALID: %s" % str(e).splitlines()[0][:120]], warnings)
    if isinstance(backtest, dict) and backtest.get("unverifiable"):
        r.append("UNVERIFIABLE_STRATEGY: %s" % str(backtest["unverifiable"])[:160])
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
        return Decision(False, r + ["BACKTEST_EVIDENCE_MISSING"], warnings)
    if isinstance(ablation, dict) and ablation.get("strategy_sha256") and backtest.get("strategy_sha256") \
            and ablation["strategy_sha256"] != backtest["strategy_sha256"]:
        r.append("EVIDENCE_CODE_MISMATCH: ablation and backtest were produced from different strategy.py")
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
    return Decision(not r, r, warnings)


NUMERIC_AUDIT_STUB = {"verdict": "PASS", "findings": [], "stats_assessment": "numeric gate only (no Auditor LLM)", "confidence": 1.0,
                      "rationale": "placeholder used ONLY by the pool-wide numeric screen; real pipeline runs use the Auditor",
                      "checks": {"lookahead_bias": "clean", "data_leakage": "clean", "overfitting": "clean",
                                 "costs_slippage": "clean", "sample_size": "clean"}}


def gate_numeric(backtest, symbol, ablation, cfg=RiskConfig()):
    """All deterministic gate checks with the Auditor stub (labelled). Used for the pool screen; never for promotion."""
    d = gate_strategy(NUMERIC_AUDIT_STUB, backtest, symbol, cfg, ablation=ablation)
    return d


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
