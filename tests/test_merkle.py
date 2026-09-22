import hashlib
import multiprocessing
import os
import random
import time
import unittest

from sealstore import (
    MerkleTree,
    SealError,
    empty_root,
    leaf_hash,
    proof_from_bytes,
    verify_consistency,
    verify_inclusion,
)
from sealstore.merkle import (
    ConsistencyProof,
    InclusionProof,
    _commit,
    _TAG,
    _node_hash,
)


EMPTY_ROOT = "de63c32025b09a380cab2b62537f8aa1979f4cfcf11d048a191d9079f050b335"
ROOT_OF_THREE = "47f0ddc157597c74902dbe31cd38fa91304573f94f8234a4312c8cf708a5e2f2"


def records(count):
    return [{"i": i, "name": "记录%d" % i, "v": i * 3 % 17} for i in range(count)]


def naive_root(leaves):
    """Independent RFC 6962 tree hash, written separately from the tree."""
    if not leaves:
        return hashlib.sha256(_TAG + b"empty").digest()

    def fold(piece):
        if len(piece) == 1:
            return piece[0]
        cut = 1 << ((len(piece) - 1).bit_length() - 1)
        return _node_hash(fold(piece[:cut]), fold(piece[cut:]))

    return _commit(len(leaves), fold(leaves))


def expected_recomputed(size, index):
    """The exact hash count update() should report."""
    level = 1
    ancestors = 0
    while 1 << level <= size:
        block = 1 << level
        parent = index // block
        if (parent + 1) * block <= size:
            ancestors += 1
        level += 1
    return 1 + ancestors + bin(size).count("1") - 1


class EmptyTreeTests(unittest.TestCase):
    def test_empty_tree_has_a_fixed_public_root(self):
        tree = MerkleTree()
        self.assertEqual(tree.root_bytes(), empty_root())
        self.assertEqual(tree.root(), empty_root().hex())
        self.assertEqual(tree.root(), EMPTY_ROOT)
        self.assertEqual(len(tree), 0)
        self.assertEqual(tree.height, 0)

    def test_empty_tree_mints_no_proofs(self):
        tree = MerkleTree()
        with self.assertRaises(IndexError):
            tree.inclusion_proof(0)
        with self.assertRaises(SealError):
            tree.consistency_proof(1)

    def test_nothing_verifies_against_the_empty_root(self):
        proof = InclusionProof(0, 1, [])
        self.assertFalse(verify_inclusion(empty_root(), {"i": 0}, proof))


class RootTests(unittest.TestCase):
    def test_root_is_pinned_for_three_records(self):
        tree = MerkleTree(records(3))
        self.assertEqual(tree.root(), ROOT_OF_THREE)
        self.assertEqual(tree.root(), tree.root_bytes().hex())

    def test_root_matches_independent_tree_hash_for_many_sizes(self):
        sizes = list(range(0, 65)) + [127, 128, 129, 255, 256, 257, 1000]
        for size in sizes:
            data = records(size)
            tree = MerkleTree(data)
            self.assertEqual(
                tree.root_bytes(), naive_root([leaf_hash(r) for r in data])
            )

    def test_incremental_appends_match_batch_construction(self):
        data = records(137)
        batch = MerkleTree(data)
        grown = MerkleTree()
        roots = [grown.root()]
        for record in data:
            grown.append(record)
            roots.append(grown.root())
        self.assertEqual(grown.root(), batch.root())
        self.assertEqual(len(grown), len(batch))
        self.assertNotEqual(roots[-1], roots[0])

    def test_append_only_adds_aligned_nodes(self):
        tree = MerkleTree(records(6))
        self.assertEqual([len(level) for level in tree.levels], [6, 3, 1])
        tree.append({"i": 6})
        self.assertEqual([len(level) for level in tree.levels], [7, 3, 1])
        tree.append({"i": 7})
        self.assertEqual([len(level) for level in tree.levels], [8, 4, 2, 1])

    def test_odd_tail_is_promoted_not_duplicated(self):
        data = records(5)
        tree = MerkleTree(data)
        # Level 1 only stores complete aligned pairs; the lone fifth leaf
        # is promoted virtually when the root is folded, never duplicated.
        self.assertEqual([len(level) for level in tree.levels], [5, 2, 1])
        self.assertEqual(tree.levels[0][4], leaf_hash(data[4]))
        self.assertEqual(tree.root_bytes(), naive_root([leaf_hash(r) for r in data]))


