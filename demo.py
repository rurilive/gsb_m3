"""EventStore 演示。

第一段：注册 v1 schema，追加几条订单事件，看校验与落盘。
第二段：非法事件被拒，读回与统计。
第三段（演进一）：注册 v2（加带默认值字段）与 v3（改名 + 加默认值），
注册表落盘后重启实例，历史事件升级到最新、再按 v1 降级读，
最后看升级条数与方案构建次数。
第三段（演进二）：预留给后续演进特性的演示位子。
"""

import os
import tempfile

from evschema.registry import SchemaRegistry
from evschema.evolve import check_compatibility
from evschema.schema import ORDER_V1, ORDER_V2, ORDER_V3, Schema, SchemaError
from evschema.store import EventStore


def main():
    tmpdir = tempfile.mkdtemp(prefix="evschema-demo-")
    events_path = os.path.join(tmpdir, "events.jsonl")
    registry_path = os.path.join(tmpdir, "registry.json")

    registry = SchemaRegistry(registry_path)
    registry.register(ORDER_V1)
    store = EventStore(events_path, registry)

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

    print("=== schema 演进一：v2 加字段、v3 改名，注册表落盘重启 ===")
    registry.register(ORDER_V2)
    registry.register(ORDER_V3)
    v_bad = Schema("order", 9, {"order_id": "str"}, required=("order_id",))
    decisions_before = {
        "v1->v2": check_compatibility(ORDER_V1, ORDER_V2)[0],
        "v2->v3": check_compatibility(ORDER_V2, ORDER_V3)[0],
        "v3->v_bad(删字段)": check_compatibility(ORDER_V3, v_bad)[0],
    }
    print("  关之前判定:", decisions_before)
    reopened_registry = SchemaRegistry(registry_path)
    decisions_after = {
        "v1->v2": check_compatibility(ORDER_V1, ORDER_V2)[0],
        "v2->v3": check_compatibility(ORDER_V2, ORDER_V3)[0],
        "v3->v_bad(删字段)": check_compatibility(ORDER_V3, v_bad)[0],
    }
    print("  重启后版本:", reopened_registry.versions("order"))
    print("  重启后判定:", decisions_after, "一致:", decisions_before == decisions_after)
    evolved_store = EventStore(events_path, reopened_registry)
    latest = evolved_store.read()
    for event in latest:
        print("   升级到最新:", event)
    print("  按 v1 降级读:")
    for event in evolved_store.read(version=1):
        print("   ", event)
    fresh_read = EventStore(events_path, reopened_registry).read()
    print("  全新实例再读，文件未动、照样升到 v3:", [event["v"] for event in fresh_read])
    estats = evolved_store.stats()
    print(
        "  stats: upgraded=%s plans_built=%s"
        % (estats["upgraded"], estats["plans_built"])
    )

    # 第三段（演进二）：预留。后续演进特性在此演示。
    print("=== schema 演进二：（预留，待后续演进特性接入）===")

    final = store.stats()
    print(
        "=== 收尾统计: events=%s appends=%s reads=%s upgraded=%s plans_built=%s ==="
        % (
            final["events"],
            final["appends"],
            final["reads"],
            final["upgraded"],
            final["plans_built"],
        )
    )


if __name__ == "__main__":
    main()
