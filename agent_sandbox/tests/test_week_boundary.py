from datetime import datetime
import pytest
from generation import week_bounds


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


@pytest.mark.parametrize(
    "date,start,end",
    [
        ("2024-01-07T23:59:59Z", "2024-01-01T00:00:00Z", "2024-01-08T00:00:00Z"),
        ("2024-01-08T00:00:00Z", "2024-01-08T00:00:00Z", "2024-01-15T00:00:00Z"),
        ("2023-12-31T23:59:59Z", "2023-12-25T00:00:00Z", "2024-01-01T00:00:00Z"),
        ("2025-01-01T12:00:00Z", "2024-12-30T00:00:00Z", "2025-01-06T00:00:00Z"),
    ],
)
def test_bounds(date, start, end):
    assert week_bounds(ts(date)) == (ts(start), ts(end))
