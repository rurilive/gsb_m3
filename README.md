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

运行方式：

```bash
python3 -m unittest tests.test_pool -v   # 或 python3 tests/test_pool.py
```

共 21 个用例：17 绿、4 红。4 个红用例钉住 3 处源码与本 README 的出入
（连续多次运行结果一致，用例不依赖时序）。

### 红用例与对应缺陷

1. `TestBorrowSemantics.test_loser_of_wakeup_race_keeps_waiting_until_next_return`（RED #1，违反语义第 1 条）
   - 缺陷：池满有多个等待者时，`return_conn` 的 `notify_all()` 同时唤醒全部等待者；
     只抢到一个连接的线程成功，抢输的线程即使远未到 deadline 也会走到
     `borrow()` 末尾「没拿到就直接 raise」的分支，立刻抛 `BorrowTimeout`，
     不会继续等待下一次归还。
   - 修复方向（一句话）：把等待改成「循环 `wait` 直到拿到连接或 deadline 到期」，
     唤醒后重新检查空闲/关闭/剩余时间，抢不到就继续等。

2. `TestReturnSemantics.test_unhealthy_return_is_closed_and_never_reused`（RED #2，违反语义第 2 条）
   - 缺陷：`return_conn()` 完全不检查 `conn.healthy`，坏连接被原样放回空闲队列
     且没有调用 `close()`，之后会被再次借给调用方。
   - 修复方向（一句话）：归还时先判 `healthy`，为 False 则 `close()` 后直接丢弃
     （从在途集合移除、不进空闲队列）。

3. `TestCloseSemantics.test_waiting_borrower_raises_immediately_when_pool_closed`
   与 `TestConcurrency.test_concurrent_borrowers_after_close_all_get_pool_closed`
   （RED #3，单线程等待版 + 真实多线程版，违反语义第 3 条）
   - 缺陷：`close()` 只置 `_closed` 标志并关闭空闲连接，没有 `notify_all()`，
     正在等待的 `borrow` 调用方要阻塞到自身 timeout 到期才能看到 `_closed`，
     而不是立即收到 `PoolClosedError`。
   - 修复方向（一句话）：`close()` 在持锁状态末尾补一次 `notify_all()`，
     并配合 RED #1 的等待循环让等待者被唤醒后立即看到关闭标志。

### 并发用例设计（全部为真实多线程，节奏用 Event/Barrier + join 定死）

- `test_parallel_borrow_return_created_bounded`：8 线程 Barrier 同时起跑，
  各 100 轮借还（线程数等于 `max_size`，不经过等待分支），校验记账与
  `created <= max_size`。
- `test_loser_of_wakeup_race_keeps_waiting_until_next_return`（红）：
  探针 Condition 在 `wait()` 入口发信号，确认 2 个等待者都已挂起后再归还，
  制造确定性的唤醒竞争；探针回调只做 `Event.set`，避免持锁自死锁。
- `test_serial_handoff_chain_wakes_each_waiter_immediately`：5 个工作线程
  严格接力，探针确认线程 i 已进入池满等待后再让当前持有者归还，钉死
  「一归还即接手」，且任一时刻最多一个等待者，与 RED #1 隔离。
- `test_concurrent_borrowers_after_close_all_get_pool_closed`（红）：
  4 线程竞争容量 2 的池（2 借到、2 等待），`close()` 后 join 全部线程，
  校验等待者立即收到 `PoolClosedError`、在途连接归还时被 close 丢弃。

所有同步点均用 `Event.wait(timeout=5)` / `join(timeout=...)` 等待并断言，
超时余量远大于实际耗时；等待线程均设为 daemon，即使缺陷导致挂起也不会
卡住测试进程。
