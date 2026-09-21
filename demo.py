"""membersim 现状演示。

第一段：手工把节点标下线，看各节点自己的成员视图。
第二段：用整表同步把状态从一个节点搬到另一个节点。
第三段：预留的周期性心跳与分区愈合演示位子（见文末注释）。
"""

from membersim import Cluster


def main():
    cluster = Cluster(["n1", "n2", "n3", "n4"], period=1.0)

    print("=== 手工标记与查询 ===")
    cluster.node("n1").mark_down("n3")
    cluster.node("n2").mark_down("n3")
    views = cluster.views()
    for node_id in sorted(views):
        print(f"  {node_id} 看到 {views[node_id]}")
    print(f"  视图一致吗：{cluster.views_agree()}")

    print("=== 整表同步：n1 把视图塞给 n4 ===")
    cluster.node("n1").announce("n4")
    cluster.step()
    print(f"  一步之后 n4 看到 {cluster.node('n4').view()}")

    # TODO(成员协议改造): 周期性心跳、疑似到死亡的升级、分区愈合后的
    # 收敛演示都加在这一段下面。


if __name__ == "__main__":
    main()
