import io
import zipfile

import pandas as pd

from scripts.research.compare_usdm_oi_archive_rest import compare


def _archive_and_rest():
    start = 1_800_000_000_000
    rows = []
    rest = []
    for index in range(288):
        stamp = start + index * 300_000
        oi = 1000.0 + index * 0.37
        value = 20_000.0 + index * 3.11
        rows.append([pd.to_datetime(stamp, unit="ms", utc=True).strftime("%Y-%m-%d %H:%M:%S"),
                     "BTCUSDT", oi, value])
        rest.append({"timestamp": stamp + 300_000,
                     "sumOpenInterest": str(oi), "sumOpenInterestValue": str(value)})
    frame = pd.DataFrame(rows, columns=["create_time", "symbol", "sum_open_interest",
                                       "sum_open_interest_value"])
    raw = frame.to_csv(index=False).encode()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("metrics.csv", raw)
    return archive.getvalue(), pd.DataFrame(rest).to_json(orient="records").encode()


def test_one_day_comparison_detects_preregistered_plus_five_minute_mapping():
    archive, rest = _archive_and_rest()
    result = compare(archive, rest)
    assert result["mapping_results"]["5"]["coverage"] == 1.0
    assert result["mapping_results"]["5"]["fields"]["sum_open_interest"][
        "median_absolute_relative_error"] == 0.0
    assert result["predeclared_plus_5m_alignment_screen"] == "PASS"
