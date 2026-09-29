"""dagwer 演示脚本。

第一段演示基线能力：给定若干条边，判断依赖图是否成环。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dagwer import DagCheck


def demo_baseline():
    print("== 基线：成环检查 ==")
    acyclic = [("a", "b"), ("b", "c"), ("c", "d")]
    cyclic = [("a", "b"), ("b", "c"), ("c", "a")]
    print("无环样例 has_cycle =", DagCheck(acyclic).has_cycle())
    print("有环样例 has_cycle =", DagCheck(cyclic).has_cycle())


def demo_graph_validation():
    # TODO(依赖图改造): 在此补一轮依赖图校验演示，
    # 包括无环图的确定拓扑序与分层输出，以及有环时的环节点集合与最短环路径。
    pass


if __name__ == "__main__":
    demo_baseline()
    demo_graph_validation()
