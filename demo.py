"""qsketch 现状演示。

第一段：SampleSet 全量收样本，查分位、均值、cdf。
第二段：ShardSet 按分片记账，查询时把各片拼起来。
第三段：codec 落盘、读回，再合并两份账本。
末尾给摘要留下位子。
"""

import os
import tempfile

from qsketch import SampleSet, ShardSet, codec


def demo_samples():
    print("=== SampleSet：全量样本 ===")
    samples = SampleSet()
    for value in (3, 1, 9, 5, 7, 2, 8):
        samples.add(value)
    print("  values:", samples.values())
    for q in (0.5, 0.99):
        print("  p%g = %s" % (q * 100, samples.quantile(q)))
    print("  stats:", samples.stats())
    print("  cdf(5) =", samples.cdf(5))


def demo_shards():
    print("=== ShardSet：分片记账 ===")
    shards = ShardSet()
    for name, values in (("edge-a", [120, 240]), ("edge-b", [90, 300])):
        for value in values:
            shards.add(name, value)
    print("  names:", shards.names(), "total:", shards.count())
    print("  p50 =", shards.quantile(0.5), " p90 =", shards.quantile(0.9))


def demo_codec():
    print("=== codec：落盘与读回 ===")
    left = ShardSet()
    left.add("edge-a", 10)
    left.add("edge-b", 30)
    right = ShardSet()
    right.add("edge-a", 20)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "shards.json")
        codec.save(left, path)
        restored = codec.read(path)
        print("  读回:", restored.names(), restored.values())

    merged = restored.merge(right)
    print("  合并后:", merged.names(), merged.values())
    print("  合并后 p50 =", merged.quantile(0.5))


def demo_digest():
    # TODO(摘要): 摘要落地后在这里补一段：同一批样本喂给摘要，
    # 看 quantile 跟全量对拍、占多少质心、落盘读回后还能接着合。
    pass


def main():
    demo_samples()
    demo_shards()
    demo_codec()
    demo_digest()


if __name__ == "__main__":
    main()
