"""avalcache 修复后行为演示：四段，对应线上踩过的几个坑。

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
    print(f"  当前时刻 {clock.now}，到期时刻均匀打散在 TTL 窗口后半段，"
          "不会再同一秒集体过期")

    section("过期清理：sweep 主动回收过期条目")
    clock2 = FakeClock()
    c2 = TtlCache(clock=clock2)
    c2.put_many([(f"k{i}", i) for i in range(4)], ttl=30)
    clock2.advance(60)
    print(f"  过期之后 stats.entries = {c2.stats()['entries']}，还占着位子")
    print(f"  sweep() 返回 {c2.sweep()}，清完后 entries = "
          f"{c2.stats()['entries']}，expired = {c2.stats()['expired']}")
    calls = []
    for i in range(4):
        c2.get_or_load(f"k{i}", lambda k: calls.append(k) or {"k": k}, ttl=30)
    print(f"  过期后每个 key 各回源一次，loader 被调用 {len(calls)} 次，"
          f"loads={c2.stats()['loads']}")

    section("回源失败：异常抛给调用方，失败结果不进缓存")
    clock3 = FakeClock()
    c3 = TtlCache(clock=clock3)
    boom = []

    def flaky(key):
        boom.append(key)
        if len(boom) == 1:
            raise RuntimeError("下游返回 503")
        return {"key": key}

    try:
        c3.get_or_load("user-1", flaky, ttl=60)
    except RuntimeError as exc:
        print(f"  第一次回源异常，原样抛出：{exc}")
    print(f"  失败后 entries = {c3.stats()['entries']}，没有写入任何兜底值")
    second = c3.get_or_load("user-1", flaky, ttl=60)
    print(f"  下游恢复后第二次拿到 {second!r}，loader 共被调用 {len(boom)} 次")
    s = c3.stats()
    print(f"  stats: hits={s['hits']} loads={s['loads']} entries={s['entries']}")

    section("覆盖写入：值换了，到期时刻按新 TTL 重算")
    clock4 = FakeClock()
    c4 = TtlCache(clock=clock4)
    c4.put("cfg", {"v": 1}, ttl=60)
    print(f"  第一次写入 expires_at = {c4.expires_at('cfg')}")
    clock4.advance(50)
    c4.put("cfg", {"v": 2}, ttl=60)
    remaining = c4.expires_at("cfg") - clock4.now
    print(f"  推进 50 秒后按新的 TTL 覆盖，expires_at = {c4.expires_at('cfg')}")
    print(f"  距离过期还有完整的 {remaining} 秒")


if __name__ == "__main__":
    main()
