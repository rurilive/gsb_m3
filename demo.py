"""leasekv 现状演示。

第一段：建一张小 KV，写入几条、按键取回、删掉一条，看命中未命中计数与主键顺序；
第二段：预留的按键租约、续约、看门狗回收与 fencing 演示位子（见文末注释）。
"""

from leasekv import LeaseKV


def main():
    print("=== 字典 KV：写入取回删除 ===")
    kv = LeaseKV()
    kv.put("acct", {"balance": 100, "owner": "t1"})
    kv.put("cfg", {"mode": "off"})
    kv.put("note", "hello")
    print("  主键 %s，条数 %d" % (kv.keys(), len(kv)))
    print("  取 cfg -> %s" % (kv.get("cfg"),))
    print("  取 nope -> %s" % (kv.get("nope"),))
    kv.delete("note")
    s = kv.stats()
    print("  删 note 后主键 %s" % (kv.keys(),))
    print("  stats: live=%d hits=%d misses=%d" % (s["live"], s["hits"], s["misses"]))

    # TODO(按键租约、续约与看门狗回收): 在 leasekv 里补出注入时钟、按 key 绑定持有者
    # 与租期的租约、续约、后台式 tick 回收过期租约之后，在这里加一段演示：注入一个
    # 可手动推进的假时钟，grant 一个带 ttl 的 key 拿到初始 token，观察在租期内只有
    # 该 holder 能改这个 key、他人改写被拒；时钟推过 ttl 后租约失效，新的 holder 抢占
    # 时 token 递增，旧 holder 带旧 token 的写被拒；再调用 tick 批量回收过期租约，
    # 打印回收数量，并确认订阅者收到了 key 变更的通知。


if __name__ == "__main__":
    main()