"""本地事件存储。

事件追加进 JSONL 文件，一行一个事件：
{"seq": 1, "type": "order", "v": 1, "data": {...}}
append 先按对应版本的 schema 校验；数据文件全程以追加方式写入，
read 只读打开，升级只发生在读路径，读前读后字节一致。

read(version=None)：
- 不传 version，每个事件投影到该类型的最新版本（改名搬运、沿版本
  链补默认值，v 更新为最新；本就在最新版本的事件原样返回）；
- 传入 version，全部投影到该版本，低于它的升级、高于它的降级；
- 降级口径：新版本独有字段直接丢弃，改名沿链还原成旧名；
  旧版本当时就缺的可选字段保持缺失，不补默认值。
"""

import json
import os

from .evolution import build_edge
from .schema import SchemaError


class EventStore:
    """行式 JSON 文件上的追加写事件存储。"""

    def __init__(self, path, registry):
        self.path = path
        self._registry = registry
        self._appends = 0
        self._reads = 0
        self._upgraded = 0
        self._downgraded = 0
        self._plans_built = 0
        self._edge_cache = {}
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

    def read(self, version=None):
        """读回全部事件并投影到目标版本，按写入顺序排列。

        version 省略时每个事件投影到它所属类型的最新版本；给定版本号
        时所有事件投影到该版本（要求每个类型都注册过该版本）。
        返回的 data 是独立副本。
        """
        self._reads += 1
        events = []
        if not os.path.exists(self.path):
            return events
        chain_cache = {}
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                etype = raw["type"]
                source_v = raw["v"]
                data = dict(raw["data"])
                if version is None:
                    target_v = self._registry.latest(etype).version
                else:
                    target_v = version
                    if version not in self._registry.versions(etype):
                        raise SchemaError(
                            "cannot read %s at unregistered v%s" % (etype, version)
                        )
                if source_v != target_v:
                    data, target_v = self._project(
                        etype, data, source_v, target_v, chain_cache
                    )
                events.append(
                    {
                        "seq": raw["seq"],
                        "type": etype,
                        "v": target_v,
                        "data": data,
                    }
                )
        return events

    def _project(self, etype, data, source_v, target_v, chain_cache):
        """沿注册版本链把 data 从 source_v 投影到 target_v。"""
        key = (etype, source_v, target_v)
        chain = chain_cache.get(key)
        if chain is None:
            registered = self._registry.versions(etype)
            try:
                start = registered.index(source_v)
                end = registered.index(target_v)
            except ValueError:
                raise SchemaError(
                    "no version path for %s v%s -> v%s"
                    % (etype, source_v, target_v)
                )
            stepping = registered[
                min(start, end) : max(start, end) + 1
            ]
            edges = [self._edge(etype, low) for low in stepping[:-1]]
            chain = (stepping, edges)
            chain_cache[key] = chain
        stepping, edges = chain
        if target_v > source_v:
            for edge in edges:
                data = edge.upgrade(data)
            self._upgraded += 1
        else:
            for edge in reversed(edges):
                data = edge.downgrade(data)
            self._downgraded += 1
        return data, target_v

    def _edge(self, etype, low_v):
        key = (etype, low_v)
        edge = self._edge_cache.get(key)
        if edge is None:
            versions = self._registry.versions(etype)
            high_v = versions[versions.index(low_v) + 1]
            edge = build_edge(
                self._registry.get(etype, low_v),
                self._registry.get(etype, high_v),
            )
            self._edge_cache[key] = edge
            self._plans_built += 1
        return edge

    def count(self):
        """事件条数。"""
        return self._count()

    def stats(self):
        """规模与调用计数快照。"""
        return {
            "events": self._count(),
            "appends": self._appends,
            "reads": self._reads,
            "upgraded": self._upgraded,
            "downgraded": self._downgraded,
            "plans_built": self._plans_built,
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
