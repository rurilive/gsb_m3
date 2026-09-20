"""相邻版本间的兼容性判定。

check_compatibility(old, new) 返回 Compatibility(ok, reasons)：
ok 为是否兼容，reasons 为不兼容理由（兼容时为空）。判据：
- 删字段拒绝（renames 声明的改名视为同一字段，不算删）
- 字段类型改变拒绝
- 旧的可选字段收紧成必填拒绝
- 新增字段必须带默认值
"""

from collections import namedtuple

Compatibility = namedtuple("Compatibility", ("ok", "reasons"))


def check_compatibility(old, new):
    """判定 old 能否安全演进到 new，返回 Compatibility。"""
    reasons = []
    if old.name != new.name:
        reasons.append("schema name changed: %s -> %s" % (old.name, new.name))
    renames = new.renames
    targets = {}
    for old_name, new_name in renames.items():
        if old_name not in old.fields:
            reasons.append(
                "rename source not in v%s: %s" % (old.version, old_name)
            )
        if new_name not in new.fields:
            reasons.append("rename target not declared: %s" % new_name)
        if new_name in targets:
            reasons.append(
                "rename target %s shared by %s and %s"
                % (new_name, targets[new_name], old_name)
            )
        targets.setdefault(new_name, old_name)
        if new_name in old.fields and new_name != old_name:
            reasons.append(
                "rename target %s already a field in v%s" % (new_name, old.version)
            )
    carried = set()
    for field, type_name in old.fields.items():
        new_name = renames.get(field, field)
        carried.add(new_name)
        if new_name not in new.fields:
            reasons.append("field removed: %s" % field)
            continue
        if new.fields[new_name] != type_name:
            reasons.append(
                "field %s type changed: %s -> %s"
                % (field, type_name, new.fields[new_name])
            )
        if field not in old.required and new_name in new.required:
            reasons.append("optional field became required: %s" % field)
    for field in new.fields:
        if field not in carried and field not in new.defaults:
            reasons.append("new field without default: %s" % field)
    return Compatibility(not reasons, tuple(reasons))
