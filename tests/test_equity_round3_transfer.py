from app.rs_equity_round3_transfer import source_rows


def test_round3_source_grid_includes_53_experiments_and_three_baselines():
    rows = source_rows()
    assert len(rows) == 56
    assert sum(row["kind"] == "baseline" for row in rows) == 3
    assert sum(row["kind"] != "baseline" for row in rows) == 53
    assert sum(row["kind"] == "breaker" for row in rows) == 48
    assert sum(row["kind"] == "volatility" for row in rows) == 3
    assert sum(row["kind"] == "loose_hybrid" for row in rows) == 2
