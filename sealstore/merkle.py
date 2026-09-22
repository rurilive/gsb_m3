"""Binary Merkle tree over sealstore records, with inclusion and
append-only consistency proofs.

The tree follows the RFC 6962 (Certificate Transparency) construction:

* a leaf hash is ``SHA256(TAG || 0x00 || canonical record bytes)``;
* an internal hash is ``SHA256(TAG || 0x01 || left || right)``;
* when a level has an odd node count the last node is promoted to the
  next level unchanged rather than duplicated, so no node ever has to
  be rehashed when a new leaf is appended;
* the advertised root commits the leaf count
  (``SHA256(TAG || "/root/" || n || bare tree hash)``), so a proof
  cannot be replayed under a different tree size -- odd-tail promotion
  would otherwise leave a smaller-size evaluation of the same path
  structurally identical;
* the empty tree has a fixed, public root.

Inclusion proofs use the RFC 6962 verification path (with the
promotion-aware shifts). Consistency proofs use the RFC 6962
``SUBPROOF(m, ..., false)`` construction: the bare old root is always
the first path element, which lets a verifier work from advertised,
size-committing roots alone (it never has to undo the root commitment
itself). Both proof objects survive a :meth:`Proof.to_bytes` /
:func:`proof_from_bytes` round trip, so a proof minted in one process
can be reloaded and verified in another.

The tree keeps complete, aligned subtree hashes per level. :meth:`append`
only creates the O(log n) new aligned nodes a leaf completes, and
:meth:`update` rewrites one leaf and recomputes only the nodes on the
single path from that leaf up to the folded root -- it never rebuilds
the tree.
"""

import hashlib

from .canonical import canonical_bytes
from .errors import SealError

_LEAF = b"\x00"
_NODE = b"\x01"
_TAG = b"sealstore/v1/merkle"

_PROOF_MAGIC = b"sealstore-proof/v1/"
_KIND_INCLUSION = b"I"
_KIND_CONSISTENCY = b"C"
_MAX_PATH = 256
_RAW_LEN = 8


def leaf_hash(record):
    """Raw leaf hash of one record."""
    return hashlib.sha256(_TAG + _LEAF + canonical_bytes(record)).digest()


def _node_hash(left, right):
    return hashlib.sha256(_TAG + _NODE + left + right).digest()


def empty_root():
    """The raw root hash of a tree with no records."""
    return hashlib.sha256(_TAG + b"empty").digest()


def _commit(size, bare):
    """Bind a bare tree hash to the number of leaves it covers.

    A proof path is evaluated purely from hashes and the advertised
    size. Without binding the size into the advertised root, the same
    path can be valid for several sizes (an odd-tail promotion makes
    the top of the path a suffix of larger trees); folding the size in
    here closes that hole using only data a verifier already has.
    """
    return hashlib.sha256(
        _TAG + b"/root/" + size.to_bytes(8, "big") + bare
    ).digest()


def _as_bytes(value):
    """Normalise a raw hash or a hex digest to raw bytes."""
    if isinstance(value, str):
        try:
            value = bytes.fromhex(value)
        except ValueError as exc:
            raise SealError("hash is not hexadecimal: %r" % (value,)) from exc
    if not isinstance(value, (bytes, bytearray)) or len(value) != 32:
        raise SealError("a hash must be exactly 32 bytes")
    return bytes(value)


def _as_root(value):
    if value is None:
        raise SealError("root hash is required")
    return _as_bytes(value)


def _split(size):
    """Largest power of two strictly smaller than ``size`` (size > 1)."""
    return 1 << ((size - 1).bit_length() - 1)


class Proof:
    """Base class for the serialisable inclusion/consistency proofs."""

    _kind = b""

    def to_bytes(self):
        """Serialise the proof to tagged binary form."""
        if len(self.path) > _MAX_PATH:
            raise SealError("proof path is too long")
        parts = [_PROOF_MAGIC, self._kind]
        for number in self._numbers():
            parts.append(number.to_bytes(_RAW_LEN, "big"))
        for node in self.path:
            parts.append(_as_bytes(node))
        return b"".join(parts)

    def _numbers(self):
        raise NotImplementedError

    @staticmethod
    def from_bytes(data):
        """Reload an inclusion or consistency proof from binary form."""
        return proof_from_bytes(data)


def _take_number(data, offset):
    if offset + _RAW_LEN > len(data):
        raise SealError("proof payload is truncated")
    return int.from_bytes(data[offset:offset + _RAW_LEN], "big"), offset + _RAW_LEN


