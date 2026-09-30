"""polyhash 现状演示。

第一段：建一个小串池，做判等、最长公共前缀与查重，观察访问计数随串长增长；
第二段：预留的滚动哈希演示位子（见文末注释）。
"""

from polyhash.core import StringPool, build_text


def main():
    print("=== 逐字符比较基线 ===")
    pool = StringPool()
    pool.add(build_text(11, 400))
    pool.add(build_text(11, 400))
    pool.add(build_text(12, 400))

    print("  串池大小 %d" % pool.size())
    print("  0 与 1 判等 %s" % pool.equal(0, 1))
    print("  0 与 2 判等 %s" % pool.equal(0, 2))
    print("  0 与 1 的最长公共前缀 %d" % pool.lcp(0, 1))
    print("  查重分组 %s" % (pool.duplicates(),))
    print("  累计字符比较次数 %d" % pool.access_count)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
