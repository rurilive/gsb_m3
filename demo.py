"""主备选举演示。"""
import os
import tempfile
import time

from lease import (
    FencedStore,
    FileLockElection,
    LeaseElection,
    LeaseLostError,
    StaleFencingTokenError,
)

lock_path = os.path.join(tempfile.mkdtemp(), "primary.lock")
primary = FileLockElection(lock_path, "node-a")
standby = FileLockElection(lock_path, "node-b")

print("primary 抢主:", primary.try_acquire())
print("standby 抢主:", standby.try_acquire(), "(被拒)")
print("当前持有者:", primary.current_holder())

primary.release()
print("primary 让位:", not primary.is_primary())
print("standby 接手:", standby.try_acquire())
print("新持有者:", standby.current_holder())

# 第二段：租约选举演示
print("\n--- 租约选举 ---")
lease_path = os.path.join(tempfile.mkdtemp(), "order-primary.lease")
store = FencedStore()  # 订单库存储层，按 fencing token 挡过期主

node_a = LeaseElection(lease_path, "node-a", lease_duration=1.0,
                       renew_interval=0.3)
node_b = LeaseElection(lease_path, "node-b", lease_duration=1.0,
                       renew_interval=0.3)

node_a.try_acquire()
node_a.start()  # 后台定期续租，不占业务写入路径
node_a.update_state({"last_order_id": 100})
store.write("order-100", "paid", node_a.assert_primary())
print("node-a 持租约写单:", store.read("order-100"),
      "token =", node_a.fencing_token)

# node-a GC 停顿：续租线程卡住，租约自然到期
node_a.stop()
node_b.try_acquire()  # 第一次看到静止的租约记录，开始数静默窗口
print("node-b 立即抢位:", node_b.is_primary(), "(要观察满一个租约期)")
time.sleep(1.2)
print("node-a 租约已失效:", not node_a.is_primary())
print("node-b 静默期满接手:", node_b.try_acquire(),
      "token =", node_b.fencing_token)
print("交接状态:", node_b.handover_state())

# 旧主醒来还想用老身份写：本地认输 + 存储层 fencing 双保险
try:
    node_a.assert_primary()
except LeaseLostError:
    print("node-a 本地已认输，写不了")
try:
    store.write("order-100", "refunded", 1)
except StaleFencingTokenError:
    print("旧 token 的写入被存储层拒绝")

store.write("order-101", "paid", node_b.assert_primary())
print("node-b 正常写单:", store.read("order-101"))
node_b.stop()
