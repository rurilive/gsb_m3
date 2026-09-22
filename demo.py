"""topoflow 现状演示。

跑几段导入工具真实碰到过的场景：重复的加边日志、重复的删边日志、
成环后又删回来的批次、同一份图的两条操作路径，最后量一下大图上
删一条边的代价。每段都把引擎的输出和 reference.py 的全量结果摆在一起。
"""

import sys
import time

from topoflow.engine import IncrementalTopo
from topoflow.reference import CycleError, order_problems, reference_is_acyclic, reference_order


def show_order(engine, label):
    """打印引擎导出的一份序，顺带和全量参考核一遍。"""
    try:
        order = engine.order()
    except CycleError:
        print("  %s: 报环，导不出序" % label)
        return None
    print("  %s: %s" % (label, order))
    print("    核序结果: %s" % (order_problems(engine.snapshot(), order) or "没问题"))
    return order


def duplicate_adds():
    print("\n=== 更新日志里有重复的边对 ===")
    engine = IncrementalTopo()
    for u, v in [("db", "app"), ("cache", "app"), ("app", "web"),
                 ("db", "app"), ("queue", "web"), ("web", "report")]:
        engine.add_edge(u, v)
    print("  app 的入度: %d，全量口径是 2" % engine.in_degree("app"))
    print("  全量参考认为无环: %s" % reference_is_acyclic(engine.snapshot()))
    show_order(engine, "引擎导出的序")


def journal_replay():
    print("\n=== 删边日志里有重复条目，同一条边先删后加 ===")
    chain = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "g")]
    engine = IncrementalTopo()
    engine.add_edges(chain)
    show_order(engine, "初始序")
    engine.remove_edges(chain + chain)      # 每一对在日志里出现了两次
    engine.add_edges(chain)                 # 同一条边紧接着又补回来
    print("  g 的入度: %d，全量口径是 1" % engine.in_degree("g"))
    show_order(engine, "回放之后的序")


def cycle_flag():
    print("\n=== 成环的边删掉之后，环标记还在 ===")
    engine = IncrementalTopo()
    engine.add_edges([("a", "b"), ("b", "c"), ("c", "d")])
    show_order(engine, "初始序")
    engine.add_edges([("d", "a"), ("e", "f")])      # d -> a 封环，e -> f 只是批里的尾巴
    print("  补上 d -> a 之后，全量参考认为无环: %s，引擎认为无环: %s"
          % (reference_is_acyclic(engine.snapshot()), engine.is_acyclic()))
    engine.remove_edge("d", "a")                    # 删掉真正封环的那条边
    print("  删掉 d -> a 之后，全量参考认为无环: %s，引擎认为无环: %s"
          % (reference_is_acyclic(engine.snapshot()), engine.is_acyclic()))
    engine.add_edges([("x", "y"), ("y", "x")])      # 再塞一个环
    engine.is_acyclic()
    engine.remove_edge("e", "f")                    # 删的却是批里那条尾巴
    print("  删掉 e -> f 之后，全量参考认为无环: %s，引擎认为无环: %s"
          % (reference_is_acyclic(engine.snapshot()), engine.is_acyclic()))
    show_order(engine, "引擎导出的序")


def history_drift():
    print("\n=== 同一份图，两条操作路径导出两份次序 ===")
    pairs = [("n0", "n1"), ("n2", "n3"), ("n4", "n5"),
             ("n6", "n7"), ("n8", "n9"), ("n10", "n11")]
    plain = IncrementalTopo()
    plain.add_edges(pairs)
    first = plain.order()

    detour = IncrementalTopo()
    detour.add_edges(pairs)
    detour.order()
    detour.add_edge("n1", "n10")        # 中途多试了一版，马上又撤掉
    detour.order()
    detour.remove_edge("n1", "n10")
    second = detour.order()

    print("  一路直建的序: %s" % first)
    print("  中途绕了一下的序: %s" % second)
    print("  两份图的边一致: %s，两份序一致: %s"
          % (plain.snapshot().edges() == detour.snapshot().edges(), first == second))
    print("  全量参考的序: %s" % reference_order(plain.snapshot()))


def removal_cost(size):
    print("\n=== 十万节点图上删一条边（size=%d）===" % size)
    pairs = [("t%d" % i, "t%d" % (i + 1)) for i in range(size - 1)]
    engine = IncrementalTopo()
    engine.add_edges(pairs)
    engine.order()

    start = time.perf_counter()
    engine.remove_edge("t%d" % (size // 2), "t%d" % (size // 2 + 1))
    engine.order()
    cost = time.perf_counter() - start

    graph = engine.snapshot()
    start = time.perf_counter()
    reference_order(graph)
    baseline = time.perf_counter() - start

    print("  删一条边到拿到新序: %.3f s" % cost)
    print("  整图重排一遍: %.3f s" % baseline)
    print("  比值: %.2f" % (cost / baseline))


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
    duplicate_adds()
    journal_replay()
    cycle_flag()
    history_drift()
    removal_cost(size)


if __name__ == "__main__":
    main()
