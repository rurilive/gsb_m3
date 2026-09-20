"""schema 版本演进：兼容判定与相邻版本之间的转换方案。

兼容判据（旧版本 -> 新版本，任一不满足则拒绝注册）：
- 字段被删除且未在 renames 中声明去向：拒绝；
- 字段类型变化（包括改名后新名的类型与旧名不一致）：拒绝；
- 旧版本中的可选字段在新版本中收紧成必填：拒绝；
- 新增字段必须在 defaults 中给出默认值；
- renames 的旧名必须在旧版本存在、新名在新版本声明，类型一致，
  新名不能重复，旧名与新名不能相同。

转换方案 EdgePlan 只描述一对相邻版本之间的差异，按 (类型, 低版本)
缓存复用；升级与降级共用同一方案的两个方向。
"""

import copy

from .schema import SchemaError


def check_compatibility(old, new):
    """判定 new 是否能作为 old 的后续版本注册。

    返回 (ok, reason)：ok 为 True 时 reason 是空串；False 时 reason
    给出第一条不兼容的理由。
    """
    if new.name != old.name:
        return False, "schema name differs: %s vs %s" % (old.name, new.name)
    if new.version <= old.version:
        return False, "new version %s is not higher than %s" % (
            new.version,
            old.version,
        )

    for source, target in new.renames.items():
        if source not in old.fields:
            return False, "renamed field %s missing in old schema" % source
        if target not in new.fields:
            return False, "rename target %s not declared" % target
        if source == target:
            return False, "field %s renamed to itself" % source
        if old.fields[source] != new.fields[target]:
            return False, (
                "rename %s -> %s changes type %s to %s"
                % (source, target, old.fields[source], new.fields[target])
            )
    rename_targets = list(new.renames.values())
    if len(set(rename_targets)) != len(rename_targets):
        return False, "rename targets collide: %s" % sorted(
            {name for name in rename_targets if rename_targets.count(name) > 1}
        )
    for target in rename_targets:
        if target in old.fields:
            return False, "rename target %s already exists in old schema" % target
    new_names = set(new.fields)
    old_names = set(old.fields)
    renamed_sources = set(new.renames)

    for name in old_names - new_names:
        if name not in renamed_sources:
            return False, "field removed without rename: %s" % name

    for name in new_names & old_names:
        if name in renamed_sources:
            continue
        if old.fields[name] != new.fields[name]:
            return False, "field %s changes type %s to %s" % (
                name,
                old.fields[name],
                new.fields[name],
            )

    for name in old_names:
        if name in old.required:
            continue
        carried = new.renames.get(name, name)
        if carried in new.fields and carried in new.required:
            return False, "optional field %s tightened to required" % (
                "%s -> %s" % (name, carried) if carried != name else name
            )

    for name in new_names - old_names:
        if name in rename_targets:
            continue
        if name not in new.defaults:
            return False, "new field %s requires a default value" % name

    return True, ""


def ensure_compatible(old, new):
    """check_compatibility 的抛错包装，供注册路径使用。"""
    ok, reason = check_compatibility(old, new)
    if not ok:
        raise SchemaError(
            "incompatible schema %s v%s -> v%s: %s"
            % (old.name, old.version, new.version, reason)
        )


def _default_value(schema, name):
    value = schema.defaults[name]
    if isinstance(value, (dict, list)):
        return copy.deepcopy(value)
    return value


class EdgePlan:
    """一对相邻版本 old(low) -> new(high) 的字段映射方案。"""

    def __init__(self, old, new):
        self.name = old.name
        self.low = old.version
        self.high = new.version
        self.upgrade_ops = []
        self.downgrade_ops = []
        for target in new.field_names():
            source = None
            for src, tgt in new.renames.items():
                if tgt == target:
                    source = src
                    break
            if source is None and target in old.fields:
                source = target
            if source is not None:
                self.upgrade_ops.append(("carry", source, target))
                if target in new.defaults:
                    self.upgrade_ops.append(("default", target, new))
                self.downgrade_ops.append(("carry", target, source))
                continue
            if target in new.defaults:
                self.upgrade_ops.append(("default", target, new))
                self.downgrade_ops.append(("drop", target))
            else:
                self.upgrade_ops.append(("carry", target, target))
                self.downgrade_ops.append(("carry", target, target))
        for source in old.field_names():
            target = new.renames.get(source)
            if target is None and source not in new.fields:
                self.downgrade_ops.append(("drop", source))

    def upgrade(self, data):
        result = {}
        for op in self.upgrade_ops:
            kind = op[0]
            if kind == "carry":
                _, source, target = op
                if source in data:
                    result[target] = data[source]
            else:
                _, target, schema = op
                if target not in result:
                    result[target] = _default_value(schema, target)
        return result

    def downgrade(self, data):
        result = {}
        for op in self.downgrade_ops:
            kind = op[0]
            if kind == "carry":
                _, source, target = op
                if source in data:
                    result[target] = data[source]
            else:
                _, target = op
                result.pop(target, None)
        return result


def build_edge(old, new):
    """构建相邻版本方案前再过一遍兼容闸门。"""
    ensure_compatible(old, new)
    return EdgePlan(old, new)
