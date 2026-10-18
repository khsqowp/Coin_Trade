from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app import paper_strategy_engine as engine_module


class PaperStrategyEngineTests(unittest.TestCase):
    def test_registry_has_twenty_unique_strategies_and_requested_styles(self) -> None:
        strategies = engine_module.STRATEGIES
        self.assertEqual(len(strategies), 20)
        self.assertEqual(len({item.strategy_id for item in strategies}), 20)
        self.assertIn("volume_impulse_3_5", {item.strategy_id for item in strategies})
        self.assertIn("heikin_ashi_trend", {item.strategy_id for item in strategies})
        self.assertIn("deep_pullback_volume_burst", {item.strategy_id for item in strategies})
        impulse = next(item for item in strategies if item.strategy_id == "volume_impulse_3_5")
        heikin = next(item for item in strategies if item.strategy_id == "heikin_ashi_trend")
        pullback = next(item for item in strategies if item.strategy_id == "deep_pullback_volume_burst")
        self.assertEqual((impulse.stop_loss_pct, impulse.take_profit_pct), (0.03, 0.05))
        self.assertIsNone(heikin.stop_loss_pct)
        self.assertEqual(heikin.exit_policy.exit_rule, "ha_flip")
        self.assertEqual(pullback.exit_policy.target_mode, "swing")
        for strategy in strategies:
            if strategy.strategy_id != "volume_impulse_3_5":
                self.assertIsNone(strategy.stop_loss_pct, strategy.strategy_id)
                self.assertIsNone(strategy.take_profit_pct, strategy.strategy_id)
                self.assertNotEqual(strategy.exit_policy.exit_rule, "none", strategy.strategy_id)

    def test_impulse_has_exact_bracket_and_pullback_uses_structure(self) -> None:
        impulse = next(item for item in engine_module.STRATEGIES if item.strategy_id == "volume_impulse_3_5")
        self.assertEqual(engine_module._initial_levels(impulse, [], "long", 100.0), (97.0, 105.0))
        self.assertEqual(engine_module._initial_levels(impulse, [], "short", 100.0), (103.0, 95.0))

        pullback = next(item for item in engine_module.STRATEGIES if item.strategy_id == "deep_pullback_volume_burst")
        prices = [100, 101, 100.5, 102, 101.2, 103, 102, 104, 102.5, 103.5, 101.8, 102.5, 101.5, 103]
        bars = [
            {"open": p - 0.2, "high": p + 0.4, "low": p - 0.5, "close": p, "volume": 10,
             "buy_volume": 6, "sell_volume": 4, "minute": i}
            for i, p in enumerate(prices)
        ]
        stop, target = engine_module._initial_levels(pullback, bars, "long", 101.0)
        self.assertLess(stop, 101.0)
        self.assertGreater(target, 101.0)

    def test_ticks_form_one_minute_candles_and_enter_only_after_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = engine_module.StrategySpec("test", "test", lambda bars, funding: "long" if len(bars) == 1 else None)
            engine = engine_module.PaperStrategyEngine(Path(tmp) / "state.json", strategies=[spec], symbols=["BTC"])
            engine.on_trade("BTC", 0, 100.0, 1.0, False)
            self.assertFalse(engine.portfolios["test"]["positions"])
            engine.on_trade("BTC", 60_000, 101.0, 2.0, True)
            self.assertEqual(len(engine.bars["BTC"]), 1)
            position = engine.portfolios["test"]["positions"]["BTC"]
            self.assertEqual(position["side"], "long")
            self.assertGreater(position["entry_price"], 101.0)

    def test_stop_and_take_profit_close_position_and_persist_independent_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = engine_module.StrategySpec("test", "test", lambda bars, funding: "long", 0.03, 0.05)
            path = Path(tmp) / "state.json"
            engine = engine_module.PaperStrategyEngine(path, strategies=[spec], symbols=["BTC"], starting_equity=142.0)
            engine.on_trade("BTC", 0, 100.0, 1.0, False)
            engine.on_trade("BTC", 60_000, 100.0, 1.0, False)
            engine.on_trade("BTC", 60_001, 105.2, 1.0, False)
            portfolio = engine.portfolios["test"]
            self.assertNotIn("BTC", portfolio["positions"])
            self.assertEqual(portfolio["trades"], 1)
            self.assertGreater(portfolio["fees_paid"], 0)
            self.assertLess(portfolio["equity"], 142.0 + 142.0 * 0.05)
            stored = json.loads(path.read_text())
            self.assertIn("test", stored["portfolios"])

    def test_strategy_portfolios_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            specs = [
                engine_module.StrategySpec("long", "long", lambda bars, funding: "long"),
                engine_module.StrategySpec("short", "short", lambda bars, funding: "short"),
            ]
            engine = engine_module.PaperStrategyEngine(Path(tmp) / "state.json", strategies=specs, symbols=["BTC"])
            engine.on_trade("BTC", 0, 100.0, 1.0, False)
            engine.on_trade("BTC", 60_000, 100.0, 1.0, False)
            self.assertEqual(engine.portfolios["long"]["positions"]["BTC"]["side"], "long")
            self.assertEqual(engine.portfolios["short"]["positions"]["BTC"]["side"], "short")
            self.assertNotEqual(engine.portfolios["long"], engine.portfolios["short"])

    def test_missing_or_invalid_market_data_does_not_open_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = engine_module.StrategySpec("test", "test", lambda bars, funding: "invalid")
            engine = engine_module.PaperStrategyEngine(Path(tmp) / "state.json", strategies=[spec], symbols=["BTC"])
            engine.on_trade("BTC", 0, 0.0, 1.0, False)
            engine.on_trade("BTC", 60_000, 100.0, 1.0, False)
            self.assertFalse(engine.portfolios["test"]["positions"])

    def test_funding_settlement_is_charged_to_long_and_credited_to_short(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            specs = [
                engine_module.StrategySpec("long", "long", lambda bars, funding: "long"),
                engine_module.StrategySpec("short", "short", lambda bars, funding: "short"),
            ]
            engine = engine_module.PaperStrategyEngine(Path(tmp) / "state.json", strategies=specs, symbols=["BTC"])
            engine.on_funding("BTC", 0, 100_000, 0.001)
            engine.on_trade("BTC", 0, 100.0, 1.0, False)
            engine.on_trade("BTC", 60_000, 100.0, 1.0, False)
            engine.on_funding("BTC", 100_000, 200_000, 0.0005)
            self.assertLess(engine.portfolios["long"]["funding_pnl"], 0)
            self.assertGreater(engine.portfolios["short"]["funding_pnl"], 0)


if __name__ == "__main__":
    unittest.main()
