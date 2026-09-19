# netpool

服务进程内的连接池，多线程环境使用，纯标准库（threading + Condition）。连接对象用
`FakeConn` 模拟（接口与真实 socket 对齐：`close()` / `healthy` 属性 / `cid`）。

## 语义约定（以下为本模块的正式行为定义）

1. **borrow(timeout=None)**
   - 有空闲连接 → 直接取出并标记为在途
   - 无空闲但池未满（在途数 < max_size）→ 用 factory 新建一个
   - 池满 → 等待归还；**等待期间只要有连接归还，应立即拿到它**；到 deadline 仍没有 → 抛 `BorrowTimeout`
   - 池已关闭 → 抛 `PoolClosedError`
2. **return_conn(conn)**
   - 归还连接进空闲队列，并唤醒等待者
   - **`conn.healthy` 为 False 的连接：归还时应立即 `close()` 并丢弃，绝不回到空闲队列**（下游健康探测已判死）
   - 归还非本池借出的连接 → `ValueError`
3. **close()**
   - 幂等；关闭所有空闲连接
   - **正在 `borrow` 中等待的调用方必须立即收到 `PoolClosedError`**，不允许等到超时
   - 在途连接随后归还时：直接 `close()` 丢弃，不进池
4. 连接创建总数不超过 `max_size`（`stats()["created"] <= max_size`）

## 运行

```bash
python3 demo.py
```

## 测试报告

测试位于 `tests/test_pool.py`（`python3 -m unittest discover -s tests -v`），
共 15 个用例：12 绿、3 红。3 个红用例各对应一处源码与本文档的出入：

1. **`test_unhealthy_conn_is_closed_and_discarded`（红）**——缺陷：`return_conn`
   不检查 `conn.healthy`，下游已判死的连接原样回到空闲队列，后续 `borrow`
   会把死连接再次发出去（违反第 2 条）。修复方向：归还时检查 `healthy`，
   为 `False` 则立即 `close()` 并丢弃，不进空闲队列。
2. **`test_close_wakes_waiting_borrower_immediately`（红）**——缺陷：`close()`
   不做 `notify`，正在 `borrow` 中等待的调用方要睡满整个 timeout 才收到
   `PoolClosedError`（违反第 3 条「立即」）。修复方向：`close()` 在持锁
   置位 `_closed` 后调用 `cond.notify_all()`。
3. **`test_concurrent_waiters_are_all_served_before_deadline`（红）**——缺陷：
   `borrow` 等待路径只 `wait` 一次，多个等待者被 `notify_all` 同时唤醒后，
   没抢到连接的等待者不等自己的 deadline 就提前抛 `BorrowTimeout`
   （违反第 1 条「到 deadline 仍没有才抛」）。修复方向：把等待改成
   `while` 循环，每次醒来重查条件，直到拿到连接或到达 deadline 才退出。

并发用例均用 `threading.Event`/`Barrier` + `join` 固定节奏，超时断言留有
余量，可独立重复运行，结果稳定。
