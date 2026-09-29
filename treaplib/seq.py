"""Naive, array-backed sequence used as the starting point.

The only data structure here is an ordinary Python list.  Every operation
is written in the most direct way possible:

* ``insert`` / ``erase`` shift the whole tail of the list;
* ``reverse_range`` swaps elements two by two;
* everything else just indexes or slices the list.

This module is intentionally simple.  It is kept around as the reference
path every future implementation must agree with.
"""


class ListLike(object):
    """A thin sequence wrapper around a Python list."""

    def __init__(self, items=None):
        if items is None:
            self._data = []
        else:
            self._data = list(items)

    # -- sizing -----------------------------------------------------------

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __eq__(self, other):
        if isinstance(other, ListLike):
            return self._data == other._data
        return NotImplemented

    def __repr__(self):
        return "ListLike(" + repr(self._data) + ")"

    # -- access -----------------------------------------------------------

    def at(self, i):
        self._check_index(i)
        return self._data[i]

    def set(self, i, value):
        self._check_index(i)
        self._data[i] = value

    def snapshot(self):
        """Return a plain-list copy of the current contents."""
        return list(self._data)

    # -- mutation ---------------------------------------------------------

    def insert(self, i, value):
        # Any position from 0 through len() is a legal insertion point.
        self._check_position(i)
        self._data.insert(i, value)

    def erase(self, i):
        self._check_index(i)
        del self._data[i]

    def reverse_range(self, left, right):
        self._check_slice(left, right)
        while left < right - 1:
            a = self._data[left]
            b = self._data[right - 1]
            self._data[left] = b
            self._data[right - 1] = a
            left += 1
            right -= 1

    def splice(self, left, right):
        """Remove ``[left, right)`` and return the removed slice as a list."""
        self._check_slice(left, right)
        taken = self._data[left:right]
        self._data[left:right] = []
        return taken

    # -- checks -----------------------------------------------------------

    def _check_index(self, i):
        if not isinstance(i, int) or isinstance(i, bool):
            raise IndexError("index must be an int, got " + repr(i))
        if i < 0 or i >= len(self._data):
            raise IndexError("index out of range: " + repr(i))

    def _check_position(self, i):
        if not isinstance(i, int) or isinstance(i, bool):
            raise IndexError("position must be an int, got " + repr(i))
        if i < 0 or i > len(self._data):
            raise IndexError("position out of range: " + repr(i))

    def _check_slice(self, left, right):
        if not isinstance(left, int) or isinstance(left, bool):
            raise IndexError("left must be an int, got " + repr(left))
        if not isinstance(right, int) or isinstance(right, bool):
            raise IndexError("right must be an int, got " + repr(right))
        if left < 0 or right > len(self._data) or left > right:
            raise IndexError(
                "bad range [" + repr(left) + ", " + repr(right) + ")"
            )