def proof_from_bytes(data):
    """Rebuild a :class:`Proof` produced by :meth:`Proof.to_bytes`."""
    if not isinstance(data, (bytes, bytearray)):
        raise SealError("proof payload must be bytes")
    prefix = len(_PROOF_MAGIC) + 1
    if len(data) < prefix or bytes(data[:len(_PROOF_MAGIC)]) != _PROOF_MAGIC:
        raise SealError("not a sealstore proof payload")
    kind = bytes(data[len(_PROOF_MAGIC):prefix])
    offset = prefix
    if kind == _KIND_INCLUSION:
        leaf_index, offset = _take_number(data, offset)
        size, offset = _take_number(data, offset)
    elif kind == _KIND_CONSISTENCY:
        leaf_index = None
        old_size, offset = _take_number(data, offset)
        new_size, offset = _take_number(data, offset)
    else:
        raise SealError("unknown proof kind %r" % (kind,))
    remaining = len(data) - offset
    if remaining % 32:
        raise SealError("proof payload is not a whole number of hashes")
    count = remaining // 32
    if count > _MAX_PATH:
        raise SealError("proof path is too long")
    path = [
        bytes(data[offset + i * 32:offset + (i + 1) * 32])
        for i in range(count)
    ]
    if kind == _KIND_INCLUSION:
        return InclusionProof(leaf_index, size, path)
    return ConsistencyProof(old_size, new_size, path)


class InclusionProof(Proof):
    """A leaf-to-root path for record ``leaf_index`` in a tree of ``size``.

    ``path`` lists the sibling hashes bottom up. The proof self-describes
    the index and tree size, so verification only needs the claimed root
    and the record (or its raw leaf hash); nothing from the live tree is
    required.
    """

    _kind = _KIND_INCLUSION

    def __init__(self, leaf_index, size, path):
        if isinstance(leaf_index, bool) or not isinstance(leaf_index, int):
            raise SealError("leaf index must be an integer")
        if isinstance(size, bool) or not isinstance(size, int):
            raise SealError("tree size must be an integer")
        if leaf_index < 0 or size <= 0 or leaf_index >= size:
            raise SealError(
                "leaf index %d is outside a tree of size %d" % (leaf_index, size)
            )
        self.leaf_index = leaf_index
        self.size = size
        self.path = [_as_bytes(node) for node in path]

    def _numbers(self):
        return [self.leaf_index, self.size]

    def __eq__(self, other):
        return (
            isinstance(other, InclusionProof)
            and self.leaf_index == other.leaf_index
            and self.size == other.size
            and self.path == other.path
        )

    def __repr__(self):
        return "InclusionProof(%d, %d, %d hashes)" % (
            self.leaf_index,
            self.size,
            len(self.path),
        )


class ConsistencyProof(Proof):
    """Proof that the tree of ``new_size`` extends the tree of ``old_size``.

    ``path`` is the RFC 6962 consistency path from the old prefix to the
    new root. Verification needs only the old and new roots.
    """

    _kind = _KIND_CONSISTENCY

    def __init__(self, old_size, new_size, path):
        if isinstance(old_size, bool) or not isinstance(old_size, int):
            raise SealError("old size must be an integer")
        if isinstance(new_size, bool) or not isinstance(new_size, int):
            raise SealError("new size must be an integer")
        if not (0 < old_size <= new_size):
            raise SealError(
                "consistency needs 0 < old size <= new size, got %d -> %d"
                % (old_size, new_size)
            )
        self.old_size = old_size
        self.new_size = new_size
        self.path = [_as_bytes(node) for node in path]

    def _numbers(self):
        return [self.old_size, self.new_size]

    def __eq__(self, other):
        return (
            isinstance(other, ConsistencyProof)
            and self.old_size == other.old_size
            and self.new_size == other.new_size
            and self.path == other.path
        )

    def __repr__(self):
        return "ConsistencyProof(%d, %d, %d hashes)" % (
            self.old_size,
            self.new_size,
            len(self.path),
        )


