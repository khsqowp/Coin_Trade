import unittest

from chart_predictor.l2_book import LocalBook, SequenceGap


def diff(first, final, previous, bids=(), asks=()):
    return {"U": first, "u": final, "pu": previous, "b": list(bids), "a": list(asks)}


class LocalBookTests(unittest.TestCase):
    def test_snapshot_bridge_and_absolute_quantity_updates(self):
        book = LocalBook()
        self.assertTrue(book.install_snapshot(
            {"lastUpdateId": 100, "bids": [["10", "2"]], "asks": [["11", "3"]]},
            [diff(99, 100, 98), diff(100, 101, 100, [["10", "4"], ["9", "1"]])],
        ))
        self.assertTrue(book.valid)
        self.assertEqual(book.last_update_id, 101)
        self.assertEqual(book.bids, {10.0: 4.0, 9.0: 1.0})
        self.assertEqual(book.asks, {11.0: 3.0})

    def test_event_before_bridge_is_ignored_and_snapshot_does_not_mutate_on_failure(self):
        book = LocalBook()
        snapshot = {"lastUpdateId": 100, "bids": [["10", "2"]], "asks": []}
        self.assertFalse(book.install_snapshot(snapshot, [diff(90, 99, 89)]))
        self.assertFalse(book.valid)
        self.assertFalse(book.install_snapshot(snapshot, [diff(101, 102, 100)]))
        self.assertFalse(book.valid)
        self.assertTrue(book.install_snapshot(snapshot, [diff(99, 101, 98, [["10", "0"]])]))
        self.assertTrue(book.valid)
        self.assertEqual(book.bids, {})

    def test_duplicate_event_and_forward_sequence_gap_invalidate_book(self):
        book = LocalBook()
        book.install_snapshot({"lastUpdateId": 10, "bids": [], "asks": []}, [diff(10, 11, 10)])
        with self.assertRaises(SequenceGap):
            book.apply_diff(diff(10, 11, 10))
        self.assertFalse(book.valid)

        book.install_snapshot({"lastUpdateId": 10, "bids": [], "asks": []}, [diff(10, 11, 10)])
        with self.assertRaises(SequenceGap):
            book.apply_diff(diff(13, 14, 12, [["9", "1"]]))
        self.assertFalse(book.valid)
        self.assertEqual(book.bids, {})
        self.assertEqual(book.asks, {})

    def test_out_of_order_old_event_invalidates_book(self):
        book = LocalBook()
        book.install_snapshot({"lastUpdateId": 10, "bids": [], "asks": []}, [diff(10, 11, 10)])
        with self.assertRaises(SequenceGap):
            book.apply_diff(diff(10, 10, 9))
        self.assertFalse(book.valid)

    def test_duplicate_in_snapshot_buffer_invalidates_atomic_install(self):
        book = LocalBook()
        with self.assertRaises(SequenceGap):
            book.install_snapshot(
                {"lastUpdateId": 10, "bids": [], "asks": []},
                [diff(10, 11, 9), diff(10, 11, 9)],
            )
        self.assertFalse(book.valid)
        self.assertEqual(book.bids, {})

    def test_newer_event_buffered_before_snapshot_bridge_is_not_silently_skipped(self):
        book = LocalBook()
        buffers = [
            [diff(102, 103, 101), diff(99, 101, 98)],
            [diff(101, 101, 100), diff(99, 101, 98)],
        ]
        for events in buffers:
            with self.subTest(events=events), self.assertRaises(SequenceGap):
                book.install_snapshot({"lastUpdateId": 100, "bids": [], "asks": []}, events)
            self.assertFalse(book.valid)
            self.assertEqual(book.bids, {})

    def test_invalidation_clears_levels_and_requires_new_snapshot_bridge(self):
        book = LocalBook()
        book.install_snapshot(
            {"lastUpdateId": 20, "bids": [["9", "2"]], "asks": [["10", "2"]]},
            [diff(20, 21, 20)],
        )
        book.invalidate("disconnect")
        self.assertFalse(book.valid)
        self.assertEqual(book.invalidate_reason, "disconnect")
        self.assertTrue(book.install_snapshot(
            {"lastUpdateId": 40, "bids": [["8", "1"]], "asks": [["11", "1"]]},
            [diff(40, 41, 40)],
        ))
        self.assertTrue(book.valid)
        self.assertEqual(book.last_update_id, 41)
        self.assertEqual(book.bids, {8.0: 1.0})
        self.assertEqual(book.asks, {11.0: 1.0})

    def test_invalid_snapshot_is_rejected(self):
        snapshots = [
            {},
            {"lastUpdateId": -1, "bids": [], "asks": []},
            {"lastUpdateId": 1, "bids": [["NaN", "2"]], "asks": []},
            {"lastUpdateId": 1, "bids": [], "asks": [["10", "-1"]]},
        ]
        for snapshot in snapshots:
            with self.subTest(snapshot=snapshot), self.assertRaises(ValueError):
                LocalBook().install_snapshot(snapshot, [])


if __name__ == "__main__":
    unittest.main()
