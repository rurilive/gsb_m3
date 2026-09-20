"""schema 版本注册表。

按 事件类型 -> 版本号 保管 Schema，注册时不允许覆盖已有版本；新版本
必须与版本号相邻的旧版本兼容（判定见 evschema.evolution）。

传入 path 时注册表本身落盘为行式 JSON 文件：注册成功即追加一行，
之后用同一路径再建实例会恢复出完全相同的版本与判定。
"""

import json
import os

from .evolution import check_compatibility, ensure_compatible
from .schema import Schema, SchemaError


class SchemaRegistry:
    """事件类型的版本目录。"""

    def __init__(self, path=None):
        self.path = path
        self._schemas = {}
        if path is not None and os.path.exists(path):
            self._load()

    def _load(self):
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                schema = Schema(
                    record["name"],
                    record["version"],
                    record["fields"],
                    required=record.get("required", ()),
                    defaults=record.get("defaults"),
                    renames=record.get("renames"),
                )
                self._schemas.setdefault(schema.name, {})[schema.version] = schema

    def register(self, schema):
        """注册一个版本。

        同一类型同一版本号已存在则报错；存在相邻版本时必须与之兼容，
        不兼容在任何写入发生前抛出。
        """
        by_version = self._schemas.get(schema.name, {})
        if schema.version in by_version:
            raise SchemaError(
                "version already registered: %s v%s" % (schema.name, schema.version)
            )
        for neighbour in by_version.values():
            versions_between = [
                ver
                for ver in by_version
                if min(neighbour.version, schema.version)
                < ver
                < max(neighbour.version, schema.version)
            ]
            if versions_between:
                continue
            old, new = sorted((neighbour, schema), key=lambda item: item.version)
            ensure_compatible(old, new)
        self._schemas.setdefault(schema.name, {})[schema.version] = schema
        if self.path is not None:
            self._persist(schema)
        return schema

    def _persist(self, schema):
        record = {
            "name": schema.name,
            "version": schema.version,
            "fields": schema.fields,
            "required": list(schema.required),
            "defaults": schema.defaults,
            "renames": schema.renames,
        }
        line = json.dumps(record, sort_keys=True)
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def check_compatibility(self, old, new):
        """evschema.evolution.check_compatibility 的转发。"""
        return check_compatibility(old, new)

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
