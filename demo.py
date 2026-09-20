"""idemkey 演示：幂等键兜住重复扣款的几类场景。

逐段演示四类历史问题现在的行为：
  1. 只差大小写的两个单号是两笔不同的单，各走各的处理
  2. 服务重启后键和结果都在，重发直接回放上次的回执
  3. 处理中途失败，键可以重新开工，不会卡死
  4. 耗时请求的结果从收工时刻起算有效期，不会刚写完就被清掉
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
    print("=== 1. 只差大小写的两个单号是两笔不同的单 ===")
    store = IdempotencyStore()
    assert store.begin("Order-7001") is True
    store.finish("Order-7001", {"order": "Order-7001", "amount": 100})
    print("  Order-7001 收工，收款 100")
    assert store.begin("order-7001") is True
    print("  begin('order-7001') -> True（新单正常开工）")
    assert store.get("order-7001") is None
    print("  get('order-7001')   -> None（不会拿回别人单子的回执）")
    store.finish("order-7001", {"order": "order-7001", "amount": 200})
    assert store.get("Order-7001") == {"order": "Order-7001", "amount": 100}
    assert store.get("order-7001") == {"order": "order-7001", "amount": 200}
    print("  两笔单各自记账，互不串扰")


def demo_restart_keeps_results():
    print("\n=== 2. 服务重启后键和结果都在 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        before = IdempotencyStore(path=path)
        before.begin("pay-88")
        before.finish("pay-88", {"amount": 250, "state": "paid"})
        print("  重启前 get('pay-88')  ->", before.get("pay-88"))
        after = IdempotencyStore(path=path)
        assert after.get("pay-88") == {"amount": 250, "state": "paid"}
        print("  重启后 get('pay-88')  ->", after.get("pay-88"), "（结果还在）")
        assert after.begin("pay-88") is False
        print("  重启后 begin('pay-88')-> False（重发直接回放，不会重复扣款）")


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
    retried = submit("pay-99")
    assert retried == {"order": "pay-99", "state": "paid"}
    print("  同一笔重发:", retried, "（重新开工，正常扣款）")
    assert submit("pay-99") == retried
    print("  再重发:", submit("pay-99"), "（已处理，回放同一份回执）")


def demo_expiry_from_finish():
    print("\n=== 4. 有效期从收工时刻起算 ===")
    clock = FakeClock()
    store = IdempotencyStore(ttl=60, clock=clock)
    store.begin("pay-77")
    clock.advance(90)                 # 这单前后跑了 90 秒
    store.finish("pay-77", {"amount": 300})
    print("  ttl=60，这单从开工到收工花了 90 秒")
    assert store.get("pay-77") == {"amount": 300}
    print("  finish 之后马上 get('pay-77') ->", store.get("pay-77"),
          "（按收工时刻起算，记录还在）")
    clock.advance(59)
    assert store.get("pay-77") == {"amount": 300}
    print("  收工后 59 秒 get('pay-77')    ->", store.get("pay-77"))
    clock.advance(2)                  # 收工后 61 秒，过了有效期
    assert store.get("pay-77") is None
    print("  收工后 61 秒 get('pay-77')    -> None（过了有效期才清掉）")


def main():
    demo_case_collision()
    demo_restart_keeps_results()
    demo_halfway_failure()
    demo_expiry_from_finish()
    print("\n演示结束：四类场景行为均符合预期")


if __name__ == "__main__":
    main()
