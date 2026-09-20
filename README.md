# lease

订单库的主备选主组件，纯标准库，靠一个锁文件决定谁是主。

- `lease/election.py`：`FileLockElection.try_acquire()` 抢锁成为主，`release()` 让位，`current_holder()` 读当前持有者；`clock` 可注入
- `lease/lease.py`：`LeaseElection` 带租约的选主（定期续租、认输让位），`FencedStore` 按 fencing token 挡过期主的写入
- `tests/test_election.py`：行为基线
- `tests/test_lease.py`：租约选举行为测试
- `demo.py`：主备抢占演示 + 租约选举演示

## 实现说明

- 续约失败判定：单次续租失败（IO 抖动）不判负，只要距上次成功续租未超过 lease_duration（按本地单调时钟算）就还是主；超时、或续租时发现记录已属他人，立即认输让位。
- 防双主：候选者不比墙钟时间戳，而是观察到租约记录（holder/token/seq）静止满一个 lease_duration 才接手；宁可短暂无主，也不冒双主。主动 release 会写让位标记，备机可立即接手。
- fencing token：每次换主 token 加一并随记录持久化；业务写前用 `assert_primary()` 取当前 token，存储层 `FencedStore` 拒绝 token 不大于已见最大值的写入，GC 停顿醒来的旧主写不进来。
- 时钟异常：租约有效性只看单调时钟，墙钟漂移/回拨不影响安全；记录里的 expires_at 仅供运维展示，不参与判断。
- 写入路径：续租在后台线程做，`assert_primary()` 是纯本地判断、无 IO，不会卡在业务写入中间。
- 状态交接：主用 `update_state()` 把交接状态写进租约记录，新主接手后经 `handover_state()` 读出继续。
