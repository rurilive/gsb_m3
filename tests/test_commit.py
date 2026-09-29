"""Baseline tests for commitx.commit.LocalCommit.

These tests lock down the current naive behaviour.  They must stay green and
must not be modified by later feature work.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commitx import LocalCommit, CommitConflict, CommitError


class LocalCommitTest(unittest.TestCase):
    def test_apply_stores_value(self):
        c = LocalCommit()
        c.apply({"key": "a", "value": 1})
        self.assertEqual(c.read("a"), 1)

    def test_keys_in_application_order(self):
        c = LocalCommit()
        c.apply({"key": "a", "value": 1})
        c.apply({"key": "b", "value": 2})
        self.assertEqual(c.keys(), ["a", "b"])

    def test_len_counts_state(self):
        c = LocalCommit()
        self.assertEqual(len(c), 0)
        c.apply({"key": "a", "value": 1})
        self.assertEqual(len(c), 1)

    def test_duplicate_key_conflicts(self):
        c = LocalCommit()
        c.apply({"key": "a", "value": 1})
        with self.assertRaises(CommitConflict):
            c.apply({"key": "a", "value": 2})

    def test_missing_key_rejected(self):
        c = LocalCommit()
        with self.assertRaises(CommitError):
            c.apply({"value": 1})

    def test_non_mapping_rejected(self):
        c = LocalCommit()
        with self.assertRaises(CommitError):
            c.apply(["key", "value"])

    def test_read_default(self):
        c = LocalCommit()
        self.assertIsNone(c.read("missing"))
        self.assertEqual(c.read("missing", 7), 7)

    def test_conflict_is_commit_error(self):
        self.assertTrue(issubclass(CommitConflict, CommitError))


if __name__ == "__main__":
    unittest.main()
