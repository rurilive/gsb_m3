"""本地事件存储。

事件追加进 JSONL 文件，一行一个事件：
{"seq": 1, "type": "order", "v": 1, "data": {...}}
append 先按对应版本的 schema 校验。read() 默认把旧版本事件升级到
最新版本（应用改名链、补默认值，v 一并更新），已在最新的原样返回；
read(version=k) 降级读，只保留目标版本声明的字段。升级只发生在读路径，
数据文件本身不被改写。
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
        self._upgrades = 0
        self._plan_builds = 0
        self._plans = {}
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
        """读回全部事件，按写入顺序排列，data 是独立副本。
        version 省略时把旧事件升到该类型最新版本；传入旧版本号则降级读，
        目标版本未声明的字段被丢弃，改名按反向映射还原。"""
        self._reads += 1
        events = []
        if not os.path.exists(self.path):
            return events
        targets = {}
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                etype = raw["type"]
                v = raw["v"]
                data = dict(raw["data"])
                if version is not None:
                    target = version
                else:
                    target = targets.get(etype)
                    if target is None:
                        target = self._registry.latest(etype).version
                        targets[etype] = target
                if v != target:
                    plan = self._plan(etype, v, target)
                    data = self._apply(plan, data)
                    if v < target:
                        self._upgrades += 1
                    v = target
                events.append(
                    {
                        "seq": raw["seq"],
                        "type": etype,
                        "v": v,
                        "data": data,
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
            "upgrades": self._upgrades,
            "plans": self._plan_builds,
        }

    def _plan(self, etype, from_v, to_v):
        """取 (类型, 源版本, 目标版本) 的升降级方案，只构建一次。"""
        key = (etype, from_v, to_v)
        plan = self._plans.get(key)
        if plan is None:
            plan = self._build_plan(etype, from_v, to_v)
            self._plans[key] = plan
            self._plan_builds += 1
        return plan

    def _build_plan(self, etype, from_v, to_v):
        steps = []
        if from_v < to_v:
            for v in range(from_v, to_v):
                new = self._registry.get(etype, v + 1)
                steps.append((dict(new.renames), dict(new.defaults), set(new.fields)))
        else:
            for v in range(from_v, to_v, -1):
                new = self._registry.get(etype, v)
                old = self._registry.get(etype, v - 1)
                reverse = {new_name: old_name for old_name, new_name in new.renames.items()}
                steps.append((reverse, {}, set(old.fields)))
        return steps

    @staticmethod
    def _apply(plan, data):
        for renames, defaults, fields in plan:
            out = {}
            for key, value in data.items():
                new_key = renames.get(key, key)
                if new_key in fields:
                    out[new_key] = value
            for key, value in defaults.items():
                if key not in out:
                    out[key] = value
            data = out
        return data

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
