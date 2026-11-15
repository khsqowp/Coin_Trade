import asyncio
import json
from pathlib import Path

import pytest

from scripts.research.crypto_l2_pilot import (
    BASE,
    CaptureLimit,
    JsonlSegment,
    Pilot,
    _validated_output_root,
    coverage_summary,
    stream_event_latency_ms,
    verify_segment,
)


def test_jsonl_segment_close_verifies_hash_count_and_time_range(tmp_path):
    path = tmp_path / "capture.jsonl"
    segment = JsonlSegment(path, max_bytes=1024)
    segment.write({"kind": "trade", "received_at_ms": 100})
    segment.write({"kind": "trade", "received_at_ms": 110})

    manifest = segment.close(complete=True, run_manifest={"run_id": "test"})

    assert manifest["segment"]["complete"] is True
    assert manifest["segment"]["record_count"] == 2
    assert manifest["segment"]["first_receive_ms"] == 100
    assert manifest["segment"]["last_receive_ms"] == 110
    verify_segment(path, manifest["segment"]["sha256"], 2)
    assert not path.with_suffix(".jsonl.partial").exists()


def test_jsonl_segment_hard_cap_preserves_partial_file(tmp_path):
    segment = JsonlSegment(tmp_path / "capture.jsonl", max_bytes=10)
    with pytest.raises(CaptureLimit):
        segment.write({"payload": "too large"})

    manifest = segment.close(complete=False, run_manifest={"run_id": "test"})

    partial = tmp_path / "capture.jsonl.partial"
    assert partial.exists()
    assert manifest["segment"]["complete"] is False
    assert json.loads((tmp_path / "incomplete.json").read_text())["segment"]["sha256"]


def test_coverage_summary_uses_per_symbol_observation_denominator():
    result = coverage_summary(
        {"BTCUSDT": 100, "ETHUSDT": 200},
        {"BTCUSDT": 99, "ETHUSDT": 198},
        {"BTCUSDT": [1], "ETHUSDT": [2]},
        {"BTCUSDT": [3], "ETHUSDT": []},
    )
    assert result["BTCUSDT"]["coverage"] == pytest.approx(0.99)
    assert result["ETHUSDT"]["coverage"] == pytest.approx(0.99)
    assert result["ETHUSDT"]["max_recovery_seconds"] == 0


def test_event_latency_rejects_missing_or_non_integer_exchange_time():
    assert stream_event_latency_ms({"E": 900}, 1000) == 100
    assert stream_event_latency_ms({"E": "900"}, 1000) is None
    assert stream_event_latency_ms({"E": True}, 1000) is None


def test_output_root_is_confined_to_pilot_data_directory(tmp_path):
    allowed = BASE / "chart_predictor" / "data" / "crypto_l2_pilots" / "test"
    assert _validated_output_root(allowed) == allowed.resolve()
    with pytest.raises(ValueError):
        _validated_output_root(tmp_path)


def test_collector_task_failure_stops_run_and_writes_incomplete_manifest(tmp_path):
    class FailingPilot(Pilot):
        async def _depth_loop(self):
            raise CaptureLimit("test hard cap")

        async def _trades_loop(self):
            await self.stop.wait()

        async def _monitor(self):
            await self.stop.wait()

    result = asyncio.run(FailingPilot(tmp_path).run())

    assert result["status"] == "incomplete"
    assert result["reason"] == "test hard cap"
    assert result["segment"]["complete"] is False
    assert Path(tmp_path, result["run_id"], "capture.jsonl.partial").exists()
