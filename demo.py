"""joinlab 现状演示。

第一段：用 NestedLoopJoin 对两小表做等值连接。
第二段：预留的哈希连接与分块连接演示位子（见文末注释）。
"""

from joinlab.join import NestedLoopJoin


def main():
    print("=== 朴素等值连接 ===")
    join = NestedLoopJoin()
    left = [(1, "的"), (2, "嘛"), (2, "呀")]
    right = [(2, "x"), (3, "y"), (1, "z")]
    result = join.join(left, right, lambda row: row[0])
    print(f"  左表 = {left}")
    print(f"  右表 = {right}")
    print(f"  连接结果 = {result}")
    print(f"  配对数 = {join.count(left, right, lambda row: row[0])}")

    # TODO(哈希连接改造): 哈希连接与分块连接实现后，在这里加一段演示：
    # 小表建哈希表遍历大表探测、排序归并连接对拍、超出内存预算时的分块多轮处理，
    # 并与朴素连接核对结果一致。


if __name__ == "__main__":
    main()
