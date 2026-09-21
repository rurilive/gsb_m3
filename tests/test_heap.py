"""ObjectHeap 行为基线：分配、根集合、槽位读写、错误路径。"""

import unittest

from genheap import ObjectHeap, RootError, SlotError, UnknownObject


class TestAlloc(unittest.TestCase):

    def test_alloc_returns_increasing_ids(self):
        heap = ObjectHeap()
        first = heap.alloc()
        second = heap.alloc()
        self.assertGreater(second, first)
        self.assertTrue(heap.alive(first))
        self.assertTrue(heap.alive(second))
        self.assertEqual(heap.roots(), ())

    def test_kind_and_payload(self):
        heap = ObjectHeap()
        plain = heap.alloc()
        self.assertEqual(heap.kind(plain), "object")
        self.assertIsNone(heap.payload(plain))
        oid = heap.alloc("page", {"name": "home"})
        self.assertEqual(heap.kind(oid), "page")
        self.assertEqual(heap.payload(oid), {"name": "home"})

    def test_unknown_oid_rejected(self):
        heap = ObjectHeap()
        for query in (heap.kind, heap.payload, heap.refs, heap.slots):
            with self.assertRaises(UnknownObject):
                query(12345)


class TestRoots(unittest.TestCase):

    def test_add_root_is_idempotent(self):
        heap = ObjectHeap()
        oid = heap.alloc()
        self.assertTrue(heap.add_root(oid))
        self.assertFalse(heap.add_root(oid))
        self.assertEqual(heap.roots(), (oid,))

    def test_roots_are_sorted(self):
        heap = ObjectHeap()
        first = heap.alloc()
        second = heap.alloc()
        third = heap.alloc()
        for oid in (third, first, second):
            heap.add_root(oid)
        self.assertEqual(heap.roots(), (first, second, third))

    def test_drop_root_and_missing_root_rejected(self):
        heap = ObjectHeap()
        oid = heap.alloc()
        with self.assertRaises(RootError):
            heap.drop_root(oid)
        heap.add_root(oid)
        heap.drop_root(oid)
        self.assertEqual(heap.roots(), ())
        with self.assertRaises(RootError):
            heap.drop_root(oid)

    def test_add_root_on_dead_oid_rejected(self):
        heap = ObjectHeap()
        with self.assertRaises(UnknownObject):
            heap.add_root(999)


class TestSlots(unittest.TestCase):

    def test_store_returns_previous_value(self):
        heap = ObjectHeap()
        src = heap.alloc()
        first = heap.alloc()
        second = heap.alloc()
        self.assertIsNone(heap.store(src, "next", first))
        self.assertEqual(heap.store(src, "next", second), first)
        self.assertEqual(heap.load(src, "next"), second)
        self.assertIsNone(heap.load(src, "never-written"))

    def test_clear_slot_with_none(self):
        heap = ObjectHeap()
        src = heap.alloc()
        dst = heap.alloc()
        heap.store(src, "next", dst)
        self.assertEqual(heap.store(src, "next", None), dst)
        self.assertIsNone(heap.load(src, "next"))
        self.assertEqual(heap.slots(src), ())
        self.assertIsNone(heap.store(src, "next", None))

    def test_slots_sorted_and_cleared_removed(self):
        heap = ObjectHeap()
        src = heap.alloc()
        dst = heap.alloc()
        heap.store(src, "zeta", dst)
        heap.store(src, "alpha", dst)
        heap.store(src, "beta", dst)
        heap.store(src, "alpha", None)
        self.assertEqual(heap.slots(src), ("beta", "zeta"))

    def test_refs_deduped_and_sorted(self):
        heap = ObjectHeap()
        src = heap.alloc()
        shared = heap.alloc()
        heap.store(src, "left", shared)
        heap.store(src, "right", shared)
        self.assertEqual(heap.refs(src), (shared,))

    def test_self_reference_allowed(self):
        heap = ObjectHeap()
        src = heap.alloc()
        heap.store(src, "me", src)
        self.assertEqual(heap.refs(src), (src,))
        self.assertEqual(heap.load(src, "me"), src)

    def test_store_from_dead_source_rejected(self):
        heap = ObjectHeap()
        src = heap.alloc()
        dst = heap.alloc()
        heap.collect()
        self.assertFalse(heap.alive(src))
        with self.assertRaises(UnknownObject):
            heap.store(src, "slot", dst)

    def test_store_to_dead_target_rejected_and_old_value_kept(self):
        heap = ObjectHeap()
        src = heap.alloc()
        good = heap.alloc("good")
        bad = heap.alloc("bad")
        heap.add_root(src)
        heap.add_root(good)
        heap.store(src, "slot", good)
        heap.collect()
        self.assertFalse(heap.alive(bad))
        with self.assertRaises(UnknownObject):
            heap.store(src, "slot", bad)
        self.assertEqual(heap.load(src, "slot"), good)

    def test_bad_slot_names_rejected(self):
        heap = ObjectHeap()
        src = heap.alloc()
        for bad in ("", 7, None):
            with self.assertRaises(SlotError):
                heap.store(src, bad, None)
            with self.assertRaises(SlotError):
                heap.load(src, bad)

    def test_load_from_dead_source_rejected(self):
        heap = ObjectHeap()
        src = heap.alloc()
        heap.store(src, "slot", None)
        heap.collect()
        with self.assertRaises(UnknownObject):
            heap.load(src, "slot")


if __name__ == "__main__":
    unittest.main()
