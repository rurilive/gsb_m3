"""基线写入器：向全部副本广播写，等待全体副本都成功后才算写成功。

现在没有任何法定人数、读修复或版本的味道：一次 put 要所有副本都点头，
只要有一个副本慢或不可达，整个写就被拖住甚至直接失败；读也只是逐个副本
取值，谁先回答就用谁，不关心副本之间是否一致。
"""


def _node_id(replica):
    """取副本的节点标识，没有显式 id 就用对象在其容器里的位置占位。"""
    return getattr(replica, "node_id", id(replica))


class ReplicaUnavailable(Exception):
    """副本不可达或拒绝服务时抛出。"""


class WriteAll:
    """全体写入器：写要所有副本成功，读逐个副本取值。

    副本是外部注入的对象，本类只依赖最少的约定：
    set(key, value) 落一次写，get(key) 取回值（键不存在返回 None）。
    这样测试可以塞进可预测的模拟副本，结果完全确定。
    """

    def __init__(self, replicas):
        self.replicas = list(replicas)
        if not self.replicas:
            raise ValueError("至少需要一个副本")

    def put(self, key, value):
        """向全部副本广播写；任一副本失败即整体失败。"""
        for replica in self.replicas:
            try:
                replica.set(key, value)
            except Exception as exc:  # noqa: BLE001 - 基线只关心成败
                raise ReplicaUnavailable(
                    "副本写入失败: %s" % (_node_id(replica),)
                ) from exc
        return value

    def get(self, key):
        """读某个键：按副本顺序问一遍，取第一个非空回答。

        基线没有版本概念，也不比较各副本的答复，谁先答就用谁。
        """
        for replica in self.replicas:
            try:
                value = replica.get(key)
            except Exception:  # noqa: BLE001 - 副本读失败就跳过
                continue
            if value is not None:
                return value
        return None

    def replicas_ok(self):
        """所有副本都可用时返回真。"""
        for replica in self.replicas:
            try:
                replica.get("__probe__")
            except Exception:  # noqa: BLE001
                return False
        return True
