"""schemakit 现状演示。

第一段：用 migrate 把几条记录按固定规则改到 v1，看字段改写与版本戳。
第二段：预留的可组合迁移链、依赖排序、往返回滚与批内回滚演示位子（见文末注释）。
"""

from schemakit import migrate


def main():
    print("=== 记录迁移 ===")
    rows = [
        {"id": 1, "nickname": "ada"},
        {"id": 2, "name": "old", "nickname": "new"},
        {"id": 3},
    ]
    for row in rows:
        out = migrate(row)
        print("  输入:", row)
        print("  输出:", out)
    print("  原记录未被改写:", rows[0])

    # TODO(迁移链扩展): 可组合迁移链、依赖排序、往返回滚与批内回滚补齐后，在这里加一段演示：
    # 注册两条首尾相接的迁移拼出两跳的链，把记录从最低版本一路迁到目标版本；
    # 再沿同一条链反向回滚，用往返前后一致的记录证明 up 与 down 互逆；
    # 一批记录里混入一条会让迁移失败的坏记录，观察整批回滚、不留半迁移状态。


if __name__ == "__main__":
    main()
