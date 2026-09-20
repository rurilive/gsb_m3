# avalcache

商品快照的进程内 TTL 缓存，纯标准库，无外部依赖。

## 现状

`avalcache/cache.py` 提供 `TtlCache`：

- `TtlCache(clock=time.monotonic)`：clock 为注入时钟，测试可换成假时钟
- `put(key, value, ttl=None)`：写入单个条目，ttl 为秒数，`None` 表示永不过期
- `put_many(items, ttl=None)`：批量写入，items 是 `(key, value)` 的可迭代对象
- `get(key)`：未命中或已过期返回 `None`
- `get_or_load(key, loader, ttl=None)`：读缓存，未命中就回源并回填
- `sweep()`：主动清理过期条目，返回清掉的数量
- `expires_at(key)`：条目的绝对到期时刻，永不过期或 key 不存在时返回 `None`
- `delete(key)`：删除条目，返回是否真的删掉
- `stats()`：返回 `hits` / `misses` / `expired` / `loads` / `entries` 的计数快照
- 内部一把锁保护，多线程单操作安全

## 问题

线上出现过一批 key 同时过期打穿下游、过期条目迟迟不回收、回源失败被当成
空结果缓存、以及覆盖写入沿用旧到期时刻等状况。

## 目标

见任务描述。约束：

- 已有方法的行为与 `tests/test_cache.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 复现当前几个缺陷
python3 -m unittest discover -s tests -v # 行为基线测试
```
