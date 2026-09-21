"""Exception types shared by the token and key layers."""


class TokenError(Exception):
    """Base class for every rejection reason."""


class MalformedToken(TokenError):
    """The token is not a well formed tokengate string."""


class InvalidSignature(TokenError):
    """The signature does not match the header and payload."""


class UnknownKey(TokenError):
    """The header names a key id the ring does not hold."""


class UnknownSession(TokenError, KeyError):
    """No live session is registered under the given id."""

    def __str__(self):  # KeyError would otherwise wrap the id in quotes
        return TokenError.__str__(self)
