"""布隆过滤器基本用法演示（内存去重挡重复请求用的那层）。"""

from bloomx import BloomFilter

bf = BloomFilter(1000, 0.01)
print("empty baseline fp:", bf.estimated_fp())

keys = ["user-1001", "user-1002", "order-77", "sess-abc", "job-42"]
for key in keys:
    bf.add(key)

print("added:", len(keys))
print("members present:", all(k in bf for k in keys))
print("absent probe user-9999:", "user-9999" in bf)
blob = bf.serialize()
print("serialized: %d bytes, magic=%r" % (len(blob), blob[:4]))
