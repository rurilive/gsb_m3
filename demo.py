"""基础字符串缓冲现状演示。

第一段：按下标插入一段文本，再删掉几个字符。
第二段：预留的协同文本演示位子（见文末注释）。
"""

from colitext.buffer import TextBuf


def main():
    print("=== 本地按下标增删 ===")
    buf = TextBuf()
    buf.insert(0, "hello world")
    print(f"  插入后 -> {buf.text()!r}")

    buf.delete(5, 1)
    print(f"  删掉空格后 -> {buf.text()!r}")

    buf.insert(5, " colitext")
    print(f"  再插入一段后 -> {buf.text()!r}")

    snap = buf.text()
    buf.delete(0, len(buf))
    print(f"  清空后原快照仍为 -> {snap!r}")

    # TODO(协同文本改造): 位置标识、并发合并、删除标记、交换律与幂等、快照与压缩
    # 实现在这里加一段演示：
    # 造两个副本共享同一段初始文本，各自在中间独立插入一段不同的文本，
    # 交换双方的操作日志后重放，观察两边的文本收敛到完全相同，
    # 再演示一方插入另一方并发删除同一区间时，先插后删的顺序不影响最终结果，
    # 并给出位置标识不因对方插入而错乱的对照。


if __name__ == "__main__":
    main()
