"""idemkey 演示：四类对账怪象修好后的行为，外加两个新能力。

演示六段：
  1. 只差大小写的两个单号现在是两笔独立单子
  2. 服务重启后结果跟着磁盘回来，重发照样回放老回执
  3. 处理中途失败调 fail() 释放占位，同一键可以重发成功
  4. ttl 从完成时刻起算，耗时 90 秒的单子收工后照样取得到
  5. 长流程中途 renew() 续期，不必重跑；完成后续期则顺延回放窗口
  6. 结果超过 max_result_size 只落截断标记，取回时一眼认出被截过
"""

import os
import tempfile

from idemkey import IdempotencyStore, TruncatedResult


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def demo_case_is_distinct():
    print("=== 1. 大小写不同的两个单号各是各的单子 ===")
    store = IdempotencyStore()
    print("  begin('Order-7001') ->", store.begin("Order-7001"))
    store.finish("Order-7001", {"order": "Order-7001", "amount": 100})
    print("  begin('order-7001') ->", store.begin("order-7001"),
          "（新单正常开工，不再串单）")
    store.finish("order-7001", {"order": "order-7001", "amount": 200})
    print("  get('Order-7001')  ->", store.get("Order-7001"))
    print("  get('order-7001')  ->", store.get("order-7001"),
          "（各取各的回执，不再多扣）")


def demo_restart_keeps_results():
    print("\n=== 2. 服务重启后结果跟着磁盘回来 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        before = IdempotencyStore(path=path)
        before.begin("pay-88")
        before.finish("pay-88", {"amount": 250, "state": "paid"})
        print("  重启前 get('pay-88')  ->", before.get("pay-88"))
        after = IdempotencyStore(path=path)
        print("  重启后 get('pay-88')  ->", after.get("pay-88"),
              "（结果完整回来）")
        print("  重启后 begin('pay-88')->", after.begin("pay-88"),
              "（判重复，调用方回放老回执即可）")


def demo_fail_allows_retry():
    print("\n=== 3. 中途失败调 fail()，同一键可以重发 ===")
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
        try:
            result = do_work(order)
        except Exception:
            store.fail(order)            # 释放占位，让重发能开工
            raise
        store.finish(order, result)
        return result

    try:
        submit("pay-99")
    except RuntimeError as exc:
        print("  第一次提交失败:", exc)
    print("  同一笔重发：begin 能重新开工，拿回 ->", submit("pay-99"),
          "（这次正常收款，不再永远回空）")
    print("  再次重发 begin('pay-99') ->", store.begin("pay-99"),
          "（结果已落键，后续重发照旧判重复）")


def demo_ttl_from_finish():
    print("\n=== 4. ttl 从完成时刻起算，长单收工后不立刻过期 ===")
    clock = FakeClock()
    store = IdempotencyStore(ttl=60, clock=clock)
    store.begin("pay-77")
    clock.advance(90)                 # 这单前后跑了 90 秒
    store.finish("pay-77", {"amount": 300})
    print("  ttl=60，这单从开工到收工花了 90 秒")
    print("  finish 之后马上 get('pay-77') ->", store.get("pay-77"),
          "（从收工时刻重新计 60 秒，记录还在）")
    clock.advance(61)
    print("  收工后再过 61 秒 get('pay-77') ->", store.get("pay-77"),
          "（这时才真正过期）")


def demo_renew_mid_flight():
    print("\n=== 5. 长流程中途 renew() 续期，不必推倒重跑 ===")
    clock = FakeClock()
    store = IdempotencyStore(ttl=60, clock=clock)
    store.begin("pay-66")
    clock.advance(55)
    print("  开工 55 秒，快到 ttl 了，renew 一下 ->", store.renew("pay-66"))
    clock.advance(55)                 # 续期后又跑了 55 秒
    store.finish("pay-66", {"amount": 88})
    print("  累计跑了 110 秒才收工，get('pay-66') ->", store.get("pay-66"),
          "（占位没过期，单子只跑了一遍）")
    clock.advance(55)
    print("  收工 55 秒后再 renew ->", store.renew("pay-66"),
          "（已完成的记录也能顺延回放窗口）")
    clock.advance(20)
    print("  再走 20 秒 get('pay-66') ->", store.get("pay-66"),
          "（按第二次续期时刻重算 ttl，仍然在）")


def demo_truncated_result():
    print("\n=== 6. 结果超上限落截断标记，取回时认得出 ===")
    store = IdempotencyStore(max_result_size=64)
    big = {"receipt": "X" * 200}
    store.finish("pay-55", big)
    got = store.get("pay-55")
    print("  200+ 字节的回执写进上限 64 字节的存储，取回 ->", got)
    print("  isinstance(got, TruncatedResult) ->",
          isinstance(got, TruncatedResult), "（标记可识别，缓存没被撑爆）")
    print("  begin('pay-55') ->", store.begin("pay-55"),
          "（截断不影响幂等判定，重发仍然回放同一份标记）")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        persisted = IdempotencyStore(path=path, max_result_size=64)
        persisted.finish("pay-56", big)
        reloaded = IdempotencyStore(path=path, max_result_size=64)
        reloaded_got = reloaded.get("pay-56")
        print("  落盘再重启后取回 ->", reloaded_got,
              "（截断标记同样能跨重启保留）")


def main():
    demo_case_is_distinct()
    demo_restart_keeps_results()
    demo_fail_allows_retry()
    demo_ttl_from_finish()
    demo_renew_mid_flight()
    demo_truncated_result()
    print("\n演示结束：四类怪象均已修复，续期与截断标记可用。")


if __name__ == "__main__":
    main()
