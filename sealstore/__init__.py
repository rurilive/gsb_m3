"""sealstore: append-only batches of records with one digest.

Records are JSON values. :class:`SealStore` keeps them in append order
and folds their digests into a single chain digest, and
:mod:`sealstore.journal` writes a store to disk and replays it back,
checking that digest on the way in.
"""

from .canonical import canonical_bytes, record_digest, sha256_hex
from .errors import SealError
from .merkle import (
    ConsistencyProof,
    InclusionProof,
    MerkleTree,
    empty_root,
    leaf_hash,
    proof_from_bytes,
    verify_consistency,
    verify_inclusion,
)
from .store import SealStore, empty_digest

__all__ = [
    "ConsistencyProof",
    "SealError",
    "SealStore",
    "InclusionProof",
    "MerkleTree",
    "canonical_bytes",
    "empty_digest",
    "empty_root",
    "leaf_hash",
    "proof_from_bytes",
    "record_digest",
    "sha256_hex",
    "verify_consistency",
    "verify_inclusion",
]
