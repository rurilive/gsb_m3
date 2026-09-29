"""raftlite 自有异常类型。

日志与状态机的可诊断错误都在这里定义，全部继承 RaftError，调用方只捕捉
RaftError 即可一次性接住所有错误。多节点复制、任期与选举、冲突回退相关的
错误留待后续在这一层扩展。
"""


class RaftError(Exception):
    """raftlite 所有可诊断错误的基类。"""


class InvalidIndex(RaftError):
    """索引非法：越界、为负或不是整数。"""


class UnknownNode(RaftError):
    """未知节点：操作指向的节点不在本次模拟的节点集合里。"""