def _verify_inclusion_hashes(leaf_index, size, leaf, root, path):
    """RFC 6962-bis inclusion verifier over raw hashes."""
    if size <= 0 or leaf_index < 0 or leaf_index >= size:
        return False
    if len(path) > max(1, size.bit_length()):
        return False
    probe_index, probe_last = leaf_index, size - 1
    needed = 0
    while probe_last != 0:
        if probe_index & 1 or probe_index == probe_last:
            if not probe_index & 1:
                while not probe_index & 1 and probe_index != 0:
                    probe_index >>= 1
                    probe_last >>= 1
        probe_index >>= 1
        probe_last >>= 1
        needed += 1
    if len(path) != needed:
        return False
    node_index = leaf_index
    last_index = size - 1
    current = leaf
    for sibling in path:
        if last_index == 0:
            return False
        if node_index & 1 or node_index == last_index:
            current = _node_hash(sibling, current)
            if not node_index & 1:
                while not node_index & 1 and node_index != 0:
                    node_index >>= 1
                    last_index >>= 1
        else:
            current = _node_hash(current, sibling)
        node_index >>= 1
        last_index >>= 1
    if last_index != 0:
        return False
    return _commit(size, current) == root


def verify_inclusion(root, record, proof, *, leaf=None):
    """Check an inclusion proof against nothing but a root and a record.

    ``record`` is the claimed value; pass ``leaf`` instead to verify a
    raw leaf hash. A structurally malformed proof or argument raises
    :class:`SealError`; a well-formed proof that does not hold returns
    ``False``.
    """
    expected_root = _as_root(root)
    path = [_as_bytes(node) for node in proof.path]
    if leaf is None:
        if record is None:
            raise SealError("a record or a leaf hash is required")
        claimed_leaf = leaf_hash(record)
    else:
        claimed_leaf = _as_bytes(leaf)
    return _verify_inclusion_hashes(
        proof.leaf_index, proof.size, claimed_leaf, expected_root, path
    )


def verify_consistency(old_root, new_root, proof):
    """RFC 6962-bis consistency verifier, using only the two roots.

    Returns ``True`` when the proof shows the ``new_root`` tree kept
    every leaf of the ``old_root`` tree and only appended more. Malformed
    arguments raise :class:`SealError`; an argument that does not hold
    returns ``False``.
    """
    first_hash = _as_root(old_root)
    second_hash = _as_root(new_root)
    old_size = proof.old_size
    new_size = proof.new_size
    if not (0 < old_size <= new_size):
        return False
    path = [_as_bytes(node) for node in proof.path]
    if old_size == new_size:
        return not path and first_hash == second_hash
    if not path:
        return False
    if len(path) > new_size.bit_length() + 1:
        return False
    node_index = old_size - 1
    last_index = new_size - 1
    while node_index & 1:
        node_index >>= 1
        last_index >>= 1
    # The minimal RFC path is consumed one hash per shift, so its length
    # is fixed by the two sizes. A shorter path can only end early by
    # lying about the sizes.
    needed = 1
    probe_index, probe_last = node_index, last_index
    while probe_last != 0:
        if probe_index & 1 or probe_index == probe_last:
            if not probe_index & 1:
                while not probe_index & 1 and probe_index != 0:
                    probe_index >>= 1
                    probe_last >>= 1
        probe_index >>= 1
        probe_last >>= 1
        needed += 1
    if len(path) != needed:
        return False
    first_runner = second_runner = path[0]
    for commit in path[1:]:
        if last_index == 0:
            return False
        if node_index & 1 or node_index == last_index:
            first_runner = _node_hash(commit, first_runner)
            second_runner = _node_hash(commit, second_runner)
            if not node_index & 1:
                while not node_index & 1 and node_index != 0:
                    node_index >>= 1
                    last_index >>= 1
        else:
            second_runner = _node_hash(second_runner, commit)
        node_index >>= 1
        last_index >>= 1
    return (
        last_index == 0
        and _commit(old_size, first_runner) == first_hash
        and _commit(new_size, second_runner) == second_hash
    )


