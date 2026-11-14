from tp.risk import RiskConfig


def test_risk_limits_unchanged_by_this_work():
    """The owner decides limits; the ablation work must not touch them."""
    c = RiskConfig()
    assert c.max_backtest_mdd == 0.35 and c.min_total_trades == 30 and c.min_oos_trades == 10
    assert c.min_oos_bars == 250 and c.min_oos_sharpe == 0.5 and c.min_oos_to_is_sharpe == 0.5
    assert c.whitelist == ("BTC/USDT", "ETH/USDT") and c.allowed_modes == ("dry_run", "paper")
