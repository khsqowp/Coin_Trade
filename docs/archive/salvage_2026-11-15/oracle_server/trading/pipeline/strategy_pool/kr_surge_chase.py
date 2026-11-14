"""KR SURGE CHASE (대형주 + 급등/상한가 근접 종목 추격) - PAPER FORWARD SIMULATION ONLY. NO ORDER CODE EXISTS ANYWHERE.

Rules (implemented in tp.krsurge on 1-minute bars, NOT here): enter intraday when the day's change >= +6% and volume in
the last 5 minutes >= 3x its day average and price < limit-up proximity; exit at +5% take-profit, -3% stop-loss (with a
conservative stop-slippage assumption) or forced flat at the 15:20 close-out. Limit-up proximity (>=28%) = cannot buy.

DAILY BARS CANNOT VALIDATE THIS STRATEGY: the +5%/-3% path and the order of high/low inside a day are unknowable from OHLC.
Therefore generate_signals() (daily) deliberately returns no signals and verifiable() reports UNVERIFIABLE until
>= MIN_SESSIONS of stored KIS 1-minute sessions exist AND the forward simulator has been run - and even then the gate keeps the
strategy blocked until the owner reviews the forward results. It is only ever evaluated by tp.krsurge.forward_sim."""
import numpy as np
import pandas as pd

MIN_SESSIONS = 60
META = {"id": "kr_surge_chase", "family": "kr_surge_chase", "market": "kr", "profile": "kr_equity", "timeframes": ["1m"],
        "symbols": ["KOSPI large caps + daily top movers"], "validation": "unverifiable"}
RULES = {"surge_entry": "day change >= +6% and 5-min volume >= 3x average", "take_profit_5pct": "exit at +5%",
         "stop_loss_3pct": "exit at -3% (+ conservative slippage)", "eod_flat": "forced flat at 15:20"}
PROTECTIVE = {"stop_loss_3pct", "eod_flat"}
RULE_KINDS = {"surge_entry": "entry", "take_profit_5pct": "exit", "stop_loss_3pct": "protective", "eod_flat": "protective"}


def verifiable():
    return ("UNVERIFIABLE: daily bars cannot test intraday +5%%/-3%% exits; needs >= %d stored 1-minute KIS sessions and "
            "the tp.krsurge forward simulator (results are forward-paper only)" % MIN_SESSIONS)


def generate_signals(df, disabled=frozenset()):
    return pd.Series(np.zeros(len(df)), index=df.index, dtype=float)
