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

## 运行

```bash
python3 demo.py                          # 单锁计数、并发对拍、快照清零演示
python3 -m unittest discover -s tests -v # 行为基线测试
python3 bench.py                         # 热键递增吞吐对比表
```
