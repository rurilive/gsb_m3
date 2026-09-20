# avalcache

商品快照的进程内 TTL 缓存，纯标准库，无外部依赖。

## 现状

`avalcache/cache.py` 提供 `TtlCache`：

- `TtlCache(clock=time.monotonic)`：clock 为注入时钟，测试可换成假时钟
- `put(key, value, ttl=None)`：写入单个条目，ttl 为秒数，`None` 表示永不过期；覆盖写入按新的 ttl 重算到期时刻
- `put_many(items, ttl=None)`：批量写入，items 是 `(key, value)` 的可迭代对象；同批条目的到期时刻均匀打散在 TTL 窗口后半段，避免同一秒集体过期
- `get(key)`：未命中或已过期返回 `None`
- `get_or_load(key, loader, ttl=None)`：读缓存，未命中就回源并回填；loader 抛异常时原样抛给调用方，失败结果不写入缓存
- `sweep()`：主动清理过期条目，返回清掉的数量，清理数计入 `expired`
- `expires_at(key)`：条目的绝对到期时刻，永不过期或 key 不存在时返回 `None`
- `delete(key)`：删除条目，返回是否真的删掉
- `stats()`：返回 `hits` / `misses` / `expired` / `loads` / `entries` 的计数快照
- 内部一把锁保护，多线程单操作安全

## 已修复的问题

- 同批写入的 key 同一秒集体过期打穿下游 → `put_many` 把到期时刻均匀打散
- 过期条目只靠读的时候顺手删 → `sweep()` 真正执行主动清理
- 回源失败被当成空结果缓存一整个 TTL 周期 → 异常原样抛出，不写缓存
- 覆盖写入沿用旧到期时刻 → 按新的 ttl 重算

## 约束

- 已有方法的行为与 `tests/test_cache.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 演示修复后的行为
python3 -m unittest discover -s tests -v # 行为基线测试
```