class InclusionProofTests(unittest.TestCase):
    def test_single_leaf_has_empty_path(self):
        record = {"i": 0}
        tree = MerkleTree([record])
        proof = tree.inclusion_proof(0)
        self.assertEqual(proof.path, [])
        self.assertTrue(verify_inclusion(tree.root(), record, proof))

    def test_pinned_proof_for_last_leaf_of_three(self):
        data = records(3)
        tree = MerkleTree(data)
        proof = tree.inclusion_proof(2)
        self.assertEqual(
            [node.hex() for node in proof.path],
            ["6b45c60f4e36981699c95a89874fa85abbd6e171cd8604b4c8c07ad6e8a23603"],
        )
        self.assertTrue(verify_inclusion(tree.root_bytes(), data[2], proof))

    def test_every_position_verifies_for_small_trees(self):
        for size in range(1, 70):
            data = records(size)
            tree = MerkleTree(data)
            for index in range(size):
                proof = tree.inclusion_proof(index)
                self.assertTrue(
                    verify_inclusion(tree.root(), data[index], proof),
                    (size, index),
                )
                self.assertLessEqual(len(proof.path), max(1, size.bit_length()))

    def test_hex_root_and_raw_root_are_both_accepted(self):
        data = records(9)
        tree = MerkleTree(data)
        proof = tree.inclusion_proof(4)
        self.assertTrue(verify_inclusion(tree.root(), data[4], proof))
        self.assertTrue(verify_inclusion(tree.root_bytes(), data[4], proof))

    def test_out_of_range_indexes_are_refused(self):
        tree = MerkleTree(records(3))
        for bad in (-1, 3, 99):
            with self.assertRaises(IndexError):
                tree.inclusion_proof(bad)

    def test_constructing_an_invalid_proof_is_refused(self):
        with self.assertRaises(SealError):
            InclusionProof(0, 0, [])
        with self.assertRaises(SealError):
            InclusionProof(-1, 2, [b"x" * 32])
        with self.assertRaises(SealError):
            InclusionProof(2, 2, [b"x" * 32])
        with self.assertRaises(SealError):
            InclusionProof(0, 2, [b"too-short"])


class ConsistencyProofTests(unittest.TestCase):
    def test_pinned_proof_from_one_to_three(self):
        tree = MerkleTree(records(3))
        proof = tree.consistency_proof(1)
        self.assertEqual(
            [node.hex() for node in proof.path],
            [
                "60902bf51f91d927ef7db748a485cc77838702a2e84106978ec82b45ac08298d",
                "83aae3e680b9b7736f3fdd34a80ba659ae9345a4341074f79787464584350775",
                "864c3e7782503f7a4fd655b2c9c663fe997f7448679b8f18801bae0dc7dcb1a7",
            ],
        )
        old_root = MerkleTree(records(1)).root()
        self.assertTrue(verify_consistency(old_root, tree.root(), proof))

    def test_all_prefixes_are_consistent(self):
        for size in range(2, 70):
            data = records(size)
            tree = MerkleTree(data)
            leaves = [leaf_hash(record) for record in data]
            for old in range(1, size):
                old_root = naive_root(leaves[:old])
                proof = tree.consistency_proof(old)
                self.assertTrue(
                    verify_consistency(old_root, tree.root_bytes(), proof),
                    (old, size),
                )

    def test_equal_size_is_trivially_consistent(self):
        tree = MerkleTree(records(4))
        proof = ConsistencyProof(4, 4, [])
        self.assertTrue(verify_consistency(tree.root(), tree.root(), proof))
        # Same size but different content cannot be called an extension.
        different = [dict(r) for r in records(4)]
        different[0] = {"i": 0, "v": 999999}
        other_tree = MerkleTree(different)
        other_proof = ConsistencyProof(4, 4, [])
        self.assertFalse(
            verify_consistency(tree.root(), other_tree.root(), other_proof)
        )

    def test_consistency_minting_validates_sizes(self):
        tree = MerkleTree(records(3))
        for bad in (0, 3, 4):
            with self.assertRaises(SealError):
                tree.consistency_proof(bad)

    def test_constructing_an_invalid_consistency_proof_is_refused(self):
        with self.assertRaises(SealError):
            ConsistencyProof(0, 3, [b"x" * 32])
        with self.assertRaises(SealError):
            ConsistencyProof(4, 3, [b"x" * 32])


