# bucketmap

分桶链表的哈希表：每个桶是一条 (key, value) 链，装载因子超过阈值就把桶数翻倍重哈希。
纯标准库，threading 可用，值不许是 None（None 表示缺失）。

## 模块

- `bucketmap/table.py`：`HashMap`，单线程实现。`capacity` 初始桶数，`load_factor` 阈值
  （默认 0.75），`auto_grow=False` 时只负责读写，扩容交给外层调度。入口：`put` / `get` /
  `delete` / `items` / `keys` / `size` / `capacity` / `bucket_index` / `buckets`。
- `bucketmap/rwlock.py`：`RWLock`，写优先的读写锁。`read()` / `write()` 是上下文管理器，
  也有 `acquire_read` / `release_read` / `acquire_write` / `release_write`。
- `bucketmap/concurrent.py`：`ConcurrentMap`，在 `HashMap` 外面套读写锁。写把装载因子顶过
  阈值时开一轮扩容，新表桶数翻倍，旧表的桶逐个搬过去，搬完对调；迁移在写操作里推进，每搬
  完一批放开一次写锁。构造参数 `batch` 是每次写操作最多推进的桶数，`step_hook(已迁桶数,
  总桶数)` 每搬完一批桶回调一次（压测用它打点或注入慢动作，回调别做重活），`clock` 用来记
  单次调用的耗时。入口：`put` / `get` / `delete` / `len` / `items` / `stats`。
- `bucketmap/reference.py`：`PlainMap`，dict 版本的参考实现，随机对拍拿它当 oracle。

## stats 口径

`puts` / `gets` / `deletes` 是三个入口的调用次数；`resizes` 是成功推完的扩容轮数；
`migrated_buckets` 是累计搬完的桶数；`pending_buckets` 是当前这轮还没搬的桶数，没有扩容
在进行时为 0；`max_pause_ms` 是单次 put / get / delete 从进入到返回的最大耗时（毫秒）；
`tables_live` 是还占着内存的表数量，含迁移目标和历轮退役的表；`entries` 是所有活表里的
条目总数；`size` 是键个数，等于 `len(map)`。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
