# sealstore

An append-only batch of records with a single digest over the whole
batch, plus a text journal format for shipping the batch around and
replaying it back.

## Layout

```
sealstore/
  canonical.py   deterministic record encoding and record digests
  store.py       SealStore, the append-only batch and its chain digest
  journal.py     save / load / verify a batch as JSON lines
  merkle.py      MerkleTree with inclusion and append-only consistency proofs
  errors.py      SealError
tests/           regression tests for the behaviour above
demo.py          end to end demo
```

## Records and digests

A record is any JSON value, usually a dict. `canonical_bytes` renders one
as compact UTF-8 with sorted keys, so key order never matters but `1` and
`1.0` do. Object keys have to be strings and nan or infinity is refused,
both with `SealError`.

`SealStore` keeps its own copy of every appended record and folds the
record digest into a running chain digest, so `digest()` commits to
content and order. A store that has seen nothing has a fixed, public
empty digest.

```python
from sealstore import SealStore, canonical_bytes, record_digest, empty_digest

store = SealStore()
store.append({"id": 1, "kind": "payment"})   # returns the record digest
store.extend([{"id": 2}])
store.digest()          # hex digest of the whole batch
store.records()         # deep copy, in append order
len(store), store.stats()
```

## Journal

```python
from sealstore import journal

journal.save(store, "batch.jsonl")   # header line plus one line per record
journal.load("batch.jsonl")          # SealStore, or SealError if the file was touched
```

The header carries the record count and the digest. `load` replays the
lines and refuses to return a store whose recomputed digest disagrees
with the header. Writes go to a temporary file first and are moved into
place, so a crashed save never truncates an existing journal.

## Merkle proofs

`MerkleTree` builds an RFC 6962 style binary tree over the same
canonical records: leaves are tagged record hashes, internal nodes are
tagged hashes of their two children, and an odd node on a level is
promoted unchanged rather than copied. The advertised root folds in the
record count as well as the bare tree hash, which binds a proof to the
exact tree size -- otherwise an odd-tail promotion would let the same
path verify under a smaller size. The empty tree has a fixed root from
`empty_root()`.

```python
from sealstore import (
    MerkleTree, proof_from_bytes,
    verify_inclusion, verify_consistency,
)

tree = MerkleTree(records)           # or append() one at a time
tree.root()                           # hex root, order and content sensitive

proof = tree.inclusion_proof(7)       # path of sibling hashes
verify_inclusion(tree.root(), records[7], proof)   # root + record is all it takes

older = MerkleTree(records[:5]).root_bytes()
consistency = tree.consistency_proof(5)
verify_consistency(older, tree.root_bytes(), consistency)  # append-only check
```

Both proof objects self-describe their sizes and positions and survive
`proof.to_bytes()` / `proof_from_bytes(...)`, so a proof minted in one
process can be shipped across a process boundary and verified there.
Consistency proofs always carry the old bare root as their first hash,
so verification needs only the two advertised roots.
Structurally malformed payloads raise `SealError`; a well-formed proof
that does not match the root, record or history returns `False`.

`tree.update(index, record)` edits one leaf and recomputes only the
nodes on that leaf's path up to the folded root (it never rebuilds the
tree), returning how many hashes it recomputed -- at most twice the
tree height. Out of range indexes raise `IndexError`; empty trees,
odd-sized levels and malformed proofs all have behaviour pinned down by
`tests/test_merkle.py`.

## Running

```
python3 demo.py
python3 -m unittest discover -s tests
```
