"""Baseline single-node committer for the commitx package.

The only thing commitx ships today is LocalCommit.  It applies a change
directly to its own in-memory state: there is no coordinator, no
participants, no voting, no prepare phase and no recovery log.  A single
apply call mutates the state and records the change in a flat list.
"""


class CommitError(Exception):
    """Base class for errors raised by commitx."""


class CommitConflict(CommitError):
    """Raised when a change conflicts with existing state."""


class LocalCommit(object):
    """A purely local, single-node committer.

    This is the most naive implementation possible: apply mutates the local
    state in place.  There is no two-phase protocol, no coordination with any
    other node and no way to recover a partially applied change, because
    nothing here can ever be partial.
    """

    def __init__(self):
        self._state = {}
        self._applied = []

    def apply(self, change):
        """Apply a single change to the local state and return its key.

        A change is a mapping with at least a key and a value.  If the key is
        already present the change is rejected: the baseline never overwrites.
        """
        if not isinstance(change, dict):
            raise CommitError("change must be a mapping")
        if "key" not in change:
            raise CommitError("change must contain a key")
        key = change["key"]
        if key in self._state:
            raise CommitConflict("key already present: %r" % (key,))
        value = change.get("value")
        self._state[key] = value
        self._applied.append(key)
        return key

    def read(self, key, default=None):
        """Read a value by key from the local state."""
        return self._state.get(key, default)

    def keys(self):
        """Return the keys currently present, in application order."""
        return list(self._applied)

    @property
    def applied(self):
        """The sequence of keys applied so far."""
        return list(self._applied)

    def __len__(self):
        return len(self._state)