class MerkleTree:
    """Records in append order, organised as an RFC 6962 Merkle tree.

    ``levels[0]`` holds every leaf hash and ``levels[d]`` holds every
    complete aligned subtree of ``2**d`` leaves. The root folds those
    complete blocks from the smallest to the largest, exactly as the
    RFC 6962 tree hash folds an odd tail upwards.
    """

    def __init__(self, records=()):
        self.levels = []
        self._size = 0
        for record in records:
            self.append(record)

    def __len__(self):
        return self._size

    @property
    def height(self):
        """``ceil(log2(size))`` for a non-empty tree, ``0`` when empty."""
        if self._size <= 1:
            return self._size
        return (self._size - 1).bit_length()

    def append(self, record):
        """Append one record.

        Only the leaf and the aligned nodes its position completes are
        hashed; existing nodes are never touched.
        """
        digest = leaf_hash(record)
        if not self.levels:
            self.levels.append([])
        self.levels[0].append(digest)
        size = self._size
        level = 0
        while (size >> level) & 1:
            level += 1
            if level == len(self.levels):
                self.levels.append([])
            block = 1 << (level - 1)
            right = self.levels[level - 1][size // block]
            left = self.levels[level - 1][size // block - 1]
            self.levels[level].append(_node_hash(left, right))
        self._size = size + 1

    def _range_hash(self, start, size):
        """Tree hash of the aligned range ``[start, start+size)``.

        The length need not be a power of two, but ``start`` must be a
        multiple of every block size the decomposition touches, which
        holds for every range the RFC recursion asks for.
        """
        runner = None
        position = start + size
        remaining = size
        bit = 0
        while remaining:
            block = 1 << bit
            if remaining & 1:
                position -= block
                if position % block:
                    raise SealError(
                        "range %d:%d is not aligned at block size %d"
                        % (start, start + size, block)
                    )
                node = self.levels[bit][position >> bit]
                runner = node if runner is None else _node_hash(node, runner)
            remaining >>= 1
            bit += 1
        return runner

    def _fold_root(self):
        if self._size == 0:
            return empty_root()
        runner = None
        position = self._size
        remaining = self._size
        bit = 0
        while remaining:
            block = 1 << bit
            if remaining & 1:
                position -= block
                node = self.levels[bit][position >> bit]
                runner = node if runner is None else _node_hash(node, runner)
            remaining >>= 1
            bit += 1
        return _commit(self._size, runner)

    def root(self):
        """Hex root hash of the whole tree (fixed value when empty)."""
        return self._fold_root().hex()

    def root_bytes(self):
        """Raw root hash of the whole tree."""
        return self._fold_root()

    def inclusion_proof(self, index):
        """Mint the :class:`InclusionProof` for leaf ``index``."""
        if not (0 <= index < self._size):
            raise IndexError(
                "leaf index %d is out of range for %d records"
                % (index, self._size)
            )
        path = []
        self._inclusion_path(index, 0, self._size, path)
        return InclusionProof(index, self._size, path)

    def _inclusion_path(self, target, start, size, path):
        if size == 1:
            return
        cut = _split(size)
        if target < cut:
            self._inclusion_path(target, start, cut, path)
            path.append(self._range_hash(start + cut, size - cut))
        else:
            self._inclusion_path(target - cut, start + cut, size - cut, path)
            path.append(self._range_hash(start, cut))

    def consistency_proof(self, old_size):
        """Mint a :class:`ConsistencyProof` from ``old_size`` to now."""
        if not (0 < old_size < self._size):
            raise SealError(
                "consistency needs 0 < old size < current size, got %d of %d"
                % (old_size, self._size)
            )
        path = []
        # Always include the bare old root explicitly. The advertised
        # root commits the size, so the verifier cannot prepend it itself;
        # this is the RFC SUBPROOF(..., false) equivalent.
        self._consistency_path(old_size, 0, self._size, path)
        return ConsistencyProof(old_size, self._size, path)

    def _consistency_path(self, target, start, size, path):
        if target == size:
            path.append(self._range_hash(start, size))
            return
        cut = _split(size)
        if target <= cut:
            self._consistency_path(target, start, cut, path)
            path.append(self._range_hash(start + cut, size - cut))
        else:
            self._consistency_path(target - cut, start + cut, size - cut, path)
            path.append(self._range_hash(start, cut))

    def update(self, index, record):
        """Replace leaf ``index`` and recompute only its path to the root.

        Returns the number of hashes recomputed: the leaf itself, every
        aligned ancestor on its path, and the folds that rebuild the
        root. It never rebuilds nodes off that path.
        """
        if not (0 <= index < self._size):
            raise IndexError(
                "leaf index %d is out of range for %d records"
                % (index, self._size)
            )
        recomputed = 1
        self.levels[0][index] = leaf_hash(record)
        level = 1
        while 1 << level <= self._size:
            block = 1 << level
            parent_index = index // block
            if (parent_index + 1) * block <= self._size:
                left = self.levels[level - 1][parent_index * 2]
                right = self.levels[level - 1][parent_index * 2 + 1]
                self.levels[level][parent_index] = _node_hash(left, right)
                recomputed += 1
            level += 1
        recomputed += bin(self._size).count("1") - 1
        return recomputed
