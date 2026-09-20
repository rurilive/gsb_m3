"""schema 版本注册表。

按 事件类型 -> 版本号 保管 Schema，注册时不允许覆盖已有版本。
注册新版本前先对相邻旧版本做兼容判定，不兼容则拒绝。
构造时传入 path 可把注册表落盘，同一路径再建实例即可恢复。
"""

import json
import os

from .compat import check_compatibility
from .schema import Schema, SchemaError


class SchemaRegistry:
    """事件类型的版本目录。"""

    def __init__(self, path=None):
        self.path = path
        self._schemas = {}
        if path and os.path.exists(path):
            self._load()

    def register(self, schema):
        """注册一个版本。同一类型同一版本号已存在则报错；
        存在更低版本时先做兼容判定，不兼容则拒绝。"""
        by_version = self._schemas.setdefault(schema.name, {})
        if schema.version in by_version:
            raise SchemaError(
                "version already registered: %s v%s" % (schema.name, schema.version)
            )
        lower = [v for v in by_version if v < schema.version]
        if lower:
            previous = by_version[max(lower)]
            verdict = check_compatibility(previous, schema)
            if not verdict.ok:
                raise SchemaError(
                    "incompatible %s v%s: %s"
                    % (schema.name, schema.version, "; ".join(verdict.reasons))
                )
        by_version[schema.version] = schema
        self._persist()
        return schema

    def get(self, name, version):
        """取指定类型指定版本的 Schema，没有则报错。"""
        by_version = self._schemas.get(name)
        if by_version is None or version not in by_version:
            raise SchemaError("unknown schema: %s v%s" % (name, version))
        return by_version[version]

    def latest(self, name):
        """取该类型版本号最大的 Schema。"""
        by_version = self._schemas.get(name)
        if not by_version:
            raise SchemaError("unknown schema: %s" % name)
        return by_version[max(by_version)]

    def versions(self, name):
        """该类型已注册的版本号，升序；未知类型返回空列表。"""
        return sorted(self._schemas.get(name, {}))

    def names(self):
        """已注册的事件类型，按字典序。"""
        return sorted(self._schemas)

    def __len__(self):
        return sum(len(by_version) for by_version in self._schemas.values())

    def _persist(self):
        if not self.path:
            return
        records = []
        for name in sorted(self._schemas):
            for version in sorted(self._schemas[name]):
                schema = self._schemas[name][version]
                records.append(
                    {
                        "name": schema.name,
                        "version": schema.version,
                        "fields": schema.fields,
                        "required": list(schema.required),
                        "defaults": schema.defaults,
                        "renames": schema.renames,
                    }
                )
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump({"schemas": records}, fh, sort_keys=True)
        os.replace(tmp_path, self.path)

    def _load(self):
        with open(self.path, encoding="utf-8") as fh:
            records = json.load(fh)["schemas"]
        for record in records:
            schema = Schema(
                record["name"],
                record["version"],
                record["fields"],
                required=record["required"],
                defaults=record["defaults"],
                renames=record["renames"],
            )
            self._schemas.setdefault(schema.name, {})[schema.version] = schema
