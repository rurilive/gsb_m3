"""signalbox 现状演示。

第一段：一个朴素可观察值，看设值如何把新值通知给订阅者，以及退订后的效果。
第二段：预留的信号、派生与批处理演示位子（见文末注释）。
"""

from signalbox import Observable


def main():
    print("=== 朴素可观察值（现有能力） ===")
    obs = Observable(1)
    seen = []
    obs.subscribe(lambda o, v: seen.append(("a", v)))
    unsub = obs.subscribe(lambda o, v: seen.append(("b", v)))

    print("  初始值:", obs.get())
    obs.set(2)
    print("  设值 2 后订阅者收到:", seen)
    print("  版本:", obs.version)

    unsub()
    obs.set(3)
    print("  退订 b 后设值 3 订阅者收到:", seen)
    print("  当前值:", obs.get())
    print("  订阅者数量:", len(obs.subscribers()))

    # TODO(反应式改造): 依赖图、惰性求值与批处理就位后，在这里加一段演示：
    # 建一个 signal 与由它派生的 computed，连续读取证明首次求值后命中缓存、
    # 未受影响的派生不重算；在一个批次里改多次 signal，证明批次提交时
    # 订阅者只被通知一次、批内读取看到的是一致视图。


if __name__ == "__main__":
    main()