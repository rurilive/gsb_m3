"""ChangeLog 演示。

第一段：单条时间线上追加变更、取全文、重建旧版本快照。
第二段：两条分支从同一版本分叉后合并，含冲突消解与删除语义。
"""

from changelogd.changelog import DELETED, ChangeLog
from changelogd.merge import merge


def main():
    log = ChangeLog(clock=lambda: 0.0)

    print("=== 单线变更 ===")
    log.append("doc-1", "title", "草稿", 1)
    log.append("doc-1", "status", "draft", 1)
    log.append("doc-1", "title", "定稿", 3)
    log.append("doc-1", "tag", "release", 4)

    print("  变更全文：")
    for c in log.history("doc-1"):
        print(f"    v{c.version} {c.field} = {c.value!r}")

    for v in (1, 3, 4):
        print(f"  at('doc-1', {v}) -> {log.at('doc-1', v)}")

    print("\n=== 多分支合并 ===")

    def fork():
        clone = ChangeLog(clock=lambda: 0.0)
        for c in log.history("doc-1"):
            if c.version <= 3:
                clone.append(c.obj, c.field, c.value, c.version)
        return clone

    # 老张和小李从 v3 分叉，各自动手
    laozhang = fork()
    laozhang.append("doc-1", "title", "终稿", 4)
    laozhang.append("doc-1", "status", "review", 4)
    laozhang.append("doc-1", "tag", DELETED, 4)  # 老张把标签删了

    xiaoli = fork()
    xiaoli.append("doc-1", "status", "published", 5)
    xiaoli.append("doc-1", "tag", "release-v2", 5)  # 小李却又改了标签
    xiaoli.append("doc-1", "owner", "xiaoli", 5)

    ticks = (10.0 + i for i in range(100))
    result = merge(
        "doc-1",
        {"laozhang": laozhang, "xiaoli": xiaoli},
        base_version=3,
        clock=lambda: next(ticks),
    )

    print("  合并结果（含来源标注）：")
    for c in result.changes:
        if c.change.version > 3:
            print(
                f"    v{c.change.version} {c.change.field} = {c.change.value!r}"
                f"    <- {c.origin}"
            )

    print("  冲突账本：")
    for conflict in result.conflicts:
        losers = ", ".join(
            f"{c.origin}={c.change.value!r}" for c in conflict.losers
        )
        print(
            f"    {conflict.field}: 赢家 {conflict.winner.origin}"
            f"={conflict.winner.change.value!r}，被消解：{losers}"
        )

    print(f"  合并后快照 at('doc-1', 5) -> {result.log.at('doc-1', 5)}")
    print("  （tag 被老张删除，虽小李改过一次，快照里不再出现；history 仍可见全程）")


if __name__ == "__main__":
    main()
