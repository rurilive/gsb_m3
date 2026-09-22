"""Deterministic byte encoding for records, and record digests.

A record is any JSON value, usually a dict. :func:`canonical_bytes` turns
one into bytes that depend only on its content: object keys are sorted,
whitespace is dropped, non-ascii text stays literal, floats keep the
shortest form that round-trips. Two records that differ in anything JSON
can express, including ``1`` versus ``1.0`` or key order, encode to
different bytes.

Object keys must be strings; anything else raises :class:`SealError`, as
do floats JSON cannot represent (nan, infinity). Tuples and other
sequences that JSON writes as arrays are normalised to arrays, so a tuple
and the list with the same items encode identically.
"""

import hashlib
import json

from .errors import SealError

_TAG = b"sealstore/v1"


def canonical_bytes(record):
    """Encode a record as deterministic UTF-8 bytes."""
    _check_keys(record)
    try:
        text = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except ValueError as exc:
        raise SealError("record cannot be encoded: %s" % (exc,)) from exc
    return text.encode("utf-8")


def _check_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SealError("object key %r is not a string" % (key,))
            _check_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_keys(item)


def sha256_hex(data):
    """Lowercase hex sha256 of raw bytes, with no tag mixed in."""
    return hashlib.sha256(data).hexdigest()


def record_digest(record):
    """Hex digest of one record, tag separated from the canonical bytes."""
    return hashlib.sha256(_TAG + b"/record/" + canonical_bytes(record)).hexdigest()
