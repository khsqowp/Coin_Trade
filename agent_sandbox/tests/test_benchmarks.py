from benchmarks import btc_buy_hold, random_trader
from config import Config


def rows(n=200):
    return [
        [i * 3600000, 100 + i / 10, 102 + i / 10, 98 + i / 10, 100.1 + i / 10, 1]
        for i in range(n)
    ]


def test_buy_hold():
    assert (
        btc_buy_hold(
            [[0, 100, 110, 90, 105, 1], [3600000, 105, 120, 100, 120, 1]], 0, 7200
        )
        == 19.999999999999996
    )
    assert btc_buy_hold([], 0, 1) is None


def test_deterministic_distribution():
    cfg = Config(watchlist=["BTCUSDT"])
    first = random_trader(
        {"BTCUSDT": rows()}, 14 * 3600, 200 * 3600, cfg, seed=42, runs=30
    )
    assert first == random_trader(
        {"BTCUSDT": rows()}, 14 * 3600, 200 * 3600, cfg, seed=42, runs=30
    )
    assert first != random_trader(
        {"BTCUSDT": rows()}, 14 * 3600, 200 * 3600, cfg, seed=43, runs=30
    )
    assert first["p10"] <= first["median"] <= first["p90"]
    assert 0 <= first["share_ge_target"] <= 1


def test_no_candles():
    assert random_trader({}, 0, 1, Config(), runs=2)["runs"] == 0
