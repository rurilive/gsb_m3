"""In-memory registry of live sessions.

A session is a named record plus the claims that were used to open it.
Note that signing is stateless: closing a session here removes the record,
but any token string that leaked out earlier keeps its own life.
"""

import secrets

from tokengate.errors import UnknownSession

SID_BYTES = 16


class Session:
    """One registered session."""

    __slots__ = ("sid", "opened_at", "claims")

    def __init__(self, sid, opened_at, claims):
        self.sid = sid
        self.opened_at = opened_at
        self.claims = dict(claims)

    def info(self):
        """Snapshot of the record as a plain dict."""
        return {"sid": self.sid, "opened_at": self.opened_at, "claims": dict(self.claims)}

    def __repr__(self):
        return "Session(sid=%r, opened_at=%r)" % (self.sid, self.opened_at)


def new_sid():
    """Fresh, unguessable session id."""
    return secrets.token_urlsafe(SID_BYTES)


class SessionStore:
    """Tracks which session ids exist. Keyed by sid, so lookup is a dict hit."""

    def __init__(self, clock):
        self._clock = clock
        self._sessions = {}

    def open(self, claims=None, sid=None):
        """Register a new session and return it.

        ``sid`` is normally left None and generated; supplying one is for
        tests and migration where ids come from elsewhere.
        """
        sid = sid or new_sid()
        if sid in self._sessions:
            raise ValueError("session id already in use: %r" % (sid,))
        session = Session(sid, self._clock.now(), claims or {})
        self._sessions[sid] = session
        return session

    def get(self, sid):
        """Return the Session or None when the id is unknown."""
        return self._sessions.get(sid)

    def require(self, sid):
        """Return the Session or raise UnknownSession."""
        session = self._sessions.get(sid)
        if session is None:
            raise UnknownSession("unknown session id: %r" % (sid,))
        return session

    def close(self, sid):
        """Drop the record; True when something was removed.

        Idempotent: closing an unknown id is not an error.
        """
        return self._sessions.pop(sid, None) is not None

    def sids(self):
        """All live session ids, sorted for stable output."""
        return sorted(self._sessions)

    def __len__(self):
        return len(self._sessions)

    def __contains__(self, sid):
        return sid in self._sessions

    def __iter__(self):
        return iter(self.sids())
