import unittest

from data_tick.load import EXPECTED_DATA_DIR, EXPECTED_TICK_DIR, _resolve_root


class TickPathGuardTests(unittest.TestCase):
    def test_uses_only_canonical_repository_data_dir(self):
        self.assertEqual(
            _resolve_root({"TRADING_DATA_DIR": str(EXPECTED_DATA_DIR)}),
            EXPECTED_TICK_DIR,
        )

    def test_rejects_missing_canonical_data_dir(self):
        with self.assertRaisesRegex(RuntimeError, "TRADING_DATA_DIR"):
            _resolve_root({})

    def test_rejects_external_trading_data_dir(self):
        with self.assertRaisesRegex(RuntimeError, "TRADING_DATA_DIR"):
            _resolve_root({"TRADING_DATA_DIR": "/not-canonical"})

    def test_rejects_external_tick_override(self):
        with self.assertRaisesRegex(RuntimeError, "TICK_PARQUET_DIR"):
            _resolve_root({
                "TRADING_DATA_DIR": str(EXPECTED_DATA_DIR),
                "TICK_PARQUET_DIR": "/not-canonical/tick/parquet",
            })

    def test_accepts_exact_internal_tick_override(self):
        self.assertEqual(
            _resolve_root({
                "TRADING_DATA_DIR": str(EXPECTED_DATA_DIR),
                "TICK_PARQUET_DIR": str(EXPECTED_TICK_DIR),
            }),
            EXPECTED_TICK_DIR,
        )
