"""Persist a store as a text journal, and replay it back.

A journal is one canonical JSON header line followed by one canonical
JSON line per record::

    {"digest":"...","format":"sealstore-journal/1","records":2}
    {"id":1,"kind":"payment"}
    {"id":2,"kind":"refund"}

:func:`load` replays the lines through a fresh :class:`SealStore` and
refuses to hand back anything whose recomputed digest disagrees with the
header, so a rewritten, reordered or truncated batch is caught here.
"""

import json
import os

from .canonical import canonical_bytes
from .errors import SealError
from .store import SealStore

MAGIC = "sealstore-journal/1"


def header(store):
    """The header dict describing a store's journal."""
    return {"format": MAGIC, "records": len(store), "digest": store.digest()}


def save(store, path):
    """Write the store to ``path``, returning the number of lines written."""
    lines = [_encode(header(store))]
    for record in store.records():
        lines.append(_encode_record(record))
    text = "\n".join(lines) + "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp, path)
    return len(lines)


def load(path):
    """Replay a journal file into a fresh store.

    Raises :class:`SealError` when the file is not a journal, a line is
    malformed, or the replayed records do not reproduce the header digest.
    """
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()
    return replay(raw, source=path)


def verify(path):
    """Return the digest a journal claims, after checking that it holds."""
    return load(path).digest()


def replay(raw, source="<memory>"):
    """Rebuild a store from journal text."""
    lines = raw.splitlines()
    if not lines:
        raise SealError("journal %s is empty" % (source,))
    try:
        head = json.loads(lines[0])
    except ValueError as exc:
        raise SealError("journal %s header is not JSON" % (source,)) from exc
    if not isinstance(head, dict) or head.get("format") != MAGIC:
        raise SealError("journal %s is not a %s file" % (source, MAGIC))
    store = SealStore()
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            raise SealError("journal %s line %d is blank" % (source, number))
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise SealError(
                "journal %s line %d is not JSON" % (source, number)
            ) from exc
        store.append(record)
    if head.get("records") != len(store):
        raise SealError(
            "journal %s holds %d records but claims %r"
            % (source, len(store), head.get("records"))
        )
    if head.get("digest") != store.digest():
        raise SealError("journal %s digest does not match its records" % (source,))
    return store


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _encode_record(record):
    return canonical_bytes(record).decode("utf-8")
