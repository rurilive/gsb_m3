"""radixest 现状演示。

第一段：精确去重计数——重复的 key 不重复计数。
第二段：预留的估算演示位子（见文末注释）。
"""

from radixest import DistinctCounter


def main():
    print("=== 精确去重计数 ===")
    c = DistinctCounter()
    events = ["u1", "u2", "u1", "u3", "u2", "u4", "u1"]
    for key in events:
        print(f"  add({key!r}) -> {c.add(key)}")
    print(f"  一共 {len(events)} 条事件，不同 key {c.count()} 个")

    # TODO(估算改造): CardinalityEstimator 落地后，在这里补三段演示：
    # 1) 注入不同规模的随机 key，打印估算值、真实值与 error_bound() 的对比
    # 2) 持续注入直到稀疏表示自动转稠密，再用显式转换转回去，展示 count() 不跳
    # 3) 两个分片估算器 merge 成一个，看合并结果的估算值覆盖并集


if __name__ == "__main__":
    main()
