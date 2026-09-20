"""ID 生成器演示。"""
from idgen import IdGenerator

g = IdGenerator()
for i in [g.next_id() for _ in range(5)]:
    print(i, "->", i >> 16, i & 0xFFFF)

# 第二段：多实例演示（留给实现者补）
print("--- 多实例 ---")
gens = [IdGenerator(instance_id=i) for i in range(3)]
ids = [g.next_id() for g in gens for _ in range(3)]
for i in ids:
    print(i, "-> ms", i >> 16, "instance", (i >> 12) & 0xF, "counter", i & 0xFFF)
assert len(ids) == len(set(ids)), "多实例出号必须互不相同"
