"""Baseline tests that pin down the current, naive behaviour.

Nothing in this file may change: it is the contract the future
implementation has to keep satisfying.
"""

import unittest

from treaplib.seq import ListLike


class ConstructionTest(unittest.TestCase):
    def test_empty(self):
        seq = ListLike()
        self.assertEqual(len(seq), 0)
        self.assertEqual(seq.snapshot(), [])

    def test_from_iterable(self):
        seq = ListLike([3, 1, 2])
        self.assertEqual(len(seq), 3)
        self.assertEqual(seq.snapshot(), [3, 1, 2])

    def test_constructor_copies_input(self):
        source = [1, 2, 3]
        seq = ListLike(source)
        source.append(99)
        self.assertEqual(seq.snapshot(), [1, 2, 3])


class AccessTest(unittest.TestCase):
    def test_at(self):
        seq = ListLike([10, 20, 30])
        self.assertEqual(seq.at(0), 10)
        self.assertEqual(seq.at(2), 30)

    def test_set(self):
        seq = ListLike([10, 20, 30])
        seq.set(1, 99)
        self.assertEqual(seq.snapshot(), [10, 99, 30])

    def test_iteration(self):
        seq = ListLike([1, 2, 3])
        self.assertEqual(list(seq), [1, 2, 3])

    def test_equality(self):
        self.assertEqual(ListLike([1, 2]), ListLike([1, 2]))
        self.assertNotEqual(ListLike([1, 2]), ListLike([2, 1]))


class InsertEraseTest(unittest.TestCase):
    def test_insert_at_front(self):
        seq = ListLike([2, 3])
        seq.insert(0, 1)
        self.assertEqual(seq.snapshot(), [1, 2, 3])

    def test_insert_at_back(self):
        seq = ListLike([1, 2])
        seq.insert(2, 3)
        self.assertEqual(seq.snapshot(), [1, 2, 3])

    def test_insert_in_middle(self):
        seq = ListLike([1, 3])
        seq.insert(1, 2)
        self.assertEqual(seq.snapshot(), [1, 2, 3])

    def test_erase(self):
        seq = ListLike([1, 2, 3])
        seq.erase(1)
        self.assertEqual(seq.snapshot(), [1, 3])

    def test_erase_to_empty(self):
        seq = ListLike([7])
        seq.erase(0)
        self.assertEqual(len(seq), 0)
        self.assertEqual(seq.snapshot(), [])


class ReverseRangeTest(unittest.TestCase):
    def test_middle_range(self):
        seq = ListLike([1, 2, 3, 4, 5])
        seq.reverse_range(1, 4)
        self.assertEqual(seq.snapshot(), [1, 4, 3, 2, 5])

    def test_whole_range(self):
        seq = ListLike([1, 2, 3])
        seq.reverse_range(0, 3)
        self.assertEqual(seq.snapshot(), [3, 2, 1])

    def test_empty_range(self):
        seq = ListLike([1, 2, 3])
        seq.reverse_range(1, 1)
        self.assertEqual(seq.snapshot(), [1, 2, 3])

    def test_single_element_range(self):
        seq = ListLike([1, 2, 3])
        seq.reverse_range(1, 2)
        self.assertEqual(seq.snapshot(), [1, 2, 3])


class SpliceTest(unittest.TestCase):
    def test_splice_returns_and_removes(self):
        seq = ListLike([1, 2, 3, 4, 5])
        taken = seq.splice(1, 3)
        self.assertEqual(taken, [2, 3])
        self.assertEqual(seq.snapshot(), [1, 4, 5])

    def test_splice_empty_range(self):
        seq = ListLike([1, 2, 3])
        taken = seq.splice(2, 2)
        self.assertEqual(taken, [])
        self.assertEqual(seq.snapshot(), [1, 2, 3])

    def test_splice_everything(self):
        seq = ListLike([1, 2])
        taken = seq.splice(0, 2)
        self.assertEqual(taken, [1, 2])
        self.assertEqual(seq.snapshot(), [])


class IndexErrorTest(unittest.TestCase):
    def test_at_out_of_range(self):
        seq = ListLike([1, 2])
        with self.assertRaises(IndexError):
            seq.at(2)
        with self.assertRaises(IndexError):
            seq.at(-1)

    def test_set_out_of_range(self):
        seq = ListLike([1, 2])
        with self.assertRaises(IndexError):
            seq.set(5, 0)

    def test_erase_out_of_range(self):
        seq = ListLike([1, 2])
        with self.assertRaises(IndexError):
            seq.erase(9)

    def test_at_on_empty(self):
        with self.assertRaises(IndexError):
            ListLike().at(0)

    def test_insert_out_of_range(self):
        seq = ListLike([1, 2])
        with self.assertRaises(IndexError):
            seq.insert(3, 0)
        with self.assertRaises(IndexError):
            seq.insert(-1, 0)

    def test_bad_range(self):
        seq = ListLike([1, 2, 3])
        with self.assertRaises(IndexError):
            seq.reverse_range(2, 1)
        with self.assertRaises(IndexError):
            seq.splice(0, 4)


if __name__ == "__main__":
    unittest.main()
