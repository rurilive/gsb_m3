# radixest

埋点链路的去重计数库，纯标准库，无外部依赖。

## 现状

`radixest/counting.py` 提供精确的 `DistinctCounter`：

- `DistinctCounter()`：空计数器，不同 key 原样存在内部 set 里
- `add(key)`：记一个 key，首次出现返回 `True`，重复出现返回 `False`；key 需可哈希
- `count()`：当前不同 key 的个数
- `key in counter` 判断某个 key 是否出现过，`reset()` 清空
- 内部一把锁保护，单次操作在多线程下安全

结果精确，代价是内存随不同 key 数线性增长。

## 问题

分钟级去重流的基数已经到亿级，精确计数器把内存顶穿；分片各数各的再把结果相加，同一个 key 落在多片会被重复入账。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_counter.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 精确计数演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 基数未超 `exact_limit` 时原样存 key 走精确计数，`count()` 与 `error_bound()`（0.0）都精确；超限瞬间把已见 key 灌进位图并丢弃集合，退化为 Linear Counting，估算式 `-bits·ln(零位数/bits)`。
- key 经带类型前缀的稳定编码后用种子化 BLAKE2b 取模定位，固定种子结果可复现；`error_bound()` 给约 3 倍标准差的相对误差上界，位图近饱和（0 位耗尽）时封顶为 1.0。
- 位图稀疏表示存被置位号的 set，稠密表示存定长 `bytearray`；置位数超过可配的 `sparse_max` 自动转稠密，`to_dense()/to_sparse()` 可显式互转，两种表示信息等价，转换前后 `count()` 不变。
- `merge()` 要求两边 `bits` 与 `seed` 相同，对位图按位或生成覆盖并集的新估算器，两边均不修改；合并后的误差界由并区位图当前填充率重新计算，填充越深界越大，两边原界不直接相加。
- 双方都在精确段且并集不超过 `exact_limit` 时合并结果仍精确；否则任一方的精确 key 先映射进位图，合并统一走概率估算。
