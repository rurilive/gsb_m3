"""Symmetric key material addressed by short key ids.

A ring holds several secrets at once so a service can rotate keys without
invalidating tokens signed under the previous one.
"""

from tokengate.errors import UnknownKey


def _to_bytes(secret):
    if isinstance(secret, bytes):
        return secret
    if isinstance(secret, str):
        return secret.encode("utf-8")
    raise TypeError("secret must be bytes or str, got %r" % (type(secret).__name__,))


class KeyRing:
    """A small set of named HMAC secrets."""

    def __init__(self, keys=None):
        self._keys = {}
        for kid, secret in dict(keys or {}).items():
            self.add(kid, secret)

    def add(self, kid, secret):
        """Register ``secret`` under ``kid``, replacing any previous entry."""
        if not kid:
            raise ValueError("kid must be a non-empty string")
        self._keys[str(kid)] = _to_bytes(secret)

    def secret(self, kid):
        """Return the bytes for ``kid`` or raise UnknownKey."""
        try:
            return self._keys[kid]
        except KeyError:
            raise UnknownKey("no secret registered for kid %r" % (kid,))

    def drop(self, kid):
        """Forget ``kid``; returns True when it was present."""
        return self._keys.pop(kid, None) is not None

    def kids(self):
        """Sorted list of registered key ids."""
        return sorted(self._keys)

    def __contains__(self, kid):
        return kid in self._keys

    def __len__(self):
        return len(self._keys)
