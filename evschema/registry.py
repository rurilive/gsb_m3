"""schema 版本注册表。

按 事件类型 -> 版本号 保管 Schema，注册时不允许覆盖已有版本；
注册新版本前先用 check_compatibility 与该类型当前最高版本比对，
不兼容的演进被拒。

构造时给 path 即落盘：每次注册成功都写回该 JSON 文件，
再用同一路径新建实例时，已注册的版本与兼容判定结果完全一致。
"""

import json
import os
import tempfile

from .evolve import check_compatibility
from .schema import Schema, SchemaError


class SchemaRegistry:
    """事件类型的版本目录。"""

    def __init__(self, path=None):
        self.path = path
        self._schemas = {}
        if path is not None and os.path.exists(path):
            self._load()

    def register(self, schema):
        """注册一个版本。

        同一类型同一版本号已存在则报错；版本号高于现有版本时，
        必须与当前最高版本兼容，否则报错且不写入。
        """
        by_version = self._schemas.setdefault(schema.name, {})
        if schema.version in by_version:
            raise SchemaError(
                "version already registered: %s v%s" % (schema.name, schema.version)
            )
        if by_version:
            current = by_version[max(by_version)]
            if schema.version > current.version:
                ok, reasons = check_compatibility(current, schema)
                if not ok:
                    raise SchemaError(
                        "incompatible schema %s v%s: %s"
                        % (schema.name, schema.version, "; ".join(reasons))
                    )
        by_version[schema.version] = schema
        self._save()
        return schema

    def check_compatibility(self, name, new):
        """便捷封装：拿该类型当前最高版本与 new 比对，返回 (ok, reasons)。"""
        return check_compatibility(self.latest(name), new)

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

    def _to_dict(self, schema):
        return {
            "name": schema.name,
            "version": schema.version,
            "fields": schema.fields,
            "required": list(schema.required),
            "defaults": schema.defaults,
            "renames": schema.renames,
        }

    def _save(self):
        if self.path is None:
            return
        payload = [
            self._to_dict(self._schemas[name][version])
            for name in sorted(self._schemas)
            for version in sorted(self._schemas[name])
        ]
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        fd, tmp_path = tempfile.mkstemp(
            dir=directory or ".", prefix=".registry-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, sort_keys=True)
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _load(self):
        with open(self.path, encoding="utf-8") as fh:
            payload = json.load(fh)
        for item in payload:
            schema = Schema(
                item["name"],
                item["version"],
                item["fields"],
                required=item.get("required", ()),
                defaults=item.get("defaults"),
                renames=item.get("renames"),
            )
            self._schemas.setdefault(schema.name, {})[schema.version] = schema
