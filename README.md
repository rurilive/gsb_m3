# crawlkit

抓取队列的 URL 去重层，纯标准库，无外部依赖。调度器入队前问 `DedupStore` 这条
URL 是不是重复，抓过的记下来，避免同一页面反复抓。

## 现状

- `crawlkit/hashing.py`：哈希原语。`digest()` 是加固定盐的 sha256，`hash_pair()`
  劈出两个 64 位无符号数，`bit_indexes()` 做双重哈希展开，`bucket_index()` 折桶，
  `fingerprint()` 取固定位数指纹（恒不为零）。
- `crawlkit/bloom.py`：`BloomFilter(capacity, fp_rate=0.01)`。`add(key)` 置位，
  `key in bf` 查询，`len(bf)` 是加键次数，`stats()` 出计数快照，
  `to_bytes()` / `from_bytes()` 落盘读回。
- `crawlkit/cuckoo.py`：`CuckooFilter(capacity, fp_bits=12)`。指纹双桶 + 踢出，
  `add(key)`、`key in cf`、`len(cf)`、`stats()`、`to_bytes()` / `from_bytes()`
  与布隆对齐，外加 `remove(key)` 真删。桶对灌满或踢出链耗尽时翻倍扩容重排，
  重排在副本上完成后一次性换表（无递归），已加键任何时刻都命中。
- `crawlkit/store.py`：`DedupStore(capacity, fp_rate=0.01, backend="bloom",
  fp_bits=12)` 门面。`mark(key)` 记录已入队，`is_duplicate(key)` 判重，
  `retry(key)` 撤销，`stats()` 出统计，同样有 `to_bytes()` / `from_bytes()`。
  默认 `backend="bloom"` 维持老行为（只加不删、落盘格式与存量快照兼容）；
  传 `backend="cuckoo"` 底层换布谷鸟过滤器，`retry(key)` 真删并返回是否撤到，
  抓取失败的 URL 重试时不再被判重复。布谷后端用独立落盘 magic `DDS2`，
  老的 `DDS1` 快照照常读回。
- `crawlkit/errors.py`：`NotSupportedError`。

位数组只置位不清位，所以布隆过滤器只加不删；判重只会多报不会漏报。
布谷鸟过滤器按指纹归属删除，同指纹但归属不同的键互不连坐；12 位指纹、
十万容量下实测误判率约千分之 1.3。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
