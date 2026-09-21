"""Exception types shared by the token and key layers."""


class TokenError(Exception):
    """Base class for every rejection reason."""


class MalformedToken(TokenError):
    """The token is not a well formed tokengate string."""


class InvalidSignature(TokenError):
    """The signature does not match the header and payload."""


class UnknownKey(TokenError):
    """The header names a key id the ring does not hold."""


class InvalidClaims(TokenError):
    """A well signed token is missing claims or carries the wrong kind."""


class TokenExpired(TokenError):
    """The token's exp is outside the accepted window."""


class TokenNotYetValid(TokenError):
    """The token claims to be valid only in the future, beyond the skew."""


class WrongTokenType(TokenError):
    """An access/refresh token was presented to the wrong entry point."""


class SessionRevoked(TokenError):
    """The session has been revoked; every token for it is dead."""


class RefreshReused(TokenError):
    """The refresh token was already rotated; presenting it again is theft."""


class UnknownSession(TokenError, KeyError):
    """No live session is registered under the given id."""

    def __str__(self):  # KeyError would otherwise wrap the id in quotes
        return TokenError.__str__(self)
