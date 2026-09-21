"""ChangeLog 现状演示。

第一段：单条时间线上追加变更、取全文、重建旧版本快照。
第二段：从同一版本分叉两条分支，按默认策略合并，看来源与冲突账。
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
    # 老张和小李从 v4 分叉，各自动手
    zhang = ChangeLog(clock=lambda: 0.0)
    zhang.append("doc-1", "title", "老张的标题", 5)
    zhang.append("doc-1", "status", "published", 5)
    zhang.append("doc-1", "tag", DELETED, 6)  # 老张删掉 tag

    li = ChangeLog(clock=lambda: 0.0)
    li.append("doc-1", "status", "archived", 6)  # 小李也改 status（撞车）
    li.append("doc-1", "owner", "li", 6)  # 小李补了负责人
    li.append("doc-1", "tag", "release-v2", 7)  # 删除之后又被人改

    result = merge("doc-1", {"zhang": zhang, "li": li}, clock=lambda: 0.0)

    print("  合并历史（带来源）：")
    for cand in result.entries:
        c = cand.change
        print(f"    v{c.version} [{cand.source}] {c.field} = {c.value!r}")

    print(f"  合并快照 at(99) -> {result.at(99)}")

    print("  冲突账（赢家 / 被消解的输家）：")
    for conf in result.conflicts:
        losers = ", ".join(f"{c.change.value!r}({c.source})" for c in conf.losers)
        print(f"    {conf.field}: {conf.winner.change.value!r}({conf.winner.source}) 胜，{losers} 负")


if __name__ == "__main__":
    main()
