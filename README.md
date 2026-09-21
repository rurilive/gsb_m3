# revcache

订单服务里的进程内读缓存，架在一个可注入延迟和故障的数据源前面。纯标准库，
没有三方依赖，线程安全。

## 模块

- `revcache/backend.py`：数据源本体，也是权威副本。`Backend` 持有每个 key 的
  值与修订号（revision）。修订号只增不减，删除也不会让它回退，所以
  `snapshot(key)` 返回的 `(value, revision)` 总是成对的，调用方拿到值就知道
  自己手里是哪一版。接口：`get`、`snapshot`、`set`（返回新修订号）、`delete`
  （返回 key 是否存在）、`revision`、`stats`。测试辅助：`inject_latency(秒)`
  给读操作加延迟，`inject_fault(key, count)` 让接下来若干次读取抛
  `TransientError`。
- `revcache/cache.py`：`ValueCache`，进程内 LRU 缓存，`capacity=None` 表示不限
  容量。接口：`get`（未命中抛 `KeyError`）、`put`、`invalidate`、`keys`、
  `items`、`len`、`stats`。测试辅助：`inject_write_faults(count)` 让接下来
  若干次 `put` 抛 `CacheError`。
- `revcache/service.py`：`CachedStore`，调用方唯一直接接触的入口。`read(key)`
  命中直接返回，未命中回源并把结果放进缓存；key 不存在时抛 `KeyError`，回源
  失败时抛 `TransientError`。`write(key, value)` 先更新数据源再让缓存里该
  key 的副本失效。`delete(key)` 两边一起删，返回 key 原先是否存在。
  `stats()` 给出 reads、hits、misses、loads、load_errors、writes、deletes。

## 计数器口径

`CachedStore.stats()` 里 hits 是被缓存直接满足的读取次数，misses 是回源处理
过的读取次数，loads 是真正成功从数据源取到值的次数。`ValueCache.stats()` 里
hits 和 misses 只统计缓存自身被查询的结果，evictions 是容量淘汰次数，
write_errors 是缓存写入失败的次数。`Backend.stats()` 里 reads 是数据源被读取
的次数，是观察回源压力的直接指标。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
