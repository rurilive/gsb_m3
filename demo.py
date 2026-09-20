"""timeoutkit 演示：给调用设预算、观察超时与取消传播。"""
import time

from timeoutkit import CallContext, Timeout, call


def slow(tag, seconds):
    time.sleep(seconds)
    return tag


def main():
    print("=== 1. 预算充足的普通调用 ===")
    ctx = CallContext(timeout=1.0)
    print("  返回:", call(lambda: slow("查询订单", 0.02), ctx=ctx))

    print("=== 2. 下游比自己慢，触发超时 ===")
    tight = CallContext(timeout=0.1)
    try:
        call(lambda: slow("下游写入", 0.5), ctx=tight)
    except Timeout as exc:
        print("  如期超时:", exc)

    print("=== 3. 父级取消，子上下文一并作废 ===")
    root = CallContext(timeout=2.0)
    step_one = root.child(timeout=1.0)
    step_two = step_one.child(timeout=1.0)
    root.cancel()
    print("  子级已取消: %s, 孙级已取消: %s" % (step_one.cancelled, step_two.cancelled))

    print("演示结束")


if __name__ == "__main__":
    main()
