# leasekit

调度器里管分片租约的进程内小包，纯标准库，无外部依赖。

## 现状

`leasekit/lease.py` 提供内存里的 `LeaseManager`：

- `LeaseManager(clock=time.monotonic, default_ttl=30.0)`：clock 为注入时钟，default_ttl 为默认租期
- `acquire(holder, ttl=None)` 发放租约并返回 `lease_id`；`ttl` 为空用默认值
- `get(lease_id)` 返回 `Lease` 只读快照；**不存在或已到期都返回 None**
- `release(lease_id, holder)` 归还租约，只有当前持有者、且租约还活着时才成功
- `renew(lease_id, holder, ttl=None)` 续期，到期点推到「现在 + ttl」；成功返回 `True`，租约失效或非当前持有者返回 `False` 且租约不动
- `reap_expired()` 由主循环驱动，清掉到期未续的租约，返回被回收的 id 列表
- `stats()` 返回 `granted` / `released` / `reaped` / `live` 计数快照；`live` 只数还没到期的
- `LeaseWatchdog(manager, lease_id, holder, renew_interval, on_lost, ttl=None)` 看护对象，主循环每轮 `tick()` 驱动：到点替持有者续期，续失败回调 `on_lost(lease_id, holder, reason)`，只通知一次；全程不起线程
- 内部一把锁保护，单个方法调用对多线程安全

`Lease` 是 frozen dataclass，字段为 `id` / `holder` / `ttl` / `expires_at`。

## 事故背景

租期是发放那一刻定死的，到期就作废，没有任何把租约往后延的途径。
长时间任务的持有者中途就丢了租约却毫不知情；过期条目又没人清理，
一直留在内存里。

## 实现说明

- `renew` 在同一次持锁内判定「持有者相同且 now < expires_at」后才把到期点改成 now + ttl；不存在、过期、冒名一律返回 `False` 且 ttl/到期点原样不动，非法 ttl（≤0）抛 `ValueError`。
- `ttl` 不传沿用租约当前租期；显式传入则记录为该租约的新租期，后续无参续期按新值走。
- 到期判定全程闭区间语义：now >= expires_at 即失效（与 `get`/`release` 基线一致），新到期点是 now + ttl 而非旧到期点累加。
- `reap_expired` 与 `renew` 共用同一把锁，「查到期 → 删除/推后」原子完成，不存在刚续上就被清掉的窗口；调用顺序无所谓，同一时刻不会出现交错状态。
- 计数口径：`granted` 只数发放、`released` 数主动归还、`reaped` 数回收删除且只在真正删除时累加（重复回收不重计），三者互斥；`live` 是当前未到期的瞬时值。
- `LeaseWatchdog` 不起线程，`tick(now=None)` 由主循环驱动，每到 `renew_interval` 续一次；续失败立即回调（reason 为 `gone` 或 `wrong_holder`），置失活后不再重复通知。

## 运行

```bash
python3 demo.py                          # 发放 / 归还 / 到期 / 续期看护 / 回收
python3 -m unittest discover -s tests -v # 基线 + 续期/回收测试
```
