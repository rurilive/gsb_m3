import json
import os
import tempfile
import unittest

from sealstore import SealError, SealStore
from sealstore import journal


def sample_records():
    return [
        {"id": 1, "kind": "payment", "amount": 12.5},
        {"id": 2, "kind": "refund", "note": "逾期退回"},
        {"id": 3, "kind": "payment", "amount": 88},
    ]


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sealstore-test-")
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "batch.jsonl")
        self.store = SealStore()
        self.store.extend(sample_records())

    def read_lines(self):
        with open(self.path, encoding="utf-8") as handle:
            return handle.read().splitlines()

    def write_lines(self, lines):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def test_save_counts_a_header_and_one_line_per_record(self):
        self.assertEqual(journal.save(self.store, self.path), 4)
        self.assertEqual(len(self.read_lines()), 4)

    def test_header_is_first_and_canonical(self):
        journal.save(self.store, self.path)
        head = json.loads(self.read_lines()[0])
        self.assertEqual(
            head,
            {"digest": self.store.digest(), "format": "sealstore-journal/1", "records": 3},
        )

    def test_round_trip_preserves_records_and_digest(self):
        journal.save(self.store, self.path)
        rebuilt = journal.load(self.path)
        self.assertEqual(rebuilt.records(), sample_records())
        self.assertEqual(rebuilt.digest(), self.store.digest())
        self.assertEqual(journal.verify(self.path), self.store.digest())

    def test_empty_store_round_trips(self):
        journal.save(SealStore(), self.path)
        self.assertEqual(len(journal.load(self.path)), 0)

    def test_tampered_record_line_is_caught(self):
        journal.save(self.store, self.path)
        lines = self.read_lines()
        lines[2] = lines[2].replace("refund", "payment")
        self.write_lines(lines)
        with self.assertRaises(SealError):
            journal.load(self.path)

    def test_empty_record_line_is_caught(self):
        journal.save(self.store, self.path)
        lines = self.read_lines()
        del lines[1]
        self.write_lines(lines)
        with self.assertRaises(SealError):
            journal.load(self.path)

    def test_tampered_header_digest_is_caught(self):
        journal.save(self.store, self.path)
        head = json.loads(self.read_lines()[0])
        head["digest"] = "0" * 64
        lines = self.read_lines()
        lines[0] = json.dumps(head, sort_keys=True, separators=(",", ":"))
        self.write_lines(lines)
        with self.assertRaises(SealError):
            journal.verify(self.path)

    def test_foreign_file_is_rejected(self):
        self.write_lines(['{"hello":"world"}', '{"id":1}'])
        with self.assertRaises(SealError):
            journal.load(self.path)

    def test_empty_file_is_rejected(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("")
        with self.assertRaises(SealError):
            journal.load(self.path)


if __name__ == "__main__":
    unittest.main()
