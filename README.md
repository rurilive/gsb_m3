# shardcount

埋点管线在用的进程内计数包，纯标准库，无外部依赖。

## 现状

`shardcount/counter.py` 提供 `LockCounter(clock=time.monotonic)`，一把全局锁护住所有键：

- `incr(key, delta=1)`：加上 delta 并返回加完之后的值，delta 允许为负
- `get(key)`：读当前值，没记过的键是 0
- `snapshot(key)`：读出当前值并把该键清零，一步做完
- `keys()` / `total()` / `stats()`：当前值非 0 的键、所有键之和、操作计数与最后变更时刻

`shardcount/registry.py` 提供 `Registry(factory=None)`：`open(name)` 按名字发计数器，
同名永远是同一份；`bind` / `get` / `names` / `drop` 管注册表。

`shardcount/reference.py` 提供对拍工具：`make_plan(seed, keys, threads, per_thread)`
生成确定性的压测计划，`expected_totals(plan)` 纯算术算出每个键的理论值，
`drive(counter, plan)` 把各段交给多线程跑完。

`shardcount/bench.py` 量吞吐：`measure(make_counter, threads, seconds)` 让若干个线程
围着热键打点，返回每秒操作数；`candidates()` 列出进比对的实现，`python3 bench.py`
打印同场对比表。

## 问题

埋点是少数几个热键、极高频率的写入。所有线程都从同一把锁下面过，热键一上来
吞吐就塌，读一次也要排在写后面。分片、有损快路、原子快照这些都没有。

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改，必须原样全绿）
- 纯标准库

## 实现说明

`shardcount/sharded.py` 的 `ShardedCounter` 把热点键摊到**按线程分配的槽位**上：
每个写线程第一次 incr 时分到一个私有槽（一个 dict），此后只写自己的槽。

- **槽位选型**：选"每线程一槽"而不是"固定槽数 + 哈希取槽"。固定槽数下多个
  线程仍会撞到同一个槽，槽锁就回去了；每线程一槽则属主独占写入，靠 GIL 保证
  单条 dict 操作原子，写路径**没有任何锁**，写线程之间永远互不相等。槽数随
  写线程数自然伸缩，冷键不占额外内存（槽是线程的，不是键的）。
- **伪共享**：CPython 里对象都是堆上指针，真正串行化的是 GIL 而不是缓存行
  竞争，所以不为槽对象做缓存行填充；把槽实现成 `__slots__` 的轻对象，每线程
  的槽引用缓存在 `threading.local` 里，热路径上一次查找都不多走。
- **读不加写锁**：`get` 直接对各槽 `dict.get` 求和（GIL 下单条操作原子），
  `keys`/`total`/`stats` 先 `dict.copy()` 再合并，都不碰任何锁。
- **原子快照**：`snapshot`/`sync` 用 Dekker 式静默协议——静默方先立
  `_quiescing` 标志再等各槽 `writing` 标志落下；写线程先立 `writing` 再看
  `_quiescing`，发现静默就退到条件变量上等。双方至少有一方看到对方的标志，
  不会错过也不会死锁；写线程只在快照/同步进行的瞬间被短暂请出场。
- **fast 模式**：正增量先攒在线程本地挂账，凑够 `batch` 个（默认 64）或遇到
  非正增量才落槽。挂账里只有正增量，所以 `get` 只读已落槽部分时**绝不超真值**；
  滞后上界 ≈ 活跃写线程数 × (batch − 1) 个增量，随 `batch` 可配。`sync()` 或
  写线程收工（`threading.local` 清理钩子触发落账）后精确，一条不丢。
- **incr 返回值**：返回本线程槽位里该键的新值。单线程下与 LockCounter 完全
  一致；多线程下同键的全局值用 `get(key)`——为返回值做全局汇总会把写路径
  打回串行，那正是单锁基线的病根。

压测数字（`python3 -m shardcount.bench`，热键递增，1 秒一轮、2 轮取最好）：

```
实现                    1 线程          2 线程          4 线程          8 线程
lock               1511137       1149592        973128        686481   相对单锁 1.00x 1.00x 1.00x 1.00x
sharded            2136934       2038274       1960439       2153667   相对单锁 1.41x 1.77x 2.01x 3.14x
sharded-fast       1917502       1732122       1663567       1609677   相对单锁 1.27x 1.51x 1.71x 2.34x
```

单锁基线随线程数上涨而塌（锁交接 + GIL 换手），分片两版基本持平；8 线程
热键下 sharded 约 3.1x、sharded-fast 约 2.3x。fast 模式在 CPython 下的
意义主要不是裸吞吐（exact 写路径本就无锁），而是把读侧一致性切成批次：
挂账期间读到的必然是一个不超过真值的滞后值。

## 运行

```bash
python3 demo.py                          # 单锁计数、并发对拍、快照清零与分片演示
python3 -m unittest discover -s tests -v # 行为基线测试
python3 -m shardcount.bench              # 热键递增吞吐对比表
```
