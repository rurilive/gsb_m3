"""avalcache 修复后演示：四段，分别对应线上踩过的四个坑。

时间用手写假时钟推进，所有时刻都是确定的，方便对照。
"""

import random

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
    c = TtlCache(clock=clock, rng=random.Random(42))
    c.put_many([(f"sku-{i}", {"price": i}) for i in range(5)], ttl=60)
    for i in range(5):
        print(f"  sku-{i}  expires_at = {c.expires_at(f'sku-{i}')}")
    spreads = [c.expires_at(f"sku-{i}") - clock.now for i in range(5)]
    print(f"  TTL=60，实际存活 {['%.1f' % s for s in spreads]} 秒，到期时刻已散开")

    section("过期清理：sweep 主动推进，不再等读触发")
    clock2 = FakeClock()
    c2 = TtlCache(clock=clock2, jitter=0)
    c2.put_many([(f"k{i}", i) for i in range(4)], ttl=30)
    clock2.advance(60)
    print(f"  过期之后 sweep() 主动清掉 {c2.sweep()} 条，"
          f"stats.entries = {c2.stats()['entries']}")
    calls = []
    for i in range(4):
        c2.get_or_load(f"k{i}", lambda k: calls.append(k) or {"k": k}, ttl=30)
    print(f"  四个请求挨个回源，loader 被调用 {len(calls)} 次，"
          f"loads={c2.stats()['loads']}")

    section("回源失败：异常原样抛出，不写缓存")
    clock3 = FakeClock()
    c3 = TtlCache(clock=clock3)
    boom = []

    def flaky(key):
        boom.append(key)
        raise RuntimeError("下游返回 503")

    try:
        c3.get_or_load("user-1", flaky, ttl=60)
    except RuntimeError as exc:
        print(f"  第一次回源异常，原样向上抛: {exc}")
    try:
        c3.get_or_load("user-1", flaky, ttl=60)
    except RuntimeError:
        pass
    print(f"  第二次依旧重新回源，loader 被调用 {len(boom)} 次，没有错误结果被缓存")
    s = c3.stats()
    print(f"  stats: hits={s['hits']} loads={s['loads']} entries={s['entries']}")

    def recovered(key):
        return {"snapshot": "fresh"}

    print(f"  下游恢复后立刻拿到新结果: {c3.get_or_load('user-1', recovered, ttl=60)}")

    section("覆盖写入：按新 TTL 重新算到期时刻")
    clock4 = FakeClock()
    c4 = TtlCache(clock=clock4)
    c4.put("cfg", {"v": 1}, ttl=60)
    print(f"  第一次写入 expires_at = {c4.expires_at('cfg')}")
    clock4.advance(50)
    c4.put("cfg", {"v": 2}, ttl=60)
    remaining = c4.expires_at("cfg") - clock4.now
    print(f"  推进 50 秒后按新的 TTL 覆盖，expires_at = {c4.expires_at('cfg')}")
    print(f"  距离过期还有 {remaining:.0f} 秒，按新 TTL 拿到完整的 60 秒")


if __name__ == "__main__":
    main()
