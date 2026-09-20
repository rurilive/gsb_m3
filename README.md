# avalcache

商品快照的进程内 TTL 缓存，纯标准库，无外部依赖。

## 现状

`avalcache/cache.py` 提供 `TtlCache`：

- `TtlCache(clock=time.monotonic, jitter=0.1, rng=None)`：clock 为注入时钟，
  测试可换成假时钟；jitter 为批量写入的 TTL 抖动比例，rng 可注入随机源
- `put(key, value, ttl=None)`：写入单个条目，ttl 为秒数，`None` 表示永不过期；
  覆盖已有 key 时一律按本次 ttl 重新计算到期时刻
- `put_many(items, ttl=None)`：批量写入，items 是 `(key, value)` 的可迭代对象；
  每个条目在 `[ttl*(1-jitter), ttl*(1+jitter)]` 区间内独立抖动到期时刻，
  jitter=0 时退化为统一到期
- `get(key)`：未命中或已过期返回 `None`
- `get_or_load(key, loader, ttl=None)`：读缓存，未命中就回源并回填；
  loader 抛异常时异常原样向上抛，不写缓存，下次请求会重新回源
- `sweep()`：主动清理全部过期条目，返回清掉的数量（计入 `expired`）
- `expires_at(key)`：条目的绝对到期时刻，永不过期或 key 不存在时返回 `None`
- `delete(key)`：删除条目，返回是否真的删掉
- `stats()`：返回 `hits` / `misses` / `expired` / `loads` / `entries` 的计数快照
- 内部一把锁保护，多线程单操作安全

## 修复说明

- 批量写入到期时刻随机打散，避免同批 key 同一秒集体过期打穿下游
- `sweep()` 真正生效，过期条目可主动回收，不必等读请求顺手删
- 回源异常不再被吞成空结果缓存，异常透传，下游恢复后下一次请求即可拿到新数据
- 覆盖写入按新 TTL 重算到期时刻，不再沿用第一次写入的旧值

约束：已有方法的行为与 `tests/test_cache.py` 基线保持不变，纯标准库。

## 运行

```bash
python3 demo.py                          # 复现当前几个缺陷
python3 -m unittest discover -s tests -v # 行为基线测试
```
