"""Baseline bitmap for the bitrange package.

The current implementation is deliberately as plain as possible.  A bitmap is
just a fixed-size list of single characters ("0" and "1").  Setting or clearing
a bit writes one character in that list.  Every range query -- whether a span
is all ones, all zeros, how many ones it holds, or where the next zero/one is --
walks the span bit by bit.  There is no interval tree, no node bookkeeping and
no lazy tags.
"""


class BitError(Exception):
    """Base class for every error raised by bitrange."""


class FlatBits(object):
    """A flat, per-bit bitmap made of a list of characters.

    The bitmap has a fixed size chosen at construction time.  Positions are
    zero based integers in ``[0, size)``.  The storage is a plain list whose
    entries are the characters ``"0"`` or ``"1"``.
    """

    def __init__(self, size):
        if not isinstance(size, int):
            raise TypeError("size must be an int")
        if size < 0:
            raise BitError("size must be non-negative")
        self._size = size
        self._cells = ["0"] * size

    @property
    def size(self):
        """Number of bits in the bitmap."""
        return self._size

    def _check_pos(self, index):
        if not isinstance(index, int):
            raise TypeError("index must be an int")
        if index < 0 or index >= self._size:
            raise BitError("index out of range: %r" % (index,))

    def _check_span(self, lo, hi):
        if not isinstance(lo, int) or not isinstance(hi, int):
            raise TypeError("lo and hi must be ints")
        if lo < 0 or hi > self._size or lo > hi:
            raise BitError("invalid span: [%r, %r)" % (lo, hi))

    def set(self, index):
        """Set the single bit at ``index`` to one."""
        self._check_pos(index)
        self._cells[index] = "1"

    def clear(self, index):
        """Clear the single bit at ``index`` to zero."""
        self._check_pos(index)
        self._cells[index] = "0"

    def get(self, index):
        """Return 1 or 0 for the bit at ``index``."""
        self._check_pos(index)
        return 1 if self._cells[index] == "1" else 0

    def is_all_one(self, lo, hi):
        """Return True when every bit in ``[lo, hi)`` is one."""
        self._check_span(lo, hi)
        for index in range(lo, hi):
            if self._cells[index] != "1":
                return False
        return True

    def is_all_zero(self, lo, hi):
        """Return True when every bit in ``[lo, hi)`` is zero."""
        self._check_span(lo, hi)
        for index in range(lo, hi):
            if self._cells[index] != "0":
                return False
        return True

    def count_one(self, lo, hi):
        """Count the ones inside ``[lo, hi)`` by walking the span."""
        self._check_span(lo, hi)
        total = 0
        for index in range(lo, hi):
            if self._cells[index] == "1":
                total += 1
        return total

    def count_all_one(self):
        """Count every one in the bitmap."""
        return self.count_one(0, self._size)

    def find_next_zero(self, start):
        """Index of the first zero at or after ``start``, or -1 if none."""
        self._check_pos(start)
        for index in range(start, self._size):
            if self._cells[index] == "0":
                return index
        return -1

    def find_next_one(self, start):
        """Index of the first one at or after ``start``, or -1 if none."""
        self._check_pos(start)
        for index in range(start, self._size):
            if self._cells[index] == "1":
                return index
        return -1
