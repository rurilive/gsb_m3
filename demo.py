"""EventStore schema 演进演示。

第一段：兼容判定闸门、v1/v2/v3 注册落盘、历史事件升级读、旧版本
降级读、升级计数与方案构建次数，以及同路径重建注册表后的判定一致性。
第二段：留位（见文末注释），预留给未来的写时迁移/在线回填能力。
"""

import os
import tempfile

from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, Schema, SchemaError
from evschema.store import EventStore


ORDER_V2 = Schema(
    "order",
    2,
    {"order_id": "str", "amount": "int", "note": "str", "channel": "str"},
    required=("order_id", "amount"),
    defaults={"note": "", "channel": "unknown"},
)

ORDER_V3 = Schema(
    "order",
    3,
    {
        "order_id": "str",
        "total": "int",
        "note": "str",
        "channel": "str",
        "segment": "str",
    },
    required=("order_id", "total"),
    defaults={"note": "", "channel": "unknown", "segment": "none"},
    renames={"amount": "total"},
)


def section_one(tmpdir):
    registry_path = os.path.join(tmpdir, "registry.jsonl")
    registry = SchemaRegistry(registry_path)
    store = EventStore(os.path.join(tmpdir, "events.jsonl"), registry)

    print("=== 兼容判定闸门 ===")
    ok, reason = registry.check_compatibility(ORDER_V1, ORDER_V2)
    print("  v1 -> v2（新增带默认值字段）:", ok)
    ok, reason = registry.check_compatibility(ORDER_V2, ORDER_V3)
    print("  v2 -> v3（amount 改名 total、新增 segment）:", ok)
    dropped = Schema(
        "order", 9,
        {"order_id": "str", "amount": "int"},
        required=("order_id", "amount"),
    )
    ok, reason = registry.check_compatibility(ORDER_V1, dropped)
    print("  删字段被拒:", not ok, "|", reason)
    guard = SchemaRegistry()
    guard.register(ORDER_V1)
    tightened = Schema(
        "order", 2,
        {"order_id": "str", "amount": "int", "note": "str"},
        required=("order_id", "amount", "note"),
        defaults={"note": ""},
    )
    try:
        guard.register(tightened)
    except SchemaError as exc:
        print("  注册不兼容版本抛错:", exc)

    print("=== 注册落盘并写历史事件 ===")
    registry.register(ORDER_V1)
    registry.register(ORDER_V2)
    registry.register(ORDER_V3)
    print("  append v1 -> seq",
          store.append("order", {"order_id": "o-1", "amount": 1200}, version=1))
    print("  append v2 -> seq",
          store.append(
              "order",
              {"order_id": "o-2", "amount": 300, "note": "gift",
               "channel": "shop"},
              version=2,
          ))
    print("  append v3 -> seq",
          store.append(
              "order",
              {"order_id": "o-3", "total": 80, "note": "vip",
               "channel": "web", "segment": "a"},
              version=3,
          ))
    try:
        store.append("order", {"order_id": "o-4", "amount": "many"}, version=1)
    except SchemaError as exc:
        print("  非法事件被拒:", exc)

    print("=== 升级读（不传 version，投影到最新 v3）===")
    for event in store.read():
        print("  ", event)

    print("=== 降级读（v1：丢新字段，改名还原）===")
    for event in store.read(version=1):
        print("  ", event)

    print("=== 同路径重建：版本、判定与读投影 ===")
    reopened = SchemaRegistry(registry_path)
    print("  恢复版本:", reopened.versions("order"))
    print("  v2 -> v3 判定:", reopened.check_compatibility(
        reopened.get("order", 2), reopened.get("order", 3)))
    reopened_store = EventStore(os.path.join(tmpdir, "events.jsonl"), reopened)
    print("  重建后升级读 v:", [event["v"] for event in reopened_store.read()])

    print("=== 计数 ===")
    stats = store.stats()
    print(
        "  events=%s appends=%s reads=%s upgraded=%s downgraded=%s plans_built=%s"
        % (
            stats["events"], stats["appends"], stats["reads"],
            stats["upgraded"], stats["downgraded"], stats["plans_built"],
        )
    )


def section_two():
    # 留位：第二段预留给未来的“写时迁移 / 在线回填”能力——即 append 时
    # 直接写最新形状、后台把历史文件重写成新版本。当前只在读路径升级，
    # 数据文件保持只追加，所以这里暂不实现，仅保留演示位子。
    print("=== 第二段（留位）===")
    print("  写时迁移 / 在线回填尚未启用：升级只发生在读路径。")


def main():
    tmpdir = tempfile.mkdtemp(prefix="evschema-demo-")
    section_one(tmpdir)
    section_two()


if __name__ == "__main__":
    main()
