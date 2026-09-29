# lockfolio

进程内分布式锁工具，纯标准库，无外部依赖。

## 现状

lockfolio/lock.py 提供朴素全局互斥锁 MutexLock：

- MutexLock(clock=None)：clock 是可注入的时钟，缺省用 time.monotonic
- acquire(key, owner)：取锁成功返回 True，已被别人持有或同一 owner 重复获取返回 False
- release(key, owner)：只有当前持有者能释放，成功返回 True
- holder(key) / is_locked(key) / keys()：只读探查，keys() 返回当前被持有的 key 快照
- 按 key 互斥，不同 key 互不干扰；多线程下同一 key 至多一个持有者

## 问题

锁一旦被持有就没有退路：拿锁的人崩了或者忘了释放，这个 key 永远锁死，别人只能干等。
获取失败是立刻返回的，没有等待、没有排队，先来的和后到的地位一样，容易饿死。
也没有任何凭据去判断某个持有者是不是已经过期，旧持有者回来照样能对数据动手。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_lock.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```