"""leasekv: 内存里的朴素字典 KV。

当前只有一张平铺的字典 KV，见 leasekv/kv.py。
按键租约、续约、看门狗回收、抢占与 fencing token、观察者通知与并发下的租约唯一性
见任务描述。
"""

from leasekv.kv import LeaseKV

__all__ = ["LeaseKV"]