# leasekit

调度器里管分片租约的进程内小包，纯标准库，无外部依赖。

## 接口

`leasekit/lease.py` 提供内存里的 `LeaseManager`：

- `LeaseManager(clock=time.monotonic, default_ttl=30.0)`：clock 为注入时钟，default_ttl 为默认租期
- `acquire(holder, ttl=None)` 发放租约并返回 `lease_id`；`ttl` 为空用默认值
- `get(lease_id)` 返回 `Lease` 只读快照；**不存在或已到期都返回 None**
- `release(lease_id, holder)` 归还租约，只有当前持有者、且租约还活着时才成功
- `renew(lease_id, holder, ttl=None)` 续期：成功 True 并把到期时刻往后延；失效或非持有者返回 False 且不动租约；`ttl` 不传沿用原租期
- `reap_expired()` 由主循环驱动，清掉所有过期未续的租约，返回本次回收条数
- `stats()` 返回 `granted` / `released` / `reaped` / `live` 计数快照；`live` 只数还没到期的
- 内部一把锁保护，单个方法调用对多线程安全

`Lease` 是 frozen dataclass，字段为 `id` / `holder` / `ttl` / `expires_at`。

`LeaseWatcher(manager, lease_id, holder, interval, on_lost, ttl=None)` 是看护对象：
不起线程，由调度器主循环每拍调用 `tick()` 驱动；到 `interval` 秒就替持有者续一次，
续期返回 False 立刻回调 `on_lost(lease_id, holder)` 通知持有者停手，之后不再动作；
任务正常结束调 `stop()` 撤下，不触发丢失通知。`interval` 应明显小于租约 TTL。

## 约束

- 现有方法行为与 `tests/test_lease.py` 基线保持一致（基线一个字不改）
- 纯标准库；时间一律走注入的 clock，不许碰真实时间或起真线程
- 新行为测试在 `tests/test_renew.py`

## 运行

```bash
python3 demo.py                          # 发放 / 归还 / 到期演示
python3 -m unittest discover -s tests -v # 全部行为测试
```

## 实现说明

1. 续期失败判定：先查存在且 holder 相等、再判 `now < expires_at`，任一不满足返回 False 且不写任何字段；边界 `now == expires_at` 算失效。
2. `ttl` 不传沿用记录里的上一次租期；显式传入则更新该租期，后续不传的续期也按新租期走；`ttl <= 0` 抛 ValueError。
3. 回收与续期在同一把锁内各自原子完成，二者先后都安全：续期先则看到新到期时刻而存活，回收先则续期随后拿到 False，不存在「刚续上就被清掉」的窗口。
4. 计数口径：`granted` 只在发放时加一，`released` 只在主动归还成功时加一，`reaped` 只在 `reap_expired` 实际删除时加一（累计，不重复计过期读取），`live` 为当下未到期条数。
5. `LeaseWatcher.tick()` 只按注入时钟安排节拍，到点做一次 renew；失败立即回调 `on_lost` 并静默，`stop()` 不触发通知；没有任何线程或真实 sleep。
