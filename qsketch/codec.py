"""落盘与读回。

JSON 编码，顶层带 fmt 格式号，当前是 1。SampleSet 存样本列表，
ShardSet 存分片名到样本列表的映射，名字排好序写，同一份对象
落盘两次字节一致。读回时结构、样本都要重新过一遍校验，不合规
一律抛 FormatError。
"""

import json

from qsketch.errors import FormatError, SketchError
from qsketch.samples import SampleSet
from qsketch.shards import ShardSet

FMT = 1


def dump(obj):
    """把 SampleSet 或 ShardSet 编成 bytes。"""
    if isinstance(obj, SampleSet):
        payload = {"fmt": FMT, "kind": "sample_set", "samples": obj.values()}
    elif isinstance(obj, ShardSet):
        payload = {
            "fmt": FMT,
            "kind": "shard_set",
            "shards": {name: obj.values(name) for name in obj.names()},
        }
    else:
        raise FormatError("cannot dump %s" % type(obj).__name__)
    text = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    return text.encode("utf-8")


def load(data):
    """从 bytes 读回 SampleSet 或 ShardSet。"""
    if isinstance(data, (bytearray, memoryview)):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise FormatError("load expects bytes, got %s" % type(data).__name__)
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise FormatError("payload is not valid json: %s" % (exc,)) from exc
    if not isinstance(payload, dict):
        raise FormatError("payload must be an object")
    if payload.get("fmt") != FMT:
        raise FormatError("unsupported fmt: %r" % (payload.get("fmt"),))
    kind = payload.get("kind")
    if kind == "sample_set":
        return _load_samples(payload.get("samples"))
    if kind == "shard_set":
        shards = payload.get("shards")
        if not isinstance(shards, dict):
            raise FormatError("shard_set without shards mapping")
        result = ShardSet()
        for name in sorted(shards):
            sample_set = _load_samples(shards[name])
            for value in sample_set.values():
                result.add(name, value)
        return result
    raise FormatError("unknown kind: %r" % (kind,))


def save(obj, path):
    """dump 之后写进文件。"""
    with open(path, "wb") as handle:
        handle.write(dump(obj))


def read(path):
    """读文件再 load。"""
    with open(path, "rb") as handle:
        return load(handle.read())


def _load_samples(raw):
    if not isinstance(raw, list):
        raise FormatError("samples must be a list")
    sample_set = SampleSet()
    for value in raw:
        try:
            sample_set.add(value)
        except SketchError as exc:
            raise FormatError("bad sample: %s" % (exc,)) from exc
    return sample_set
