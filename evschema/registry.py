"""schema 版本注册表。

按 事件类型 -> 版本号 保管 Schema，注册时不允许覆盖已有版本。
"""

from .schema import SchemaError


class SchemaRegistry:
    """事件类型的版本目录。"""

    def __init__(self):
        self._schemas = {}

    def register(self, schema):
        """注册一个版本，同一类型同一版本号已存在则报错。"""
        by_version = self._schemas.setdefault(schema.name, {})
        if schema.version in by_version:
            raise SchemaError(
                "version already registered: %s v%s" % (schema.name, schema.version)
            )
        by_version[schema.version] = schema
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
