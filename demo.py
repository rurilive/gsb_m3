"""EventStore 现状演示。

第一段：注册 v1 schema，追加几条订单事件，看校验与落盘。
第二段：非法事件被拒，读回与统计。
第三段：预留的 schema 演进演示位子（见文末注释）。
"""

import os
import tempfile

from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, SchemaError
from evschema.store import EventStore


def main():
    registry = SchemaRegistry()
    registry.register(ORDER_V1)
    tmpdir = tempfile.mkdtemp(prefix="evschema-demo-")
    store = EventStore(os.path.join(tmpdir, "events.jsonl"), registry)

    print("=== 追加事件 ===")
    print("  append(o-1) -> seq", store.append("order", {"order_id": "o-1", "amount": 1200}))
    print(
        "  append(o-2) -> seq",
        store.append("order", {"order_id": "o-2", "amount": 300, "note": "gift"}),
    )
    try:
        store.append("order", {"order_id": "o-3", "amount": "many"})
    except SchemaError as exc:
        print("  非法事件被拒:", exc)

    print("=== 读回与统计 ===")
    for event in store.read():
        print("  ", event)
    before = store.stats()
    print(
        "  stats: events=%s appends=%s reads=%s"
        % (before["events"], before["appends"], before["reads"])
    )

    # TODO(schema 演进): 注册表支持兼容判定与落盘、read 支持升降级之后，
    # 在这里加一段演示：注册 v2 与 v3（改名字段加默认值），把历史事件
    # 读成最新形状再按 v1 降级读一遍，最后展示升级计数与方案构建次数。

    final = store.stats()
    print(
        "=== 收尾统计: events=%s appends=%s reads=%s ==="
        % (final["events"], final["appends"], final["reads"])
    )


if __name__ == "__main__":
    main()
