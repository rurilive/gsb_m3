# leasekit

调度器里管分片租约的进程内小包，纯标准库，无外部依赖。

## 现状

`leasekit/lease.py` 提供内存里的 `LeaseManager`：

- `LeaseManager(clock=time.monotonic, default_ttl=30.0)`：clock 为注入时钟，default_ttl 为默认租期
- `acquire(holder, ttl=None)` 发放租约并返回 `lease_id`；`ttl` 为空用默认值
- `get(lease_id)` 返回 `Lease` 只读快照；**不存在或已到期都返回 None**
- `release(lease_id, holder)` 归还租约，只有当前持有者、且租约还活着时才成功
- `stats()` 返回 `granted` / `released` / `live` 计数快照；`live` 只数还没到期的
- 内部一把锁保护，单个方法调用对多线程安全

`Lease` 是 frozen dataclass，字段为 `id` / `holder` / `ttl` / `expires_at`。

## 问题

租期是发放那一刻定死的，到期就作废，没有任何把租约往后延的途径。
长时间任务的持有者中途就丢了租约却毫不知情；过期条目又没人清理，
一直留在内存里。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_lease.py` 基线保持不变（基线一个字不改）
- 纯标准库；时间一律走注入的 clock，不许碰真实时间或起真线程
- 新行为放 `tests/test_renew.py`

## 运行

```bash
python3 demo.py                          # 发放 / 归还 / 到期演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
