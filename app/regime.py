"""Historical macro/news regime timeline for BTC, used as a backtest-only proxy for
the "경제팀 오버레이 필터" described in docs/trading-agent-plan.md.

IMPORTANT — this is NOT the real economy-team LLM pipeline output. That pipeline only
started producing synthesis documents recently and has no multi-year history to
backtest against. This timeline is a researched, best-effort reconstruction of known
BTC market regimes (FTX collapse, ETF approval, 2024 halving, yen carry-trade unwind,
Oct 2025 liquidation cascade, etc.), sourced via web research and cross-checked across
multiple outlets. Treat it as an approximation for testing whether a regime-aware
filter would have helped historically — not as a validated ground truth, and not as
the actual signal the live bot will use (the live bot uses the real, current economy
team synthesis, which by definition has no equivalent for past years).

Confidence is lower for periods closer to "now" (2026-07) since narratives there are
less settled with hindsight than e.g. the 2022 FTX collapse.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

# (start, end, label) — end is exclusive. Labels: RISK_ON, RISK_OFF, NEUTRAL.
_TIMELINE: list[tuple[str, str, str]] = [
    ("2022-01-01", "2022-11-02", "RISK_OFF"),   # 긴축·테라루나 붕괴, BTC 47.6K -> 19K대
    ("2022-11-02", "2023-02-01", "RISK_OFF"),   # FTX 파산, 컨테이전, BTC 16.5K대 저점
    ("2023-02-01", "2023-03-10", "NEUTRAL"),    # FTX 이후 20~25K 박스권 회복 초기
    ("2023-03-10", "2023-07-01", "RISK_ON"),    # SVB 사태 역설적 랠리, ETF 기대감 형성
    ("2023-07-01", "2023-11-01", "NEUTRAL"),    # 25~30K 박스권 장기 횡보
    ("2023-11-01", "2024-04-01", "RISK_ON"),    # 현물 ETF 승인(2024-01-10), 사상 최고가 경신
    ("2024-04-01", "2024-08-05", "NEUTRAL"),    # 반감기 이후 55~70K 박스권, 매도 압력
    ("2024-08-05", "2024-08-16", "RISK_OFF"),   # 엔캐리 청산 쇼크, 48시간 -20%
    ("2024-08-16", "2024-12-01", "RISK_ON"),    # 급반등 + 미 대선 랠리, 103K대
    ("2024-12-01", "2025-03-01", "RISK_ON"),    # 취임 랠리 후 관세 이슈로 상승세 둔화
    ("2025-03-01", "2025-10-10", "RISK_ON"),    # 변동성 속 상승 지속, 126K 고점(2025-10)
    ("2025-10-10", "2025-11-01", "RISK_OFF"),   # 사상 최대 청산 캐스케이드($20B+)
    ("2025-11-01", "2026-07-01", "RISK_OFF"),   # 126K 고점 이후 장기 하락, 58K대까지
    ("2026-07-01", "2026-07-20", "NEUTRAL"),    # 이른 반등 조짐이나 판단 근거 부족 (저신뢰)
]

_DEFAULT_LABEL = "NEUTRAL"


def _to_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc))


_PARSED = [(_to_timestamp(start), _to_timestamp(end), label) for start, end, label in _TIMELINE]


def regime_at(timestamp: pd.Timestamp) -> str:
    for start, end, label in _PARSED:
        if start <= timestamp < end:
            return label
    return _DEFAULT_LABEL


def regime_series(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series([regime_at(ts) for ts in index], index=index, name="REGIME")
