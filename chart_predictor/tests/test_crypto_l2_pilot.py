import asyncio
import json
from pathlib import Path
import time

import pytest

from scripts.research.crypto_l2_pilot import (
    BASE,
    CaptureLimit,
    JsonlSegment,
    Pilot,
    SYMBOLS,
    _validated_output_root,
    coverage_summary,
    interval_overlap,
    recovery_acceptance,
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
    segment = JsonlSegment(tmp_path / "capture.jsonl", max_bytes=1024,
                           manifest_reserve_bytes=512)
    with pytest.raises(CaptureLimit):
        segment.write({"payload": "x" * 600})

    manifest = segment.close(complete=False, run_manifest={"run_id": "test"})

    partial = tmp_path / "capture.jsonl.partial"
    assert partial.exists()
    assert manifest["segment"]["complete"] is False
    assert json.loads((tmp_path / "incomplete.json").read_text())["segment"]["sha256"]


def test_total_cap_includes_metadata_and_preserves_partial_on_failure(tmp_path):
    segment = JsonlSegment(tmp_path / "capture.jsonl", max_bytes=256,
                           manifest_reserve_bytes=100)
    segment.write({"kind": "x"})
    with pytest.raises(CaptureLimit, match="capture plus manifest"):
        segment.close(complete=False, run_manifest={"run_id": "test"})
    assert (tmp_path / "capture.jsonl.partial").exists()
    assert not (tmp_path / "incomplete.json").exists()


def test_manifest_reports_exact_metadata_and_total_output_bytes(tmp_path):
    path = tmp_path / "capture.jsonl"
    segment = JsonlSegment(path, max_bytes=16_384, manifest_reserve_bytes=4096)
    segment.write({"kind": "trade", "received_at_ms": 100})
    manifest = segment.close(complete=True, run_manifest={
        "run_id": "test",
        "resource_metrics": {"capture_elapsed_seconds": 60},
    })
    metadata_size = (tmp_path / "manifest.json").stat().st_size
    metrics = manifest["resource_metrics"]
    assert metrics["metadata_bytes"] == metadata_size
    assert metrics["total_output_bytes"] == path.stat().st_size + metadata_size
    assert metrics["total_output_bytes_per_hour"] == pytest.approx(
        metrics["total_output_bytes"] * 60
    )


def test_verifier_rejects_a_partially_written_final_jsonl_record(tmp_path):
    path = tmp_path / "partial.jsonl"
    path.write_bytes(b'{"kind":"started"}\n{"kind":"truncated"')
    from hashlib import sha256

    with pytest.raises(IOError, match="incomplete JSONL"):
        verify_segment(path, sha256(path.read_bytes()).hexdigest(), 2)


def test_restart_creates_new_segment_without_completing_old_partial(tmp_path):
    first = Pilot(tmp_path)
    first.segment.write({"kind": "before_restart"})
    first.segment.close(complete=False, run_manifest={"run_id": first.run_dir.name})

    second = Pilot(tmp_path)

    assert second.run_dir != first.run_dir
    assert (first.run_dir / "capture.jsonl.partial").exists()
    assert not (first.run_dir / "capture.jsonl").exists()
    second.segment.close(complete=False, run_manifest={"run_id": second.run_dir.name})


def test_depth_disconnect_invalidates_books_and_reconnect_requires_resync(tmp_path):
    pilot = Pilot(tmp_path)
    for symbol, book in pilot.books.items():
        assert book.install_snapshot(
            {"lastUpdateId": 10, "bids": [["9", "1"]], "asks": [["10", "1"]]},
            [{"U": 10, "u": 11, "pu": 10, "b": [], "a": []}],
        )
        assert book.valid
    pilot.depth_online = True

    pilot._depth_disconnected()
    assert not pilot.depth_online
    assert all(not book.valid and not book.bids and not book.asks for book in pilot.books.values())

    attempt = pilot._depth_connected()
    assert attempt == 1
    assert all(not book.valid for book in pilot.books.values())
    assert all(pilot.snapshots[symbol] is None for symbol in pilot.books)
    for book in pilot.books.values():
        book.invalidate("test_cleanup")
    pilot.segment.close(complete=False, run_manifest={"run_id": pilot.run_dir.name})


def test_first_successful_connection_is_not_counted_as_a_reconnect(tmp_path):
    pilot = Pilot(tmp_path)
    assert pilot._depth_connected() == 1
    assert pilot.reconnects["depth"] == 0
    pilot._depth_disconnected()
    assert pilot._depth_connected() == 2
    assert pilot.reconnects["depth"] == 1
    pilot._depth_disconnected()
    pilot.segment.close(complete=False, run_manifest={"run_id": pilot.run_dir.name})


def test_disconnect_discards_pending_snapshot_tasks_before_reconnect(tmp_path, monkeypatch):
    async def scenario():
        pilot = Pilot(tmp_path)
        old_task = asyncio.create_task(asyncio.Event().wait())
        pilot.snapshot_tasks["BTCUSDT"] = old_task
        pilot._depth_disconnected()
        await asyncio.sleep(0)
        assert old_task.cancelled()
        assert "BTCUSDT" not in pilot.snapshot_tasks

        monkeypatch.setattr(
            "scripts.research.crypto_l2_pilot._fetch_snapshot",
            lambda symbol: {"symbol": symbol},
        )
        pilot._start_snapshot("BTCUSDT", force=True)
        fresh_task = pilot.snapshot_tasks["BTCUSDT"]
        assert fresh_task is not old_task
        fresh_task.cancel()
        await asyncio.gather(old_task, fresh_task, return_exceptions=True)
        pilot.segment.close(complete=False, run_manifest={"run_id": pilot.run_dir.name})

    asyncio.run(scenario())


def test_unbridgeable_newer_buffer_refreshes_stale_snapshot(tmp_path, monkeypatch):
    pilot = Pilot(tmp_path)
    pilot.snapshots["BTCUSDT"] = {"lastUpdateId": 10, "bids": [], "asks": []}
    pilot.buffers["BTCUSDT"] = [
        {"U": 12, "u": 13, "pu": 11, "b": [], "a": []},
    ]
    requested = []
    monkeypatch.setattr(
        pilot, "_schedule_snapshot_retry", lambda symbol: requested.append(symbol)
    )

    pilot._try_bridge("BTCUSDT")

    assert requested == ["BTCUSDT"]
    assert pilot.snapshots["BTCUSDT"] is None
    assert pilot.buffers["BTCUSDT"]
    pilot.segment.close(complete=False, run_manifest={"run_id": pilot.run_dir.name})


def test_snapshot_retry_uses_bounded_exponential_backoff(tmp_path):
    async def scenario():
        pilot = Pilot(tmp_path)
        delays = []

        async def hold_retry(symbol, delay):
            delays.append(delay)
            await pilot.stop.wait()

        pilot._retry_snapshot = hold_retry
        for _ in range(5):
            pilot._schedule_snapshot_retry("BTCUSDT")
            task = pilot.snapshot_retry_tasks["BTCUSDT"]
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            pilot.snapshot_retry_tasks.pop("BTCUSDT", None)
        assert delays == [1.0, 2.0, 4.0, 8.0, 8.0]
        pilot.segment.close(complete=False, run_manifest={"run_id": pilot.run_dir.name})

    asyncio.run(scenario())


def test_short_mocked_end_to_end_capture_completes_and_verifies(tmp_path, monkeypatch):
    class FakeSocket:
        def __init__(self, pilot, depth):
            self.pilot = pilot
            self.depth = depth
            self.last_update = {"BTCUSDT": 100, "ETHUSDT": 100}
            self.bridge_sent = {"BTCUSDT": False, "ETHUSDT": False}
            self.trade_ids = {"BTCUSDT": 1, "ETHUSDT": 1}
            self.turn = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def __aiter__(self):
            return self._messages()

        async def _messages(self):
            while not self.pilot.stop.is_set():
                symbol = SYMBOLS[self.turn % len(SYMBOLS)]
                now_ms = time.time_ns() // 1_000_000
                if self.depth:
                    previous = self.last_update[symbol]
                    if not self.bridge_sent[symbol]:
                        first, final, previous_id = 99, 100, 98
                        self.bridge_sent[symbol] = True
                    else:
                        first, final, previous_id = previous + 1, previous + 1, previous
                    event = {
                        "e": "depthUpdate", "E": now_ms, "s": symbol,
                        "U": first, "u": final, "pu": previous_id,
                        "b": [], "a": [],
                    }
                    self.last_update[symbol] = final
                    stream = f"{symbol.lower()}@depth@500ms"
                else:
                    event = {"e": "aggTrade", "E": now_ms, "s": symbol,
                             "a": self.trade_ids[symbol], "p": "100", "q": "1", "m": False}
                    self.trade_ids[symbol] += 1
                    stream = f"{symbol.lower()}@aggTrade"
                self.turn += 1
                yield json.dumps({"stream": stream, "data": event})
                await asyncio.sleep(0.005)

    pilot = Pilot(tmp_path, capture_seconds=0.5, max_wall_seconds=3)
    monkeypatch.setattr(
        "scripts.research.crypto_l2_pilot._fetch_snapshot",
        lambda symbol: {"lastUpdateId": 100, "bids": [], "asks": []},
    )
    monkeypatch.setattr(
        "scripts.research.crypto_l2_pilot.websockets.connect",
        lambda url, **kwargs: FakeSocket(pilot, depth="/public/" in url),
    )

    result = asyncio.run(pilot.run())

    assert result["status"] == "completed"
    assert set(result["coverage"]) == set(SYMBOLS)
    assert all(result["coverage"][symbol]["coverage"] >= 0.99 for symbol in SYMBOLS), result["coverage"]
    assert result["acceptance"]["recovery"]["within_30_seconds"] is None
    assert result["resource_metrics"]["total_output_bytes"] <= result["hard_byte_cap"]
    assert result["resource_metrics"]["metadata_bytes"] == (
        pilot.run_dir / "manifest.json"
    ).stat().st_size


def test_snapshot_error_schedules_retry_without_blocking_depth_event_loop(tmp_path):
    async def scenario():
        async def fail():
            raise OSError("injected snapshot failure")

        pilot = Pilot(tmp_path)
        pilot.depth_online = True
        failed_task = asyncio.create_task(fail())
        with pytest.raises(OSError):
            await failed_task
        pilot.snapshot_tasks["BTCUSDT"] = failed_task

        await asyncio.wait_for(pilot._collect_snapshots(), timeout=0.2)

        assert "BTCUSDT" in pilot.snapshot_retry_tasks
        assert "BTCUSDT" not in pilot.snapshot_tasks
        retry = pilot.snapshot_retry_tasks["BTCUSDT"]
        retry.cancel()
        await asyncio.gather(retry, return_exceptions=True)
        pilot.segment.close(complete=False, run_manifest={"run_id": pilot.run_dir.name})

    asyncio.run(scenario())


def test_manifest_keeps_per_symbol_validity_intervals(tmp_path):
    pilot = Pilot(tmp_path)
    pilot.snapshots["BTCUSDT"] = {"lastUpdateId": 1, "bids": [], "asks": []}
    pilot.buffers["BTCUSDT"] = [
        {"U": 1, "u": 2, "pu": 1, "b": [], "a": []},
    ]
    pilot._try_bridge("BTCUSDT")
    pilot._invalidate("BTCUSDT", "test_gap")

    intervals = pilot.book_validity_intervals["BTCUSDT"]
    assert [interval["state"] for interval in intervals] == ["invalid", "valid", "invalid"]
    assert intervals[0]["end_monotonic_s"] is not None
    assert intervals[1]["end_reason"] == "test_gap"
    assert intervals[2]["end_monotonic_s"] is None

    manifest = pilot.segment.close(
        complete=False,
        run_manifest={"run_id": pilot.run_dir.name,
                      "book_validity_intervals": pilot.book_validity_intervals},
    )
    assert manifest["book_validity_intervals"]["BTCUSDT"] == intervals


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


def test_coverage_interval_excludes_time_before_sync_and_after_window():
    assert interval_overlap(9.75, 10.25, 10.0, 20.0) == pytest.approx(0.25)
    assert interval_overlap(19.75, 20.25, 10.0, 20.0) == pytest.approx(0.25)
    assert interval_overlap(20.0, 21.0, 10.0, 20.0) == 0


def test_no_live_recovery_is_not_reported_as_recovery_pass():
    result = recovery_acceptance({"BTCUSDT": [], "ETHUSDT": []})
    assert result["observed_both_symbols"] is False
    assert result["within_30_seconds"] is None
    assert result["no_recovery_observed_is_not_a_pass"] is True


def test_recovery_acceptance_requires_both_symbols_and_30_second_limit():
    assert recovery_acceptance({"BTCUSDT": [2], "ETHUSDT": [30]})["within_30_seconds"] is True
    assert recovery_acceptance({"BTCUSDT": [2], "ETHUSDT": [30.1]})["within_30_seconds"] is False
    assert recovery_acceptance({"BTCUSDT": [2], "ETHUSDT": []})["within_30_seconds"] is None


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
