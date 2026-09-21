"""本地事件存储。

事件追加进 JSONL 文件，一行一个事件：
{"seq": 1, "type": "order", "v": 1, "data": {...}}
append 先按对应版本的 schema 校验。文件永远只追加：read 做的
升级/降级只发生在读路径，不回写文件，读前读后文件字节一致。

read(version=None) 不给版本时把每条事件升级到该类型最新版本，
事件里的 v 一并更新；给了版本则统一投影到该版本（升级或降级），
目标版本必须是该类型已注册的版本。相邻版本之间的迁移方案
（evolve.StepPlan）按 (类型, 低版本号) 缓存，只构建一次。
"""

import json
import os

from .evolve import StepPlan
from .schema import SchemaError


class EventStore:
    """行式 JSON 文件上的追加写事件存储。"""

    def __init__(self, path, registry):
        self.path = path
        self._registry = registry
        self._appends = 0
        self._reads = 0
        self._upgraded = 0
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
        """读回全部事件并投影到目标版本，按写入顺序排列。

        version 为 None 时每条事件升级到该类型最新版本，v 更新；
        version 给定则投影到该版本。已在目标版本的事件原样返回，
        data 仍是独立副本。文件本身不会被修改。
        """
        self._reads += 1
        events = []
        if not os.path.exists(self.path):
            return events
        latest_versions = {}
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                etype = raw["type"]
                current_v = raw["v"]
                if version is None:
                    target_v = latest_versions.get(etype)
                    if target_v is None:
                        target_v = self._registry.latest(etype).version
                        latest_versions[etype] = target_v
                else:
                    target_v = version
                    self._registry.get(etype, target_v)
                data = dict(raw["data"])
                if current_v < target_v:
                    self._project(etype, data, current_v, target_v, True)
                    current_v = target_v
                    self._upgraded += 1
                elif current_v > target_v:
                    self._project(etype, data, target_v, current_v, False)
                    current_v = target_v
                events.append(
                    {"seq": raw["seq"], "type": etype, "v": current_v, "data": data}
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
            "upgraded": self._upgraded,
            "plans_built": len(self._plans),
        }

    def _project(self, etype, data, low_v, high_v, upward):
        """沿已注册的相邻版本链把 data 从一端投影到另一端。"""
        chain = [v for v in self._registry.versions(etype) if low_v <= v <= high_v]
        pairs = list(zip(chain, chain[1:]))
        if not upward:
            pairs.reverse()
        for low_step, high_step in pairs:
            plan = self._step(etype, low_step, high_step)
            if upward:
                plan.upgrade(data)
            else:
                plan.downgrade(data)

    def _step(self, etype, low_v, high_v):
        """取相邻版本单步方案，未建过则构建并计入 plans_built。"""
        plan = self._plans.get((etype, low_v))
        if plan is None:
            plan = StepPlan(
                self._registry.get(etype, low_v),
                self._registry.get(etype, high_v),
            )
            self._plans[(etype, low_v)] = plan
        return plan

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
