"""ObjectStore 行为基线：引用计数、连边、回收顺序、回调重入与统计。"""

import unittest

from objlife import LinkError, ObjectStore, RefCountError, UnknownObject


class Recorder:
    """销毁回调记录器，记下每次回调拿到的 (oid, kind, payload)。"""

    def __init__(self):
        self.died = []

    def __call__(self, store, oid, kind, payload):
        self.died.append((oid, kind, payload))


class TestCreate(unittest.TestCase):

    def test_create_counts_one_reference(self):
        store = ObjectStore()
        oid = store.create("page", {"name": "home"})
        self.assertTrue(store.alive(oid))
        self.assertEqual(store.refcount(oid), 1)
        self.assertEqual(store.retain_count(oid), 1)
        self.assertEqual(store.kind(oid), "page")
        self.assertEqual(store.payload(oid), {"name": "home"})

    def test_default_kind_and_payload(self):
        store = ObjectStore()
        oid = store.create()
        self.assertEqual(store.kind(oid), "object")
        self.assertIsNone(store.payload(oid))

    def test_oids_never_reused(self):
        store = ObjectStore()
        first = store.create()
        second = store.create()
        self.assertGreater(second, first)
        store.release(first)
        self.assertGreater(store.create(), second)


class TestExternalRefs(unittest.TestCase):

    def test_retain_and_release(self):
        store = ObjectStore()
        oid = store.create()
        self.assertEqual(store.retain(oid), 2)
        self.assertEqual(store.release(oid), 1)
        self.assertEqual(store.release(oid), 0)
        self.assertFalse(store.alive(oid))

    def test_release_without_reference_rejected(self):
        store = ObjectStore()
        holder = store.create("holder")
        target = store.create("target")
        store.link(holder, target)
        store.release(target)  # target 只剩 holder 那条边
        self.assertTrue(store.alive(target))
        with self.assertRaises(RefCountError):
            store.release(target)
        self.assertEqual(store.refcount(target), 1)

    def test_ops_on_unknown_object(self):
        store = ObjectStore()
        live = store.create()
        for call in (store.retain, store.release, store.refcount,
                     store.retain_count, store.kind, store.payload,
                     store.out_links):
            with self.assertRaises(UnknownObject):
                call(404)
        with self.assertRaises(UnknownObject):
            store.link(404, live)
        with self.assertRaises(UnknownObject):
            store.link(live, 404)

    def test_dead_object_is_gone(self):
        store = ObjectStore()
        oid = store.create()
        store.release(oid)
        self.assertFalse(store.alive(oid))
        with self.assertRaises(UnknownObject):
            store.refcount(oid)


class TestLinks(unittest.TestCase):

    def test_link_and_unlink_counts(self):
        store = ObjectStore()
        a = store.create("a")
        b = store.create("b")
        self.assertEqual(store.link(a, b), 2)
        self.assertEqual(store.out_links(a), [b])
        self.assertEqual(store.unlink(a, b), 1)
        self.assertEqual(store.out_links(a), [])
        self.assertTrue(store.alive(b))

    def test_self_link_rejected(self):
        store = ObjectStore()
        a = store.create()
        with self.assertRaises(LinkError):
            store.link(a, a)
        self.assertEqual(store.refcount(a), 1)

    def test_duplicate_link_rejected(self):
        store = ObjectStore()
        a = store.create()
        b = store.create()
        store.link(a, b)
        with self.assertRaises(LinkError):
            store.link(a, b)
        self.assertEqual(store.refcount(b), 2)

    def test_unlink_missing_edge_rejected(self):
        store = ObjectStore()
        a = store.create()
        b = store.create()
        with self.assertRaises(LinkError):
            store.unlink(a, b)

    def test_unlink_reaps_target_at_zero(self):
        store = ObjectStore()
        a = store.create()
        b = store.create()
        store.link(a, b)
        store.release(b)  # b 只剩 a 的边
        store.unlink(a, b)
        self.assertFalse(store.alive(b))

    def test_out_links_snapshot_is_copy(self):
        store = ObjectStore()
        a = store.create()
        b = store.create()
        store.link(a, b)
        snapshot = store.out_links(a)
        snapshot.append(999)
        self.assertEqual(store.out_links(a), [b])


