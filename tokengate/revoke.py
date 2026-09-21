"""Per-session revocation list, keyed by session id.

Revoking a session kills every token that names it, including refresh
strings already handed out. Lookup is a dict hit: ``is_revoked`` is
constant time and independent of the number of revoked sessions.

Each entry remembers ``expires_at``, an upper bound on how long any token
of that session could possibly remain live. ``sweep`` drops entries past
it, so a long running service does not grow without end.
"""

from tokengate.errors import UnknownSession


class RevocationList:
    """Maps revoked session ids to the moment their tombstone can expire."""

    def __init__(self, clock=None):
        self._clock = clock
        self._revoked = {}

    def bind_clock(self, clock):
        """Attach the clock used by later parameterless sweep calls."""
        self._clock = clock

    def revoke(self, sid, expires_at):
        """Mark ``sid`` revoked, keeping the token until ``expires_at``.

        Revoking again extends the keep-until time when the new bound is
        later, so a rotation right before revocation cannot shorten the
        tombstone's life. Returns the stored bound.
        """
        previous = self._revoked.get(sid)
        if previous is None or expires_at > previous:
            self._revoked[sid] = expires_at
        return self._revoked[sid]

    def is_revoked(self, sid):
        """True exactly when ``sid`` currently has a live tombstone."""
        return sid in self._revoked

    def expires_at(self, sid):
        """The keep-until time, or raise UnknownSession."""
        try:
            return self._revoked[sid]
        except KeyError:
            raise UnknownSession("session is not revoked: %r" % (sid,))

    def discard(self, sid):
        """Drop one entry; True when something was removed."""
        return self._revoked.pop(sid, None) is not None

    def sweep(self, now=None):
        """Remove tombstones whose bound is strictly before ``now``.

        Returns ``{"removed": n, "remaining": m}``.
        """
        if now is None:
            if self._clock is None:
                raise RuntimeError("sweep() needs a clock or an explicit now")
            now = self._clock.now()
        expired = [sid for sid, bound in self._revoked.items() if bound < now]
        for sid in expired:
            del self._revoked[sid]
        return {"removed": len(expired), "remaining": len(self._revoked)}

    def sids(self):
        """All currently remembered revoked ids, sorted."""
        return sorted(self._revoked)

    def __contains__(self, sid):
        return sid in self._revoked

    def __len__(self):
        return len(self._revoked)
