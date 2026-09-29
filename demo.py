"""colstore 现状演示。

第一段：搭一个三列的小存储，整列取回并看存储总量；
第二段：预留的编码与区间扫描演示位子（见文末注释）。
"""

from colstore.column import Column
from colstore.store import Store


def main():
    print("=== 朴素列存储 ===")
    store = Store(
        [
            Column("id", [1, 2, 3, 4, 5, 6]),
            Column("city", [1, 1, 1, 2, 2, 2]),
            Column("amount", [10, 10, 10, 20, 20, 20]),
        ]
    )
    print("  列 %s，行数 %d" % (store.column_names, store.num_rows()))
    print("  city 整列取回 %s" % (store.scan("city"),))
    print("  第 0 行 %s" % (store.get_row(0),))
    print("  存储总量 %d" % store.storage_size())

    # TODO(多种列编码与惰性扫描): 在 colstore 里补出 RLE、字典编码、delta 三种列编码与
    # 自动选码、惰性区间解码、谓词下推与行更新之后，在这里加一段演示：对递增列与低基数列
    # 看各自编码后的存储量与原样存储的对比，对一段行区间做只解所需区间的扫描并打印解码
    # 次数，再对一个编码列做一次带谓词的扫描看跳过了哪些区间。


if __name__ == "__main__":
    main()