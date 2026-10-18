from report import closed_trades, max_drawdown


def test_partial_fills_grouped_and_both_fees():
    fills = [
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 1,
            "ts": 0,
            "fee": 0.05,
            "realized_pnl": 0,
            "decision_id": "entry",
        },
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 1,
            "ts": 1,
            "fee": 0.05,
            "realized_pnl": 0,
            "decision_id": "entry",
        },
        {
            "symbol": "BTCUSDT",
            "side": "SELL",
            "qty": 1,
            "ts": 2,
            "fee": 0.055,
            "realized_pnl": 10,
        },
        {
            "symbol": "BTCUSDT",
            "side": "SELL",
            "qty": 1,
            "ts": 3,
            "fee": 0.055,
            "realized_pnl": 10,
        },
    ]
    trades = closed_trades(fills)
    assert len(trades) == 1 and trades[0]["net_pnl"] == 19.79
    assert trades[0]["entry_decision_id"] == "entry"
    assert max_drawdown([1000, 1100, 880, 1200]) == 20
