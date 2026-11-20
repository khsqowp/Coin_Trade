from scripts.research.audit_funding_timestamp_mapping import compare_rows


def test_funding_archive_rows_match_timestamp_and_exact_decimal_rate():
    result = compare_rows([(1000, "0.001000"), (2000, "-0.002")],
                          [(1000, "0.001"), (2000, "-0.0020")])
    assert result["pass"] is True
    assert result["timestamp_matches"] == 2
    assert result["exact_rate_matches"] == 2


def test_funding_archive_mismatch_is_not_hidden():
    result = compare_rows([(1000, "0.001"), (2000, "-0.002")],
                          [(1000, "0.0011"), (3000, "0.003")])
    assert result["pass"] is False
    assert result["archive_only_timestamps"] == [2000]
    assert result["api_only_timestamps"] == [3000]
    assert result["exact_rate_matches"] == 0
