import hashlib
import unittest

from sealstore import SealError, SealStore, empty_digest, record_digest


class EmptyStoreTests(unittest.TestCase):
    def test_empty_digest_is_the_chain_tag(self):
        self.assertEqual(empty_digest(), hashlib.sha256(b"sealstore/v1/chain").hexdigest())
        self.assertEqual(SealStore().digest(), empty_digest())

    def test_empty_store_stats(self):
        self.assertEqual(SealStore().stats(), {"records": 0, "digest": empty_digest()})
        self.assertEqual(len(SealStore()), 0)


class AppendTests(unittest.TestCase):
    def test_append_returns_the_record_digest(self):
        store = SealStore()
        record = {"id": 1, "amount": 2.5}
        self.assertEqual(store.append(record), record_digest(record))

    def test_digest_changes_with_content_and_order(self):
        first = {"id": 1}
        second = {"id": 2}
        forward = SealStore()
        forward.extend([first, second])
        backward = SealStore()
        backward.extend([second, first])
        self.assertNotEqual(forward.digest(), backward.digest())
        self.assertNotEqual(forward.digest(), empty_digest())

    def test_store_copies_the_record_it_is_given(self):
        store = SealStore()
        record = {"id": 1, "tags": ["x"]}
        store.append(record)
        record["tags"].append("y")
        record["id"] = 99
        self.assertEqual(store.records(), [{"id": 1, "tags": ["x"]}])
        self.assertEqual(store.digest(), _replayed_digest([{"id": 1, "tags": ["x"]}]))

    def test_records_hands_out_copies(self):
        store = SealStore()
        store.append({"id": 1})
        copy = store.records()
        copy[0]["id"] = 99
        self.assertEqual(store.records(), [{"id": 1}])
        self.assertEqual(store.digest(), _replayed_digest([{"id": 1}]))

    def test_rejecting_a_record_leaves_the_store_alone(self):
        store = SealStore()
        store.append({"id": 1})
        before = store.digest()
        with self.assertRaises(SealError):
            store.append({"id": 2, "bad": float("nan")})
        with self.assertRaises(SealError):
            store.append({3: "non-string key"})
        self.assertEqual(len(store), 1)
        self.assertEqual(store.digest(), before)

    def test_extend_counts(self):
        store = SealStore()
        self.assertEqual(store.extend([{"a": 1}, {"a": 2}, {"a": 3}]), 3)
        self.assertEqual(len(store), 3)


def _replayed_digest(records):
    store = SealStore()
    store.extend(records)
    return store.digest()


if __name__ == "__main__":
    unittest.main()
