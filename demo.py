"""rangeidx 现状演示。

第一段：造一张用户表，用线性扫描查一个字段的等值条件，看到命中行数与访问计数；
第二段：预留的二级有序索引演示位子（见文末注释）。
"""

from rangeidx.table import Table


def main():
    print("=== 线性扫描 ===")
    users = Table("users")
    for i in range(1, 6):
        users.insert({"id": i, "name": "u%02d" % i, "age": 20 + i})
    users.reset_access_count()
    hit = users.scan(lambda r: r["age"] == 23)
    print("  表 %d 行，命中 %d 行，访问计数 %d" % (
        users.count(),
        len(hit),
        users.access_count,
    ))
    print("  命中记录 %s" % (hit,))

    # TODO(二级有序索引): 在 rangeidx 里补出按字段建的有序索引、范围查询与前缀
    # 查询之后，在这里加一段演示：为一个字段建索引，做一次范围查询与前缀查询，
    # 打印结果是否有序，并比较访问计数说明这次查询没有走全表扫描。


if __name__ == "__main__":
    main()