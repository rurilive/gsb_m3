"""lfux 现状演示。

第一段：定容缓存的写入与读回、满时按插入先后淘汰、peek 不改变状态。
第二段：频次淘汰演示的占位（见文末注释）。
"""

from lfux import FifoCache


def main():
    print("=== 定容缓存读写 ===")
    c = FifoCache(3)
    c.put("alpha", 1)
    c.put("beta", 2)
    c.put("gamma", 3)
    print("  命中 alpha:", c.get("alpha"))
    print("  未命中 delta:", c.get("delta"))
    print("  当前键（插入序）:", c.keys())

    print("=== 满时按插入先后淘汰 ===")
    c.get("alpha")
    c.get("alpha")
    print("  反复读 alpha 后，它的取值:", c.get("alpha"))
    c.put("delta", 4)
    print("  写入 delta 后，当前键:", c.keys())
    print("  alpha 是否还在:", "alpha" in c)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
