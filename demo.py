"""mvjoin 现状演示。

第一段：一段订单和商品的变更流按顺序落进 Dataset。
第二段：全量重算按品类统计的视图，看结果和一次重算配了多少对。
第三段：逐条变更都重算一次，量一下全量重算的步进成本。
（增量维护视图的位子在文末留好了。）
"""

import time

from mvjoin import ChangeLog, Dataset, FullView, Join, Table, ViewSpec


def sample_log():
    """两个仓库在售的商品，加几笔订单，中间有一条改连接键的更新和一条删除。"""
    log = ChangeLog()
    log.insert("skus", {"row_id": 1, "sku": "A1", "category": "fresh", "warehouse": "east"})
    log.insert("skus", {"row_id": 2, "sku": "A1", "category": "frozen", "warehouse": "west"})
    log.insert("skus", {"row_id": 3, "sku": "B2", "category": "dry", "warehouse": "east"})
    log.insert("skus", {"row_id": 4, "sku": None, "category": "dry", "warehouse": "west"})
    log.insert("orders", {"order_id": 101, "sku": "A1", "amount": 1200})
    log.insert("orders", {"order_id": 102, "sku": "B2", "amount": 800})
    log.insert("orders", {"order_id": 103, "sku": None, "amount": 5000})
    log.update("orders", {"order_id": 102, "sku": "B2", "amount": 800},
               {"order_id": 102, "sku": "A1", "amount": 800})
    log.delete("orders", {"order_id": 103, "sku": None, "amount": 5000})
    return log


SPEC = ViewSpec(
    name="category_orders",
    join=Join("orders", "skus", "sku", "sku"),
    group="skus.category",
    metrics=[("cnt", "count", None), ("amount", "sum", "orders.amount")],
)


def main():
    log = sample_log()
    dataset = Dataset(Table("orders", "order_id"), Table("skus", "row_id"))

    print("=== 变更流落库 ===")
    for change in log.changes():
        dataset.apply(change)
    print("  变更 %d 条，落到订单 %d 行、商品 %d 行" % (
        len(log), len(dataset.table("orders")), len(dataset.table("skus"))))

    view = FullView(SPEC)
    print("=== 全量重算 ===")
    result = view.recompute(dataset)
    for group in sorted(result, key=str):
        print("  %-8s cnt=%-3d amount=%d" % (group, result[group]["cnt"],
                                             result[group]["amount"]))
    print("  重算 %d 次，最近一次配了 %d 对" % (view.refreshes, view.last_pairs))

    print("=== 逐条步进（全量重算的路子）===")
    step_log = ChangeLog()
    for i in range(200):
        step_log.insert("orders", {"order_id": 1000 + i, "sku": "A1" if i % 2 else "B2",
                                   "amount": 100 + i})
    started = time.perf_counter()
    for change in step_log.changes():
        dataset.apply(change)
        view.recompute(dataset)
    spent = time.perf_counter() - started
    print("  %d 条变更各重算一次，共 %.3f 秒" % (len(step_log), spent))
    print("  重算 %d 次，订单涨到 %d 行" % (view.refreshes, len(dataset.table("orders"))))

    # TODO(增量维护): IncrementalView 落地后，在这里补第四段：
    # 同一份变更流喂给它，逐条跟 FullView.recompute 对结果；
    # 再把 step_log 那 200 条走一遍，和上面的耗时比一比。


if __name__ == "__main__":
    main()
