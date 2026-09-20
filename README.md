# lease

订单库的主备选主组件，纯标准库，靠一个锁文件决定谁是主。

- `lease/election.py`：`FileLockElection.try_acquire()` 抢锁成为主，`release()` 让位，`current_holder()` 读当前持有者；`clock` 可注入
- `tests/test_election.py`：行为基线
- `demo.py`：主备抢占演示
