"""idemkey 修复后演示：幂等键兜住重复扣款的几类场景。

逐段演示四个现象：
  1. 只差大小写的两个单号各算各的，互不串单
  2. 服务重启后键和结果都在，重发正确回放
  3. 处理中途失败，键可以重新开工
  4. 耗时请求的有效期从收工时刻起算，结果不会提前消失
"""

import os
import tempfile

from idemkey import IdempotencyStore


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def demo_case_collision():
    print("=== 1. 只差大小写的两个单号各算各的 ===")
    store = IdempotencyStore()
    print("  begin('Order-7001') ->", store.begin("Order-7001"))
    store.finish("Order-7001", {"order": "Order-7001", "amount": 100})
    print("  Order-7001 收工，收款 100")
    print("  begin('order-7001') ->", store.begin("order-7001"),
          "（新单正常开工）")
    store.finish("order-7001", {"order": "order-7001", "amount": 40})
    print("  get('Order-7001') ->", store.get("Order-7001"))
    print("  get('order-7001') ->", store.get("order-7001"),
          "（两笔各回各的回执）")


def demo_restart_loses_results():
    print("\n=== 2. 服务重启后键还在、结果没了 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        before = IdempotencyStore(path=path)
        before.begin("pay-88")
        before.finish("pay-88", {"amount": 250, "state": "paid"})
        print("  重启前 get('pay-88')  ->", before.get("pay-88"))
        after = IdempotencyStore(path=path)
        print("  重启后 get('pay-88')  ->", after.get("pay-88"), "（结果还在）")
        print("  重启后 begin('pay-88')->", after.begin("pay-88"),
              "（重发被判成重复，直接回放上面的结果）")


def demo_halfway_failure():
    print("\n=== 3. 处理中途失败，键可以重新开工 ===")
    store = IdempotencyStore()
    attempts = {"n": 0}

    def do_work(order):
        attempts["n"] += 1
        if attempts["n"] == 1:            # 第一次下游抖了一下
            raise RuntimeError("下游超时，这一单没做完")
        return {"order": order, "state": "paid"}

    def submit(order):
        if not store.begin(order):
            return store.get(order)
        result = do_work(order)
        store.finish(order, result)
        return result

    try:
        submit("pay-99")
    except RuntimeError as exc:
        print("  第一次提交失败:", exc)
    print("  同一笔重发拿回:", submit("pay-99"),
          "（重新开工，这一单正常扣款）")


def demo_expiry_from_begin():
    print("\n=== 4. 耗时请求的有效期从收工时刻起算 ===")
    clock = FakeClock()
    store = IdempotencyStore(ttl=60, clock=clock)
    store.begin("pay-77")
    clock.advance(90)                 # 这单前后跑了 90 秒
    store.finish("pay-77", {"amount": 300})
    print("  ttl=60，这单从开工到收工花了 90 秒")
    print("  finish 之后马上 get('pay-77') ->", store.get("pay-77"),
          "（从收工起算，结果还在）")
    clock.advance(61)                 # 收工后又过了 61 秒
    print("  收工 61 秒后 get('pay-77')   ->", store.get("pay-77"),
          "（过了有效期才被清掉）")


def main():
    demo_case_collision()
    demo_restart_loses_results()
    demo_halfway_failure()
    demo_expiry_from_begin()
    print("\n演示结束")


if __name__ == "__main__":
    main()
