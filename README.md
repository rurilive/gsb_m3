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

## Running

```
python3 demo.py
python3 -m unittest discover -s tests
```
