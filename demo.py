"""ID 生成器演示。"""
from idgen import IdGenerator

g = IdGenerator()
for i in [g.next_id() for _ in range(5)]:
    print(i, "->", i >> 16, i & 0xFFFF)

# 第二段：多实例演示（三个机房各自出号，互不冲突）
from idgen import FileInstanceRegistry, SnowflakeGenerator

registry = FileInstanceRegistry("/tmp/idgen-demo-leases")
gens = [SnowflakeGenerator(i, registry=registry) for i in range(3)]
ids = [g.next_id() for g in gens for _ in range(3)]
for i in ids:
    print(i, "-> 实例", (i >> 12) & 0x3FF, "序列", i & 0xFFF)
print("去重后:", len(set(ids)), "/", len(ids))
for g in gens:
    g.close()
