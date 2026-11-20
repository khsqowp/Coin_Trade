from datetime import datetime, timezone

import pytest

from scripts.research.audit_cvd_inputs import validate_funding_rows, validate_kline_rows


def _month_start_ms(year=2023, month=3):
    return int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)


def _kline_rows():
    start = _month_start_ms()
    rows = []
    for index in range(31 * 24):
        open_ms = start + index * 3_600_000
        rows.append({
            "open_time": str(open_ms), "open": "100", "high": "101", "low": "99",
            "close": "100.5", "volume": "10", "close_time": str(open_ms + 3_599_999),
            "quote_volume": "1000", "count": "5", "taker_buy_volume": "6",
            "taker_buy_quote_volume": "600", "ignore": "0",
        })
    return rows


def _funding_rows():
    start = _month_start_ms()
    return [
        {"calc_time": str(start + i * 8 * 3_600_000),
         "funding_interval_hours": "8", "last_funding_rate": "0.0001"}
        for i in range(31 * 3)
    ]


def test_complete_hourly_kline_month_and_taker_bounds_pass():
    result = validate_kline_rows(_kline_rows(), "BTCUSDT", "2023-03")
    assert result["row_count"] == 31 * 24
    assert result["gap_count"] == 0
    assert result["taker_buy_base_min"] == 6.0


def test_partial_first_month_is_allowed_only_as_contiguous_left_truncation():
    rows = _kline_rows()[-201:]
    result = validate_kline_rows(rows, "ARBUSDT", "2023-03", allow_partial_start=True)
    assert result["row_count"] == 201
    assert result["leading_unobserved_hours"] == 31 * 24 - 201
    with pytest.raises(ValueError, match="expected 744"):
        validate_kline_rows(rows, "ARBUSDT", "2023-03")


@pytest.mark.parametrize("mutate,reason", [
    (lambda rows: rows.__setitem__(20, {**rows[20], "taker_buy_volume": "11"}), "taker-buy volume"),
    (lambda rows: rows.__setitem__(20, {**rows[20], "close_time": "0"}), "close_time"),
    (lambda rows: rows.__setitem__(20, {**rows[20], "open_time": rows[19]["open_time"]}), "duplicate or off-grid"),
])
def test_invalid_hourly_kline_inputs_fail_closed(mutate, reason):
    rows = _kline_rows()
    mutate(rows)
    with pytest.raises(ValueError, match=reason):
        validate_kline_rows(rows, "BTCUSDT", "2023-03")


def test_funding_intervals_and_values_validate():
    result = validate_funding_rows(_funding_rows(), "BTCUSDT", "2023-03")
    assert result["row_count"] == 31 * 3
    assert result["interval_hours"] == [8]
    assert result["utc_grid_checked"] is True
    assert result["boundary_checked"] is True


def test_funding_gap_or_nonfinite_rate_fails_closed():
    rows = _funding_rows()
    rows[2] = {**rows[2], "calc_time": str(int(rows[2]["calc_time"]) + 3_600_000)}
    with pytest.raises(ValueError, match="funding timestamps disagree"):
        validate_funding_rows(rows, "BTCUSDT", "2023-03")
    rows = _funding_rows()
    rows[0] = {**rows[0], "last_funding_rate": "NaN"}
    with pytest.raises(ValueError, match="non-finite last_funding_rate"):
        validate_funding_rows(rows, "BTCUSDT", "2023-03")


@pytest.mark.parametrize("remove_index,reason", [
    (0, "missing first expected UTC funding settlement"),
    (-1, "missing last expected UTC funding settlement"),
])
def test_missing_funding_month_boundary_settlement_fails_closed(remove_index, reason):
    rows = _funding_rows()
    rows.pop(remove_index)
    with pytest.raises(ValueError, match=reason):
        validate_funding_rows(rows, "BTCUSDT", "2023-03")


def test_partial_listing_can_start_with_pre_first_hourly_candle_settlement():
    rows = _funding_rows()
    partial_kline_start = _month_start_ms() + 7 * 3_600_000
    result = validate_funding_rows(
        rows, "ARBUSDT", "2023-03", expected_start_ms=partial_kline_start,
        allow_partial_start=True)
    assert result["boundary_checked"] is True
