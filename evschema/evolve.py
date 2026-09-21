"""schema 版本演进：兼容判定与相邻版本之间的迁移方案。

兼容判据（old -> new，逐条收集，全部通过才兼容）：

- 必须是同名 schema；
- renames 里每个旧名都得在 old 中存在、新名都得在 new 中存在，
  且旧名已消失、新名原本不在 old 中；
- 改名后的字段类型必须与旧类型一致；
- 未改名字段不得删除、不得改类型；
- 旧可选字段不得收紧成必填（保留或改名后收紧都拒）；旧必填放开为
  可选则允许，旧数据一定带值；
- 真正新增的字段（不是改名目标）必须在 defaults 中给出默认值。

迁移以相邻版本为单步，升级做「改名 + 新增字段补默认值」，
降级做「反向改名 + 删除高版本新增字段」。单步方案按 (类型, 低版本号)
缓存，只构建一次。
"""


def check_compatibility(old, new):
    """判定 new 是否可作为 old 的新版本，返回 (ok, reasons)。

    ok 为 True 时 reasons 为空列表；否则 reasons 列出全部拒绝理由。
    """
    reasons = []
    if old.name != new.name:
        return False, ["schema name mismatch: %s != %s" % (old.name, new.name)]

    renames = new.renames
    for source in renames:
        if source not in old.fields:
            reasons.append("rename source missing in old schema: %s" % source)

    claimed = set()
    for source, target in renames.items():
        if target not in new.fields:
            reasons.append("rename target missing in new schema: %s" % target)
            continue
        if source in old.fields and source in new.fields:
            reasons.append("rename source still present in new schema: %s" % source)
        if target not in old.fields:
            claimed.add(target)
        else:
            reasons.append("rename target already exists in old schema: %s" % target)

    for source, target in renames.items():
        if source in old.fields and target in new.fields:
            if old.fields[source] != new.fields[target]:
                reasons.append(
                    "renamed field %s changes type %s -> %s"
                    % (source, old.fields[source], new.fields[target])
                )
            if source not in old.required and target in new.required:
                reasons.append(
                    "renamed optional field tightened to required: %s -> %s"
                    % (source, target)
                )

    for field, type_name in old.fields.items():
        if field in renames:
            continue
        if field not in new.fields:
            reasons.append("field removed: %s" % field)
        elif new.fields[field] != type_name:
            reasons.append(
                "field %s changes type %s -> %s"
                % (field, type_name, new.fields[field])
            )

    for field in new.required:
        if (
            field in old.fields
            and field not in renames
            and field not in old.required
        ):
            reasons.append("optional field tightened to required: %s" % field)

    for field in new.fields:
        if field in old.fields or field in claimed:
            continue
        if field not in new.defaults:
            reasons.append("new field without default: %s" % field)

    return not reasons, reasons


class StepPlan:
    """两个相邻版本之间的单步迁移方案，同一步可升可降。"""

    __slots__ = (
        "name",
        "low_version",
        "high_version",
        "renames",
        "up_defaults",
        "down_drop",
    )

    def __init__(self, low, high):
        renames = {}
        claimed = set()
        for source, target in high.renames.items():
            if (
                source in low.fields
                and target in high.fields
                and source not in high.fields
                and target not in low.fields
            ):
                renames[source] = target
                claimed.add(target)
        self.name = low.name
        self.low_version = low.version
        self.high_version = high.version
        self.renames = renames
        self.up_defaults = {
            field: high.defaults[field]
            for field in high.fields
            if field not in low.fields and field not in claimed
        }
        self.down_drop = [
            field
            for field in high.fields
            if field not in low.fields and field not in claimed
        ]

    def upgrade(self, data):
        """低版本数据就地升级到高版本。"""
        for source, target in self.renames.items():
            if source in data:
                data[target] = data.pop(source)
        for field, value in self.up_defaults.items():
            if field not in data:
                data[field] = value
        return data

    def downgrade(self, data):
        """高版本数据就地降级到低版本。"""
        for field in self.down_drop:
            data.pop(field, None)
        for source, target in self.renames.items():
            if target in data:
                data[source] = data.pop(target)
        return data
