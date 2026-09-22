"""An append-only batch of records folded into one chain digest."""

import copy
import hashlib
import json

from .canonical import canonical_bytes, record_digest
from .errors import SealError

_CHAIN_TAG = b"sealstore/v1/chain"


def empty_digest():
    """The digest of a store that has never seen a record."""
    return hashlib.sha256(_CHAIN_TAG).hexdigest()


class SealStore:
    """Records in append order, plus a digest over the whole batch.

    Appending a record hashes its canonical bytes into a running chain, so
    the digest commits to both the content and the order of everything
    appended so far. The store keeps its own normalised copy of each
    record: the caller may reuse or mutate the dict afterwards without
    touching the digest, and :meth:`records` hands out copies for the same
    reason.
    """

    def __init__(self):
        self._records = []
        self._chain = hashlib.sha256(_CHAIN_TAG).digest()

    def append(self, record):
        """Append one record and return its record digest.

        The record must be encodable; :class:`SealError` is raised, and
        the store is left untouched, otherwise.
        """
        data = canonical_bytes(record)
        digest = record_digest(record)
        self._records.append(json.loads(data.decode("utf-8")))
        self._chain = hashlib.sha256(
            _CHAIN_TAG + self._chain + bytes.fromhex(digest)
        ).digest()
        return digest

    def extend(self, records):
        """Append an iterable of records, returning how many landed."""
        appended = 0
        for record in records:
            self.append(record)
            appended += 1
        return appended

    def digest(self):
        """Hex digest of the whole batch, order sensitive."""
        return self._chain.hex()

    def records(self):
        """A deep copy of the stored records, in append order."""
        return copy.deepcopy(self._records)

    def __len__(self):
        return len(self._records)

    def stats(self):
        return {"records": len(self._records), "digest": self._chain.hex()}
