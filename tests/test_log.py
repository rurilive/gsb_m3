"""eventlog 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from eventlog import EventLog
from eventlog.log import EventLog as DirectEventLog


class TestEventLogBaseline(unittest.TestCase):
    def test_append_returns_increasing_offset(self):
        log = EventLog()
        self.assertEqual(log.append("a"), 0)
        self.assertEqual(log.append("b"), 1)
        self.assertEqual(log.append("c"), 2)

    def test_read_returns_events_in_append_order(self):
        log = EventLog()
        log.append({"type": "created", "id": 1})
        log.append({"type": "updated", "id": 1})
        log.append({"type": "deleted", "id": 1})
        self.assertEqual(
            [e["type"] for e in log.read()],
            ["created", "updated", "deleted"],
        )

    def test_len_tracks_appends(self):
        log = EventLog()
        self.assertEqual(len(log), 0)
        log.append("x")
        log.append("y")
        self.assertEqual(len(log), 2)

    def test_read_returns_copy(self):
        log = EventLog()
        log.append("x")
        got = log.read()
        got.append("y")
        self.assertEqual(len(log.read()), 1)

    def test_iter_yields_in_order(self):
        log = EventLog()
        log.append(1)
        log.append(2)
        log.append(3)
        self.assertEqual(list(log), [1, 2, 3])

    def test_events_are_stored_verbatim(self):
        log = EventLog()
        event = {"type": "created", "payload": [1, 2]}
        log.append(event)
        self.assertIs(log.read()[0], event)

    def test_empty_log_reads_empty(self):
        log = EventLog()
        self.assertEqual(log.read(), [])
        self.assertEqual(len(log), 0)

    def test_package_exports_same_class(self):
        self.assertIs(EventLog, DirectEventLog)


if __name__ == "__main__":
    unittest.main()
