"""autocmplt 现状演示。

第一段：搭一撮小词表，用朴素全量扫描按前缀取候选、看热度排序与扫描代价；
第二段：预留的字典树检索、Top-K 剪枝、增量学习、模糊补全与序列化演示位子
（见文末注释）。
"""

from autocmplt.scan import Autocomplete


def main():
    print("=== 朴素全量扫描补全 ===")
    a = Autocomplete()
    a.add("car", 3)
    a.add("cart", 5)
    a.add("carbon", 1)
    a.add("cat", 4)
    a.add("dog", 2)
    print("  词表 %s" % (a.words(),))
    print("  前缀 car 候选 -> %s" % a.candidates("car"))
    print("  前缀 cat 候选 -> %s" % a.candidates("cat"))
    print("  本次 scans -> %d" % a.scans())
    print("  词表规模 -> %d" % len(a))
    a.remove("cart")
    print("  删掉 cart 后前缀 car 候选 -> %s" % a.candidates("car"))

    # TODO(字典树与补全): 在 autocmplt 里补出字典树（按前缀取候选、子树聚合计数）、
    # 热度降序加字典序稳定的排序、Top-K 截断剪枝、learn 增量学习与 remove 清理计数、
    # 末尾字符差一的有界模糊补全、以及整树的序列化往返之后，在这里加一段演示：先
    # add 一撮词建好字典树，用 candidates 取一个前缀的候选并按热度打印，确认排序
    # 与朴素扫描一致、scans 比朴素扫描小；再用 top_k 只取前缀的前 K 个候选，打印
    # 结果并确认与不截断时的前 K 个一样；接着对某个词多调几次 learn，打印该词热度
    # 变化与候选次序的挪动；再对某个可能少打一个字符的前缀跑模糊补全，打印命中；
    # 最后把整棵树序列化成字节串再反序列化，打印往返后的候选与热度，确认与往返前
    # 一致。


if __name__ == "__main__":
    main()
