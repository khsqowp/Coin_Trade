"""Only acceptance calendar from Round14 onward: definition Y, eight 2-year windows.

Round4/6 definition X remains historical evidence, never an acceptance calendar.
"""

PERIOD_STANDARD = "정의Y: 순수 2년 롤링창 8개"
ALPHA_PERIODS = tuple(
    [(f"{y}-09-08", f"{y + 2}-09-07") for y in range(2019, 2024)]
    + [
        ("2020-10-06", "2022-10-05"),
        ("2023-10-06", "2025-10-05"),
        ("2024-10-06", "2026-10-05"),
    ]
)


def assert_standard(rows: list[dict]) -> None:
    """Reject an alternate calendar before interpreting an alpha vote."""
    if tuple((r["start"], r["end"]) for r in rows) != ALPHA_PERIODS:
        raise ValueError("기간 기준 불일치: 정의Y의 순서와 경계를 정확히 사용해야 한다")


def alpha_pass(rows: list[dict]) -> bool:
    assert_standard(rows)
    return sum(r["alpha"] > 0 for r in rows) >= 7
