from app.rs_equity_round4_transfer import PERIODS, winners


def test_round4_uses_the_five_source_winners_and_eight_original_windows():
    rows = winners()
    assert [(r["name"], r["config"]["dd_trigger"]) for r in rows] == [
        ("heikin_ashi", .15), ("heikin_ashi", .20), ("heikin_ashi", .25),
        ("heikin_ashi", .30), ("frvp", .20),
    ]
    assert len(PERIODS) == 8
