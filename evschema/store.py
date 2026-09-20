"""本地事件存储。

事件追加进 JSONL 文件，一行一个事件：
{"seq": 1, "type": "order", "v": 1, "data": {...}}
append 先按对应版本的 schema 校验，read 按写入顺序原样读回。
"""

import json
import os

from .schema import SchemaError


class EventStore:
    """行式 JSON 文件上的追加写事件存储。"""

    def __init__(self, path, registry):
        self.path = path
        self._registry = registry
        self._appends = 0
        self._reads = 0
        self._total = None

    def append(self, etype, data, version=None):
        """追加一个事件，返回其序号。version 省略时用该类型最新版本。"""
        if version is None:
            version = self._registry.latest(etype).version
        schema = self._registry.get(etype, version)
        problems = schema.validate(data)
        if problems:
            raise SchemaError(
                "invalid %s v%s: %s" % (etype, version, "; ".join(problems))
            )
        seq = self._count() + 1
        line = json.dumps(
            {"seq": seq, "type": etype, "v": version, "data": data},
            sort_keys=True,
        )
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        self._total = seq
        self._appends += 1
        return seq

    def read(self):
        """读回全部事件，按写入顺序排列，data 是独立副本。"""
        self._reads += 1
        events = []
        if not os.path.exists(self.path):
            return events
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                events.append(
                    {
                        "seq": raw["seq"],
                        "type": raw["type"],
                        "v": raw["v"],
                        "data": dict(raw["data"]),
                    }
                )
        return events

    def count(self):
        """事件条数。"""
        return self._count()

    def stats(self):
        """规模与调用计数快照。"""
        return {
            "events": self._count(),
            "appends": self._appends,
            "reads": self._reads,
        }

    def _count(self):
        if self._total is None:
            total = 0
            if os.path.exists(self.path):
                with open(self.path, encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            total += 1
            self._total = total
        return self._total