class TestReap(unittest.TestCase):

    def test_hook_receives_identity(self):
        rec = Recorder()
        store = ObjectStore(on_destroy=rec)
        oid = store.create("page", {"name": "home"})
        store.release(oid)
        self.assertEqual(rec.died, [(oid, "page", {"name": "home"})])

    def test_chain_dies_from_root_down(self):
        rec = Recorder()
        store = ObjectStore(rec)
        a = store.create("a")
        b = store.create("b")
        c = store.create("c")
        store.link(a, b)
        store.link(b, c)
        store.release(b)
        store.release(c)
        store.release(a)  # a 归零，出边连锁带走 b、c
        self.assertEqual([oid for oid, _, _ in rec.died], [a, b, c])
        self.assertEqual(store.ids(), [])
        self.assertEqual(store.stats()["destroyed"], 3)
        self.assertEqual(store.stats()["links"], 0)

    def test_shared_child_survives(self):
        rec = Recorder()
        store = ObjectStore(rec)
        left = store.create("left")
        right = store.create("right")
        shared = store.create("shared")
        store.link(left, shared)
        store.link(right, shared)
        store.release(shared)  # 靠两条边活着
        store.release(left)    # left 死，shared 少一条边还活着
        self.assertFalse(store.alive(left))
        self.assertTrue(store.alive(shared))
        self.assertEqual(store.refcount(shared), 1)
        self.assertEqual([oid for oid, _, _ in rec.died], [left])

    def test_hook_may_reenter_container(self):
        seen = []

        def hook(store, oid, kind, payload):
            seen.append((oid, kind))
            if kind == "victim":
                store.retain(spare)          # 回调里动别的对象
                scratch = store.create("scratch")
                store.release(scratch)       # 回调里再释放，触发嵌套回收

        store = ObjectStore()
        spare = store.create("spare")
        store.set_hook(hook)
        victim = store.create("victim")
        store.release(victim)

        self.assertEqual(seen[0], (victim, "victim"))
        self.assertEqual(len(seen), 2)
        self.assertNotEqual(seen[1][0], victim)
        self.assertTrue(store.alive(spare))
        self.assertEqual(store.retain_count(spare), 2)
        self.assertFalse(store.alive(victim))

    def test_hook_error_still_detaches_links(self):
        def boom(store, oid, kind, payload):
            raise RuntimeError("boom on %s" % kind)

        store = ObjectStore(on_destroy=boom)
        child = store.create("child")
        parent = store.create("parent")
        store.link(parent, child)
        store.release(child)  # child 只剩 parent 那条边
        with self.assertRaises(RuntimeError):
            store.release(parent)
        self.assertFalse(store.alive(parent))
        self.assertFalse(store.alive(child))  # 回调炸了，出边照样摘
        stats = store.stats()
        self.assertEqual(stats["alive"], 0)
        self.assertEqual(stats["links"], 0)
        fresh = store.create("fresh")  # 容器还能接着用
        self.assertTrue(store.alive(fresh))


class TestRootsAndStats(unittest.TestCase):

    def test_roots_are_objects_with_external_refs(self):
        store = ObjectStore()
        a = store.create()
        b = store.create()
        store.link(a, b)
        store.release(b)
        self.assertEqual(store.roots(), [a])
        store.release(a)
        self.assertEqual(store.roots(), [])

    def test_stats_track_creation_and_destruction(self):
        store = ObjectStore()
        a = store.create()
        b = store.create()
        store.link(a, b)
        stats = store.stats()
        for key in ("alive", "created", "destroyed", "links"):
            self.assertIn(key, stats)
        self.assertEqual(stats["alive"], 2)
        self.assertEqual(stats["created"], 2)
        self.assertEqual(stats["destroyed"], 0)
        self.assertEqual(stats["links"], 1)
        store.release(b)
        store.release(a)
        stats = store.stats()
        self.assertEqual(stats["alive"], 0)
        self.assertEqual(stats["destroyed"], 2)

    def test_set_hook_none_disables_callback(self):
        def boom(store, oid, kind, payload):
            raise AssertionError("不该被调到")

        store = ObjectStore(on_destroy=boom)
        store.set_hook(None)
        oid = store.create()
        store.release(oid)
        self.assertFalse(store.alive(oid))


class TestCurrentCycleBehaviour(unittest.TestCase):
    """锁住现状：没有外部引用的环照样活着，回收只认计数归零。"""

    def test_cycle_survives_without_scan(self):
        store = ObjectStore()
        a = store.create("a")
        b = store.create("b")
        store.link(a, b)
        store.link(b, a)
        store.release(a)
        store.release(b)
        self.assertEqual(store.ids(), [a, b])
        self.assertEqual(store.refcount(a), 1)


if __name__ == "__main__":
    unittest.main()