class UpdateTests(unittest.TestCase):
    SIZES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 100, 127, 128, 129]

    def test_update_matches_full_rebuild_and_reports_path_cost(self):
        for size in self.SIZES:
            data = records(size)
            indexes = {0, size - 1, size // 2, size // 3}
            for index in indexes:
                tree = MerkleTree(data)
                changed = [dict(record) for record in data]
                changed[index] = {"i": index, "name": "改写", "v": -1}
                rebuilt = MerkleTree(changed)
                count = tree.update(index, changed[index])
                self.assertEqual(tree.root(), rebuilt.root(), (size, index))
                self.assertEqual(count, expected_recomputed(size, index))
                height = 1 if size == 1 else (size - 1).bit_length()
                self.assertLessEqual(count, 2 * height, (size, index))

    def test_update_touches_only_the_path(self):
        data = records(9)
        tree = MerkleTree(data)
        before = [list(level) for level in tree.levels]
        tree.update(2, {"i": 2, "v": 9999})
        changed_cells = []
        for depth, level in enumerate(tree.levels):
            for cell, value in enumerate(level):
                if value != before[depth][cell]:
                    changed_cells.append((depth, cell))
        self.assertEqual(changed_cells, [(0, 2), (1, 1), (2, 0), (3, 0)])

    def test_update_out_of_range_raises_index_error(self):
        tree = MerkleTree(records(3))
        for bad in (-1, 3, 10):
            with self.assertRaises(IndexError):
                tree.update(bad, {"i": bad})

    def test_proofs_verify_after_update(self):
        data = records(7)
        changed = [dict(r) for r in data]
        changed[4] = {"i": 4, "v": 77}
        tree = MerkleTree(data)
        tree.update(4, changed[4])
        proof = tree.inclusion_proof(4)
        self.assertTrue(verify_inclusion(tree.root(), changed[4], proof))


class SerialisationTests(unittest.TestCase):
    def test_inclusion_round_trip(self):
        data = records(11)
        tree = MerkleTree(data)
        proof = tree.inclusion_proof(7)
        restored = proof_from_bytes(proof.to_bytes())
        self.assertIsInstance(restored, InclusionProof)
        self.assertEqual(restored, proof)
        self.assertTrue(verify_inclusion(tree.root(), data[7], restored))

    def test_consistency_round_trip(self):
        data = records(11)
        tree = MerkleTree(data)
        proof = tree.consistency_proof(5)
        old_root = MerkleTree(records(5)).root()
        restored = proof_from_bytes(proof.to_bytes())
        self.assertIsInstance(restored, ConsistencyProof)
        self.assertEqual(restored, proof)
        self.assertTrue(verify_consistency(old_root, tree.root(), restored))

    def test_payload_is_versioned_binary(self):
        proof = InclusionProof(1, 4, [os.urandom(32)])
        raw = proof.to_bytes()
        self.assertTrue(raw.startswith(b"sealstore-proof/v1/"))
        self.assertIsInstance(raw, bytes)

    def test_garbage_payloads_raise(self):
        good = MerkleTree(records(4)).inclusion_proof(0).to_bytes()
        tampered_kind = b"sealstore-proof/v1/X" + good[len(b"sealstore-proof/v1/I"):]
        for garbage in (
            b"",
            b"not a sealstore proof",
            tampered_kind,
            good[:-1],
            good + b"x",
            good[:20],
        ):
            with self.assertRaises(SealError):
                proof_from_bytes(garbage)


def _verify_in_other_process(payload, count, index):
    proof = proof_from_bytes(payload)
    record = records(count)[index]
    tree = MerkleTree(records(count))
    return verify_inclusion(tree.root(), record, proof)


class CrossProcessTests(unittest.TestCase):
    def test_proof_reloaded_in_a_spawned_process_verifies(self):
        context = multiprocessing.get_context("spawn")
        proof = MerkleTree(records(13)).inclusion_proof(10)
        with context.Pool(1) as pool:
            result = pool.apply(
                _verify_in_other_process, (proof.to_bytes(), 13, 10)
            )
        self.assertTrue(result)


class RandomDifferentialTests(unittest.TestCase):
    SEED = 20260922

    def test_cross_size_forgeries_are_rejected(self):
        # An odd-tail promotion makes a path for size n also evaluate
        # structurally for smaller sizes; the size-bound root must stop
        # a proof replayed under a different size.
        for n in range(2, 90):
            data = records(n)
            tree = MerkleTree(data)
            roots = [MerkleTree(data[:m]).root_bytes() for m in range(n + 1)]
            for index in range(n):
                proof = tree.inclusion_proof(index)
                for fake_size in range(index + 1, n + 2):
                    if fake_size == n:
                        continue
                    forged = InclusionProof(index, fake_size, list(proof.path))
                    self.assertFalse(
                        verify_inclusion(tree.root_bytes(), data[index], forged),
                        ("inclusion", n, index, fake_size),
                    )
            for old in range(1, n):
                consistency = tree.consistency_proof(old)
                for fake_size in range(old + 1, n + 2):
                    if fake_size == n:
                        continue
                    forged = ConsistencyProof(old, fake_size, list(consistency.path))
                    self.assertFalse(
                        verify_consistency(
                            roots[old], tree.root_bytes(), forged
                        ),
                        ("consistency", old, n, fake_size),
                    )

    def test_random_append_only_history_stays_consistent(self):
        rng = random.Random(self.SEED + 2)
        tree = MerkleTree()
        snapshots = []
        for _ in range(120):
            tree.append({"i": len(tree), "v": rng.randrange(1 << 30)})
            if rng.random() < 0.4:
                snapshots.append((len(tree), tree.root_bytes()))
        for old_size, old_root in snapshots:
            proof = tree.consistency_proof(old_size)
            self.assertTrue(
                verify_consistency(old_root, tree.root_bytes(), proof),
                old_size,
            )

    def test_random_appends_and_updates_against_full_rebuild(self):
        rng = random.Random(self.SEED)
        size = rng.randrange(1, 400)
        data = [
            {"i": i, "v": rng.randrange(1 << 30), "tag": rng.choice(["a", "b", "c"])}
            for i in range(size)
        ]
        tree = MerkleTree(data)
        for _ in range(60):
            action = rng.random()
            if action < 0.6:
                index = rng.randrange(len(data))
                new_record = {"i": index, "v": rng.randrange(1 << 30), "tag": "改"}
                count = tree.update(index, new_record)
                data[index] = new_record
                rebuilt = MerkleTree(data)
                self.assertEqual(tree.root(), rebuilt.root())
                height = 1 if len(data) == 1 else (len(data) - 1).bit_length()
                self.assertLessEqual(count, 2 * height)
                proof = tree.inclusion_proof(index)
                self.assertTrue(verify_inclusion(tree.root(), new_record, proof))
            else:
                record = {"i": len(data), "v": rng.randrange(1 << 30), "tag": "新"}
                data.append(record)
                tree.append(record)
            self.assertEqual(
                tree.root_bytes(), naive_root([leaf_hash(r) for r in data])
            )

        # Prefix roots of the final data are structurally consistent,
        # even after intervening in-place updates.
        leaves = [leaf_hash(r) for r in data]
        for old in {1, len(data) // 2, len(data) - 1}:
            if 0 < old < len(data):
                old_root = naive_root(leaves[:old])
                proof = tree.consistency_proof(old)
                self.assertTrue(
                    verify_consistency(old_root, tree.root_bytes(), proof)
                )

    def test_random_tampered_records_and_proofs_are_rejected(self):
        rng = random.Random(self.SEED + 1)
        for _ in range(40):
            size = rng.randrange(1, 80)
            data = records(size)
            tree = MerkleTree(data)
            index = rng.randrange(size)
            proof = tree.inclusion_proof(index)

            tampered_record = dict(data[index])
            tampered_record["v"] = rng.randrange(1000, 100000)
            self.assertFalse(
                verify_inclusion(tree.root(), tampered_record, proof)
            )
            self.assertFalse(
                verify_inclusion(os.urandom(32), data[index], proof)
            )

            if proof.path:
                bad = InclusionProof(
                    proof.leaf_index,
                    proof.size,
                    [b for b in proof.path],
                )
                flip_at = rng.randrange(len(bad.path))
                raw = bytearray(bad.path[flip_at])
                raw[rng.randrange(32)] ^= 1 << rng.randrange(8)
                bad.path[flip_at] = bytes(raw)
                self.assertFalse(verify_inclusion(tree.root(), data[index], bad))

            if size > 1:
                old = rng.randrange(1, size)
                consistency = tree.consistency_proof(old)
                old_root = MerkleTree(records(old)).root()
                self.assertTrue(
                    verify_consistency(old_root, tree.root(), consistency)
                )
                # A tree that rewrote history instead of appending fails.
                reordered = [dict(r) for r in data]
                reordered[0], reordered[-1] = reordered[-1], reordered[0]
                self.assertFalse(
                    verify_consistency(
                        old_root, MerkleTree(reordered).root(), consistency
                    )
                )


class PerformanceTests(unittest.TestCase):
    def test_hundred_thousand_builds_under_five_seconds(self):
        data = [{"i": i, "v": i % 97} for i in range(100_000)]
        start = time.perf_counter()
        tree = MerkleTree(data)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 5.0, "build took %.2fs" % elapsed)
        self.assertEqual(len(tree), 100_000)

    def test_single_update_is_sub_millisecond_and_path_bounded(self):
        size = 100_000
        tree = MerkleTree([{"i": i} for i in range(size)])
        height = (size - 1).bit_length()
        timings = []
        for index in (0, size - 1, size // 2, 12345):
            start = time.perf_counter()
            count = tree.update(index, {"i": index, "v": 1})
            timings.append(time.perf_counter() - start)
            self.assertLessEqual(count, 2 * height)
            self.assertEqual(count, expected_recomputed(size, index))
        self.assertLess(min(timings), 0.001, "fastest update took %.4fs" % min(timings))


if __name__ == "__main__":
    unittest.main()
