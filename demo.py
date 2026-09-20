"""avalcache 现状演示：四段，分别复现线上踩到的几个坑。

时间用手写假时钟推进，所有时刻都是确定的，方便对照。
"""

from avalcache.cache import TtlCache


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def section(title):
    print()
    print(f"=== {title} ===")


def main():
    section("批量写入：同批 key 的到期时刻")
    clock = FakeClock()
    c = TtlCache(clock=clock)
    c.put_many([(f"sku-{i}", {"price": i}) for i in range(5)], ttl=60)
    for i in range(5):
        print(f"  sku-{i}  expires_at = {c.expires_at(f'sku-{i}')}")
    print(f"  当前时刻 {clock.now}，五个 key 的到期时刻完全一样")

    section("过期清理：没人主动清，全靠读的时候顺手删")
    clock2 = FakeClock()
    c2 = TtlCache(clock=clock2)
    c2.put_many([(f"k{i}", i) for i in range(4)], ttl=30)
    clock2.advance(60)
    print(f"  过期之后 stats.entries = {c2.stats()['entries']}，还占着位子")
    print(f"  sweep() 返回 {c2.sweep()}，主动清理入口目前什么都不做")
    calls = []
    for i in range(4):
        c2.get_or_load(f"k{i}", lambda k: calls.append(k) or {"k": k}, ttl=30)
    print(f"  四个请求挨个回源，loader 被调用 {len(calls)} 次，"
          f"loads={c2.stats()['loads']}")

    section("回源失败：异常被吞掉，空结果进了缓存")
    clock3 = FakeClock()
    c3 = TtlCache(clock=clock3)
    boom = []

    def flaky(key):
        boom.append(key)
        raise RuntimeError("下游返回 503")

    first = c3.get_or_load("user-1", flaky, ttl=60)
    second = c3.get_or_load("user-1", flaky, ttl=60)
    print(f"  第一次回源异常，返回 {first!r}")
    print(f"  第二次直接返回 {second!r}，loader 总共只被调用 {len(boom)} 次")
    s = c3.stats()
    print(f"  stats: hits={s['hits']} loads={s['loads']} entries={s['entries']}")
    print("  下游其实已经恢复，但接下来一整个 TTL 拿到的都还是空快照")

    section("覆盖写入：值换了，到期时刻没重算")
    clock4 = FakeClock()
    c4 = TtlCache(clock=clock4)
    c4.put("cfg", {"v": 1}, ttl=60)
    print(f"  第一次写入 expires_at = {c4.expires_at('cfg')}")
    clock4.advance(50)
    c4.put("cfg", {"v": 2}, ttl=60)
    remaining = c4.expires_at("cfg") - clock4.now
    print(f"  推进 50 秒后按新的 TTL 覆盖，expires_at = {c4.expires_at('cfg')}")
    print(f"  距离过期只剩 {remaining} 秒，而不是完整的 60 秒")


if __name__ == "__main__":
    main()
