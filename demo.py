"""ChangeLog 现状演示。

第一段：单条时间线上追加变更、取全文、重建旧版本快照。
第二段：两条分支从同一版本分叉后合并，含冲突消解与删除语义。
"""

from changelogd.changelog import DELETED, ChangeLog
from changelogd.merge import merge


class Tick:
    """演示用注入时钟：每次调用前进 1 秒。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        self.now += 1.0
        return self.now


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
    zhang = ChangeLog(clock=Tick(100.0))
    zhang.append("doc-1", "title", "老张的标题", 5)
    zhang.append("doc-1", "status", "review", 5)
    zhang.append("doc-1", "tag", DELETED, 6)  # 老张把标签删了
    li = ChangeLog(clock=Tick(200.0))
    li.append("doc-1", "status", "published", 5)
    li.append("doc-1", "tag", "release", 6)  # 小李还在改标签
    li.append("doc-1", "owner", "li", 7)

    merged = ChangeLog(clock=Tick())
    result = merge(
        merged,
        "doc-1",
        [("老张", zhang.history("doc-1")), ("小李", li.history("doc-1"))],
        start_version=8,
    )

    print("  合并结果（带来源）：")
    for entry in result.entries:
        c = entry.change
        print(f"    v{c.version} {c.field} = {c.value!r}  <- {entry.source}")

    print("  冲突与输家：")
    for conflict in result.conflicts:
        losers = ", ".join(
            f"{o.source}:{o.change.value!r}" for o in conflict.losers)
        print(f"    {conflict.field}: {conflict.winner.source} 胜，"
              f"被消解：{losers}")

    print(f"  最终快照：{result.snapshot()}")
    print(f"  merged.at('doc-1', 11) -> {merged.at('doc-1', 11)}")


if __name__ == "__main__":
    main()
