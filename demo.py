"""主备选举演示。"""
import os
import tempfile

from lease import FileLockElection

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

# 第二段：租约选举演示（留给实现者补）
