"""基线演示：直跑即可看到朴素查询的行为与规模痛点。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hldquery import PathQuerier, step_count


#          0
#        / | \
#       1  2  3
#      / \    |
#     4   5   6
PARENTS = [-1, 0, 0, 0, 1, 1, 3]
WEIGHTS = [3, 1, 4, 1, 5, 9, 2]


def first_section():
    q = PathQuerier(7, PARENTS, WEIGHTS)
    print("路径权值和 4->6 =", q.path_sum(4, 6))
    print("路径最大值 4->5 =", q.path_max(4, 5))
    print("子树权值和 1   =", q.subtree_sum(1))
    print("路径和最大与端点 =", q.best_path())
    print("逐级步数 4->6 =", q.walk_steps(4, 6))
    print("一次路径查询步数 4->6 =", step_count(q, 4, 6))
    q.update(5, 100)
    print("改点权后路径最大值 4->5 =", q.path_max(4, 5))


# TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    first_section()
