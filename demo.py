"""breakerbox 现状演示。

第一段：朴素重试——失败就重试固定次数，成功即返回，耗尽抛错。
第二段：预留的三态断路器、滑动窗口与降级演示位子（见文末注释）。
"""

from breakerbox import RetryExhausted, RetryGuard


def main():
    print("=== 朴素重试（重试 2 次） ===")
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("上游抖动")
        return "成功"

    guard = RetryGuard(retries=2)
    print(f"  第三次调用成功 -> {guard.run(flaky)!r}，总调用 {len(calls)} 次")

    def always_fail():
        raise RuntimeError("一直失败")

    try:
        RetryGuard(retries=1).run(always_fail)
    except RetryExhausted as exc:
        print(f"  耗尽 -> {exc.attempts} 次尝试，末次异常 {exc.last!r}")

    # TODO(三态断路器、滑动窗口与降级): 三态状态机、按时间窗的成功失败统计、
    # 半开探测限流与降级回调都补齐后，在这里加一段演示：
    # 用一个假时钟连续喂失败，打印失败率越阈值后 closed 转 open；
    # 把假时钟往前拨过冷却，打印 open 转 half_open；
    # 半开下探测成功打印回到 closed，失败打印退回 open；
    # 再演示 open 期间调用走降级回调拿到兜底结果，并打印一份指标快照。


if __name__ == "__main__":
    main()